"""
Agent C — Bid Evaluator
Compares each tender criterion against extracted bidder data.
Handles numeric normalisation (₹5 crore = 50,000,000), date parsing,
and language variations.

For each criterion returns:
  - verdict: eligible | not_eligible | manual_review
  - reason: ALWAYS explains WHY — especially for not_eligible (no grey area)
  - evidence_field: references the source bidder data field
"""

import json
import re
import os
import logging
from datetime import datetime

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
logger = logging.getLogger(__name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

# ---------------------------------------------------------------------------
# Indian Currency Normalisation
# ---------------------------------------------------------------------------
MULTIPLIERS = {
    "crore": 1_00_00_000,
    "cr": 1_00_00_000,
    "crores": 1_00_00_000,
    "lakh": 1_00_000,
    "lakhs": 1_00_000,
    "lac": 1_00_000,
    "lacs": 1_00_000,
    "thousand": 1_000,
    "k": 1_000,
    "million": 10_00_000,
    "billion": 1_00_00_00_000,
}


def normalise_currency(value_str: str) -> float | None:
    """
    Normalise Indian currency strings to a float.
    Examples:
        "₹5 Crore" → 50000000.0
        "₹10,50,000" → 1050000.0
        "5.2 crores" → 52000000.0
        "Rs. 50 Lakh" → 5000000.0
    """
    if not value_str:
        return None

    text = value_str.lower().strip()
    # Remove currency symbols and prefixes
    text = re.sub(r'[₹$]', '', text)
    text = re.sub(r'\brs\.?\b', '', text)
    text = re.sub(r'\binr\b', '', text)
    text = text.strip()

    # Check for multiplier words
    multiplier = 1
    for word, mult in MULTIPLIERS.items():
        if word in text:
            multiplier = mult
            text = text.replace(word, '').strip()
            break

    # Extract numeric value
    text = text.replace(',', '').strip()
    match = re.search(r'[\d.]+', text)
    if match:
        try:
            return float(match.group()) * multiplier
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# LLM-assisted evaluation
# ---------------------------------------------------------------------------
EVAL_SYSTEM_PROMPT = """You are an impartial government procurement bid evaluator AI.

You are given:
1. A list of tender criteria (what the tender requires)
2. Extracted bidder data (what the bidder claims/provides)

For EACH criterion, you must determine:
- "verdict": one of "eligible", "not_eligible", or "manual_review"
- "reason": A CLEAR, SPECIFIC explanation. 
  - For "not_eligible": MUST state exactly WHY the bidder fails. Example: "Bidder's annual turnover is ₹3.2 Crore which is below the required minimum of ₹5 Crore"
  - For "eligible": Briefly confirm how the requirement is met.
  - For "manual_review": Explain what data is missing or ambiguous.
- "evidence_field": which bidder data field you used (e.g. "annual_turnover")
- "extracted_value": the actual value found in bidder data
- "confidence": float 0-1 of how confident you are

CRITICAL RULES:
1. There must be NO GREY AREA for not_eligible verdicts. State the exact shortfall.
2. For numeric criteria, compare normalised values (₹5 Crore = ₹5,00,00,000 = 50,000,000)
3. Mandatory criteria that are not met → not_eligible (no exceptions)
4. If bidder data for a mandatory criterion is completely missing → not_eligible with reason "Required data not provided by bidder"
5. Only use manual_review when data EXISTS but is ambiguous or partially legible
6. Be strict but fair — do not infer data that isn't there

Return a JSON object with:
{
  "criteria_results": [
    {
      "criterion_name": "...",
      "criterion_type": "technical|financial|compliance",
      "is_mandatory": true/false,
      "verdict": "eligible|not_eligible|manual_review",
      "reason": "...",
      "evidence_field": "...",
      "extracted_value": "...",
      "threshold": "...",
      "confidence": 0.0-1.0
    }
  ],
  "overall_status": "eligible|not_eligible|manual_review",
  "rejection_reasons": ["list of clear reasons if not_eligible"]
}

overall_status rules:
- If ANY mandatory criterion is not_eligible → overall = "not_eligible"
- If all mandatory criteria are eligible but some have manual_review → overall = "manual_review"  
- If all criteria are eligible → overall = "eligible"

rejection_reasons: List EVERY specific reason the bidder is not eligible. Leave empty if eligible.
"""


def evaluate_bid(criteria: dict, bidder_data: dict) -> dict:
    """
    Agent C entry point.
    Compares each criterion against extracted bidder values.
    Returns a full audit object with per-criterion verdicts.
    """
    bidder_id = bidder_data.get("bidder_id", "unknown")
    logger.info("Agent C: Evaluating bidder %s", bidder_id)

    # Prepare criteria summary for LLM
    all_criteria = []
    for ctype in ("technical_criteria", "financial_criteria", "compliance_criteria"):
        for c in criteria.get(ctype, []):
            c_copy = dict(c)
            c_copy["criterion_type"] = ctype.replace("_criteria", "")
            all_criteria.append(c_copy)

    if not all_criteria:
        logger.warning("No criteria found — returning manual_review")
        return {
            "bidder_id": bidder_id,
            "timestamp": datetime.utcnow().isoformat(),
            "criteria_results": [],
            "overall_status": "manual_review",
            "rejection_reasons": ["No criteria were extracted from the tender document"],
        }

    # Build the prompt payload
    criteria_text = json.dumps(all_criteria, indent=2, ensure_ascii=False)
    bidder_text = json.dumps(bidder_data, indent=2, ensure_ascii=False)

    try:
        response = model.generate_content(
            f"{EVAL_SYSTEM_PROMPT}\n\nTENDER CRITERIA:\n{criteria_text}\n\nBIDDER DATA:\n{bidder_text}\n\nEvaluate this bidder against ALL criteria. Be explicit about reasons for not_eligible verdicts — no grey area.",
            generation_config={"response_mime_type": "application/json"}
        )
        result = json.loads(response.text)
    except Exception as e:
        logger.error("Agent C LLM call failed: %s", e)
        raise RuntimeError(f"Agent C evaluation failed: {e}") from e

    # Add metadata
    result["bidder_id"] = bidder_id
    result["timestamp"] = datetime.utcnow().isoformat()

    # Ensure rejection_reasons exists
    if "rejection_reasons" not in result:
        result["rejection_reasons"] = []

    # Double-check: if overall_status is not_eligible, there MUST be rejection_reasons
    if result.get("overall_status") == "not_eligible" and not result["rejection_reasons"]:
        # Extract reasons from criteria_results
        for cr in result.get("criteria_results", []):
            if cr.get("verdict") == "not_eligible" and cr.get("is_mandatory", True):
                result["rejection_reasons"].append(cr.get("reason", "Criterion not met"))

    logger.info(
        "Agent C: Bidder %s — Status: %s, Rejections: %d",
        bidder_id,
        result.get("overall_status"),
        len(result.get("rejection_reasons", [])),
    )
    return result
