"""
Agent B — Bidder Document Parser
Extracts key facts from scanned government bidder documents using
OpenAI Vision API (primary) or LayoutLMv3 (fallback).
Handles tables, stamps, seals, and mixed-format pages.
Design principle: NEVER make decisions — only extract facts.
"""

import base64
import json
import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from pdf2image import convert_from_path
import pytesseract
import google.generativeai as genai

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TESSERACT_PATH = os.getenv("TESSERACT_PATH")
POPPLER_PATH = os.getenv("POPPLER_PATH")
USE_LAYOUTLM = os.getenv("USE_LAYOUTLM", "false").lower() == "true"

if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

# ---------------------------------------------------------------------------
# System Prompt for Vision API
# ---------------------------------------------------------------------------
VISION_SYSTEM_PROMPT = """You are a document data-extraction AI for Indian government procurement.
You are given page images from a bidder's submission document.

Your ONLY job is to EXTRACT facts. NEVER make eligibility decisions.

Extract the following fields:
- "annual_turnover": The company's annual turnover as stated (preserve original format, e.g. "₹5.2 Crore" or "52,00,000")
- "projects_completed": Number of similar projects completed (integer)
- "certifications": List of all certifications mentioned (ISO, BIS, FSSAI, etc.)
- "registration_number": Company/firm registration number (CIN, GSTIN, PAN, etc.)
- "additional_fields": Any other relevant facts found (as key-value pairs)
- "confidence_scores": For each of the four main fields, rate your confidence 0.0 to 1.0:
  - 1.0 = clearly printed/typed and unambiguous
  - 0.7-0.9 = readable but some uncertainty (e.g. partial stamp overlay)
  - 0.4-0.6 = partially obscured or handwritten
  - 0.0-0.3 = barely legible or inferred

Rules:
1. If a field is not found in the document, set it to null and confidence to 0.0
2. Preserve exact values — do NOT normalise currencies or convert units
3. If text is in Hindi or mixed Hindi/English, transliterate values to English
4. For tables, extract all rows and note which row contains the relevant data
5. Note any stamps, seals, or signatures found in additional_fields
6. Return ONLY valid JSON, no markdown, no explanation
"""

OCR_SYSTEM_PROMPT = """You are a document data-extraction AI for Indian government procurement.
You are given OCR-extracted text from a bidder's submission document.

Your ONLY job is to EXTRACT facts. NEVER make eligibility decisions.

Extract the following fields and return as JSON:
- "annual_turnover": string or null
- "projects_completed": integer or null
- "certifications": list of strings
- "registration_number": string or null
- "additional_fields": dict of any other relevant key-value facts
- "confidence_scores": { "annual_turnover": float, "projects_completed": float, "certifications": float, "registration_number": float }

Confidence 0.0-1.0 based on how clearly the data appeared in the OCR text.
If a field is not found, set it to null and confidence to 0.0.
Return ONLY valid JSON.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def pdf_to_images(pdf_path: str) -> list:
    """Convert PDF to list of PIL Image objects."""
    poppler_kwargs = {}
    if POPPLER_PATH:
        poppler_kwargs["poppler_path"] = POPPLER_PATH
    return convert_from_path(str(pdf_path), dpi=200, fmt="jpeg", **poppler_kwargs)


def image_to_base64(img) -> str:
    # Not needed for Gemini, but keeping to avoid changing logic elsewhere if used
    pass


def extract_text_ocr(pdf_path: str) -> str:
    """Fallback: extract text via pytesseract OCR."""
    images = pdf_to_images(pdf_path)
    parts = []
    for i, img in enumerate(images, 1):
        text = pytesseract.image_to_string(img, lang="eng")
        parts.append(f"--- PAGE {i} ---\n{text}")
    return "\n\n".join(parts)


import time

def call_gemini_with_retry(prompt_parts, generation_config, max_retries=3):
    """Wrapper to handle 429 rate limit errors automatically."""
    for attempt in range(max_retries):
        try:
            return model.generate_content(prompt_parts, generation_config=generation_config)
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                if attempt < max_retries - 1:
                    logger.warning("Gemini API rate limit hit (429). Waiting 60s before retry %d/%d...", attempt + 1, max_retries - 1)
                    time.sleep(60)
                    continue
            raise e

# ---------------------------------------------------------------------------
# Vision API Extraction
# ---------------------------------------------------------------------------
def parse_with_vision(pdf_path: str) -> dict:
    """Use OpenAI Vision API to extract data from document images."""
    images = pdf_to_images(pdf_path)
    logger.info("Agent B (Vision): Processing %d pages", len(images))

    # For documents with many pages, process in batches and merge
    # Send up to 5 pages at once (API limit consideration)
    all_content = []
    batch_size = 5

    for batch_start in range(0, len(images), batch_size):
        batch = images[batch_start:batch_start + batch_size]
        # Gemini accepts PIL Images directly in the content array
        prompt_parts = [VISION_SYSTEM_PROMPT, "\n\nExtract all relevant bidder data from these document pages:"]
        prompt_parts.extend(batch)

        response = call_gemini_with_retry(
            prompt_parts,
            generation_config={"response_mime_type": "application/json"}
        )
        batch_data = json.loads(response.text)
        all_content.append(batch_data)

    # Merge batch results (take highest-confidence values)
    return merge_extractions(all_content)


def merge_extractions(extractions: list[dict]) -> dict:
    """Merge multiple extraction batches, keeping highest-confidence values."""
    if len(extractions) == 1:
        return extractions[0]

    merged = {
        "annual_turnover": None,
        "projects_completed": None,
        "certifications": [],
        "registration_number": None,
        "additional_fields": {},
        "confidence_scores": {
            "annual_turnover": 0.0,
            "projects_completed": 0.0,
            "certifications": 0.0,
            "registration_number": 0.0,
        },
    }

    for ext in extractions:
        scores = ext.get("confidence_scores", {})
        # Keep value with higher confidence
        for field in ("annual_turnover", "projects_completed", "registration_number"):
            new_conf = float(scores.get(field, 0))
            old_conf = merged["confidence_scores"].get(field, 0)
            if new_conf > old_conf and ext.get(field) is not None:
                merged[field] = ext[field]
                merged["confidence_scores"][field] = new_conf

        # Merge certifications (union)
        certs = ext.get("certifications", [])
        if isinstance(certs, list):
            for c in certs:
                if c not in merged["certifications"]:
                    merged["certifications"].append(c)
            cert_conf = float(scores.get("certifications", 0))
            if cert_conf > merged["confidence_scores"]["certifications"]:
                merged["confidence_scores"]["certifications"] = cert_conf

        # Merge additional fields
        add = ext.get("additional_fields", {})
        if isinstance(add, dict):
            merged["additional_fields"].update(add)

    return merged


# ---------------------------------------------------------------------------
# OCR Fallback Extraction
# ---------------------------------------------------------------------------
def parse_with_ocr(pdf_path: str) -> dict:
    """Fallback: extract text via OCR and send to LLM for structuring."""
    text = extract_text_ocr(pdf_path)
    logger.info("Agent B (OCR fallback): Extracted %d chars", len(text))

    max_chars = 60_000
    if len(text) > max_chars:
        text = text[:max_chars]

    response = call_gemini_with_retry(
        f"{OCR_SYSTEM_PROMPT}\n\nExtract bidder data from this OCR text:\n\n{text}",
        generation_config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------
def parse_bidder_document(pdf_path: str) -> dict:
    """
    Agent B entry point.
    Extracts key facts from a scanned bidder document.
    Returns structured data with confidence scores.
    NEVER makes eligibility decisions — only extracts.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info("Agent B: Starting document parsing for %s", path.name)

    try:
        if USE_LAYOUTLM:
            logger.info("Using LayoutLMv3 mode (OCR + LLM structuring)")
            result = parse_with_ocr(pdf_path)
        else:
            logger.info("Using Vision API mode")
            result = parse_with_vision(pdf_path)
    except Exception as e:
        logger.error("Primary extraction failed: %s — falling back to OCR", e)
        try:
            result = parse_with_ocr(pdf_path)
        except Exception as e2:
            logger.error("OCR fallback also failed: %s", e2)
            raise RuntimeError(f"Agent B: All extraction methods failed: {e2}") from e2

    # Ensure required keys
    defaults = {
        "annual_turnover": None,
        "projects_completed": None,
        "certifications": [],
        "registration_number": None,
        "additional_fields": {},
        "confidence_scores": {
            "annual_turnover": 0.0,
            "projects_completed": 0.0,
            "certifications": 0.0,
            "registration_number": 0.0,
        },
    }
    for key, default in defaults.items():
        if key not in result:
            result[key] = default

    # Ensure confidence_scores sub-keys
    cs = result.get("confidence_scores", {})
    for field in ("annual_turnover", "projects_completed", "certifications", "registration_number"):
        if field not in cs:
            cs[field] = 0.0
        else:
            cs[field] = float(cs[field])
    result["confidence_scores"] = cs

    logger.info(
        "Agent B: Extraction complete — turnover=%s, projects=%s, certs=%d, reg=%s",
        result.get("annual_turnover"),
        result.get("projects_completed"),
        len(result.get("certifications", [])),
        result.get("registration_number"),
    )
    return result
