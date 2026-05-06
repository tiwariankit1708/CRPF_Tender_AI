"""
Agent A — Criteria Extraction Agent
Reads a tender PDF, sends its text to an LLM, and returns structured
eligibility criteria categorised as technical, financial, and compliance.
"""

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

if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a government procurement specialist AI. Your task is to extract and categorise ALL eligibility requirements, supply specifications, and conditions explicitly stated in the tender document.

You MUST return a valid JSON object with exactly these three keys:
- "technical_criteria": list of criteria related to technical capability, experience, staffing, equipment, material specifications, supply items, or quality standards.
- "financial_criteria": list of criteria related to turnover, net worth, bank guarantees, EMD, pricing rules, etc.
- "compliance_criteria": list of criteria related to registrations, certifications, legal compliance, GST, PAN, licences, etc.

Each criterion object MUST have these fields:
- "name": short descriptive name (e.g. "Minimum Annual Turnover", "Quality Standard")
- "description": full description as stated in the document
- "threshold": the minimum/maximum value, requirement, or specification (e.g. "₹5 Crore", "3 years", "ISO 9001", "Approved quality")
- "is_mandatory": true if the criterion is mandatory/essential, false if desirable/optional
- "weight": float 0.0-1.0 indicating relative importance (mandatory items should be 1.0)

Rules:
1. Extract EVERY requirement or specification mentioned — do not summarise or skip any. Even if it is a simple list of items to supply with a quality condition, treat it as a technical criterion.
2. If a criterion could belong to multiple categories, place it in the most relevant one.
3. If a threshold is not explicitly stated, set threshold to "Not specified".
4. Preserve exact figures, dates, and values from the document.
5. Return ONLY the JSON object, no markdown, no explanation.
"""


# ---------------------------------------------------------------------------
# PDF → Text extraction
# ---------------------------------------------------------------------------
def extract_text_from_pdf(pdf_path: str) -> str:
    """Convert PDF pages to images and OCR them to extract full text."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    poppler_kwargs = {}
    if POPPLER_PATH:
        poppler_kwargs["poppler_path"] = POPPLER_PATH

    try:
        images = convert_from_path(str(path), dpi=300, **poppler_kwargs)
    except Exception as e:
        logger.error("pdf2image conversion failed: %s", e)
        raise RuntimeError(f"Failed to convert PDF to images: {e}") from e

    full_text_parts: list[str] = []
    for i, img in enumerate(images, 1):
        text = pytesseract.image_to_string(img, lang="eng")
        full_text_parts.append(f"--- PAGE {i} ---\n{text}")

    full_text = "\n\n".join(full_text_parts)
    logger.info("Extracted %d characters from %d pages of %s",
                len(full_text), len(images), path.name)
    return full_text


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------
import time

def call_gemini_with_retry(prompt, generation_config, max_retries=3):
    """Wrapper to handle 429 rate limit errors automatically."""
    for attempt in range(max_retries):
        try:
            return model.generate_content(prompt, generation_config=generation_config)
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                if attempt < max_retries - 1:
                    logger.warning("Gemini API rate limit hit (429). Waiting 60s before retry %d/%d...", attempt + 1, max_retries - 1)
                    time.sleep(60)
                    continue
            raise e


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------
def extract_criteria(pdf_path: str) -> dict:
    """
    Agent A entry point.
    Reads a tender PDF, extracts text via OCR, sends to LLM,
    and returns structured criteria as a dict.
    """
    logger.info("Agent A: Starting criteria extraction from %s", pdf_path)

    # Step 1 — Extract text
    text = extract_text_from_pdf(pdf_path)

    if len(text.strip()) < 50:
        logger.warning("Very little text extracted — document may be image-only or empty.")

    # Step 2 — Truncate if needed (LLM context window)
    max_chars = 80_000  # ~20k tokens
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[... TRUNCATED — document exceeds context limit ...]"
        logger.warning("Tender text truncated to %d chars", max_chars)

    # Step 3 — Call LLM
    try:
        response = call_gemini_with_retry(
            f"{SYSTEM_PROMPT}\n\nExtract all eligibility requirements, supply specifications, and conditions from this tender document:\n\n{text}",
            generation_config={"response_mime_type": "application/json"}
        )
        raw = response.text
        criteria = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("LLM returned invalid JSON: %s", e)
        criteria = {
            "technical_criteria": [],
            "financial_criteria": [],
            "compliance_criteria": [],
        }
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        raise RuntimeError(f"Agent A LLM call failed: {e}") from e

    # Step 4 — Ensure required keys exist
    for key in ("technical_criteria", "financial_criteria", "compliance_criteria"):
        if key not in criteria:
            criteria[key] = []

    logger.info(
        "Agent A: Extracted %d technical, %d financial, %d compliance criteria",
        len(criteria["technical_criteria"]),
        len(criteria["financial_criteria"]),
        len(criteria["compliance_criteria"]),
    )
    return criteria
