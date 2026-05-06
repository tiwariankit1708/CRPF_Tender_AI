"""
Agent D — Evaluation Auditor
Reviews each criterion result from Agent C and flags items
that require human review. Generates review notes explaining
what is unclear and what a human reviewer should check.
"""

import json
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
# Thresholds
# ---------------------------------------------------------------------------
CONFIDENCE_THRESHOLD = 0.75  # Flag if below this


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------
AUDIT_SYSTEM_PROMPT = """You are a senior government procurement auditor AI.
You review the evaluation results produced by an automated bid evaluation system.

Your job is to identify items that need HUMAN REVIEW and generate clear notes.

For each flagged item, provide:
- "criterion_name": name of the criterion
- "current_verdict": the verdict given by the evaluator
- "confidence": the confidence score
- "review_note": A detailed explanation of:
  1. What is unclear or uncertain
  2. What the human reviewer should specifically check
  3. What documents or evidence they should look at
  4. Any discrepancies or anomalies noticed
- "evidence_field": which data field is relevant

Flag an item if ANY of these conditions are true:
1. confidence < 0.75
2. verdict == "manual_review"
3. The reason mentions ambiguity, partial data, or unclear information
4. There's a mismatch between the extracted value and typical expected ranges
5. The evidence_field is null or empty for a mandatory criterion

Return JSON:
{
  "flagged_items": [...],
  "human_review_required": true/false,
  "audit_summary": "brief overall assessment"
}

Set human_review_required to true if ANY items are flagged.
"""


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------
def audit_evaluation(evaluation: dict) -> dict:
    """
    Agent D entry point.
    Reviews evaluation results and flags items needing human review.

    Parameters:
        evaluation: dict from Agent C with criteria_results

    Returns:
        dict with flagged_items list and human_review_required bool
    """
    bidder_id = evaluation.get("bidder_id", "unknown")
    logger.info("Agent D: Auditing evaluation for bidder %s", bidder_id)

    criteria_results = evaluation.get("criteria_results", [])

    if not criteria_results:
        logger.warning("No criteria results to audit")
        return {
            "tender_id": evaluation.get("tender_id", "unknown"),
            "bidder_id": bidder_id,
            "flagged_items": [{
                "criterion_name": "N/A",
                "current_verdict": "manual_review",
                "confidence": 0.0,
                "review_note": "No evaluation results found. The entire evaluation needs human review.",
                "evidence_field": None,
            }],
            "human_review_required": True,
            "audited_at": datetime.utcnow().isoformat(),
        }

    # -----------------------------------------------------------------------
    # Step 1: Rule-based pre-flagging (fast, no LLM needed)
    # -----------------------------------------------------------------------
    pre_flagged = []
    for cr in criteria_results:
        confidence = float(cr.get("confidence", 0))
        verdict = cr.get("verdict", "manual_review")

        should_flag = False
        flag_reasons = []

        if confidence < CONFIDENCE_THRESHOLD:
            should_flag = True
            flag_reasons.append(f"Low confidence ({confidence:.2f} < {CONFIDENCE_THRESHOLD})")

        if verdict == "manual_review":
            should_flag = True
            flag_reasons.append("Verdict is manual_review")

        if cr.get("is_mandatory", True) and not cr.get("evidence_field"):
            should_flag = True
            flag_reasons.append("No evidence field for mandatory criterion")

        if should_flag:
            pre_flagged.append({
                "criterion": cr,
                "flag_reasons": flag_reasons,
            })

    logger.info("Agent D: Pre-flagged %d of %d criteria", len(pre_flagged), len(criteria_results))

    # -----------------------------------------------------------------------
    # Step 2: LLM-enhanced audit (generates human-readable review notes)
    # -----------------------------------------------------------------------
    if pre_flagged:
        try:
            eval_text = json.dumps(evaluation, indent=2, ensure_ascii=False)
            flagged_text = json.dumps(pre_flagged, indent=2, ensure_ascii=False)

            response = model.generate_content(
                f"{AUDIT_SYSTEM_PROMPT}\n\nFULL EVALUATION:\n{eval_text}\n\nPRE-FLAGGED ITEMS:\n{flagged_text}\n\nGenerate detailed review notes for each flagged item. Also check if any other items should be flagged.",
                generation_config={"response_mime_type": "application/json"}
            )
            audit_result = json.loads(response.text)
        except Exception as e:
            logger.error("Agent D LLM audit failed: %s — using rule-based flags", e)
            # Fall back to rule-based flags
            audit_result = {
                "flagged_items": [
                    {
                        "criterion_name": f["criterion"].get("criterion_name", "Unknown"),
                        "current_verdict": f["criterion"].get("verdict", "manual_review"),
                        "confidence": float(f["criterion"].get("confidence", 0)),
                        "review_note": f"Flagged due to: {'; '.join(f['flag_reasons'])}. "
                                       f"Original reason: {f['criterion'].get('reason', 'N/A')}",
                        "evidence_field": f["criterion"].get("evidence_field"),
                    }
                    for f in pre_flagged
                ],
                "human_review_required": True,
            }
    else:
        audit_result = {
            "flagged_items": [],
            "human_review_required": False,
        }

    # Add metadata
    audit_result["tender_id"] = evaluation.get("tender_id", "unknown")
    audit_result["bidder_id"] = bidder_id
    audit_result["audited_at"] = datetime.utcnow().isoformat()
    audit_result["human_review_required"] = len(audit_result.get("flagged_items", [])) > 0

    logger.info(
        "Agent D: Audit complete — %d flagged items, human_review_required=%s",
        len(audit_result.get("flagged_items", [])),
        audit_result["human_review_required"],
    )
    return audit_result
