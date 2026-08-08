"""
CRPF Tender AI — FastAPI Backend
Main application with all endpoints for the tender evaluation pipeline.
"""

import json
import os
import uuid
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

# Agents
from agents.criteria_agent import extract_criteria
from agents.parser_agent import parse_bidder_document
from agents.evaluator_agent import evaluate_bid
from agents.auditor_agent import audit_evaluation

# Report generation
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

load_dotenv()

# Track server start time for uptime calculation
SERVER_START_TIME = datetime.utcnow()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("crpf_tender_ai")

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
STORAGE_DIR = Path("storage")
TENDERS_DIR = STORAGE_DIR / "tenders"
BIDS_DIR = STORAGE_DIR / "bids"
REPORTS_DIR = STORAGE_DIR / "reports"

for d in (TENDERS_DIR, BIDS_DIR, REPORTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
APP_VERSION = "1.1.0"

app = FastAPI(
    title="CRPF Tender AI",
    description="Multi-agent AI system for government procurement tender evaluation",
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def save_json(filepath: Path, data: dict):
    """Save dict as JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def load_json(filepath: Path) -> dict | None:
    """Load JSON file, return None if not found."""
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# ---------------------------------------------------------------------------
# POST /upload/tender — Accept PDF, run Agent A, return criteria
# ---------------------------------------------------------------------------
@app.post("/upload/tender")
async def upload_tender(file: UploadFile = File(...)):
    """Upload a tender PDF and extract eligibility criteria using Agent A."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    tender_id = str(uuid.uuid4())[:8]
    tender_dir = TENDERS_DIR / tender_id
    tender_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded PDF
    pdf_path = tender_dir / file.filename
    content = await file.read()
    with open(pdf_path, "wb") as f:
        f.write(content)

    logger.info("Tender uploaded: %s (ID: %s)", file.filename, tender_id)

    # Run Agent A
    try:
        criteria = extract_criteria(str(pdf_path))
    except Exception as e:
        logger.error("Agent A failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Criteria extraction failed: {str(e)}")

    # Save criteria
    result = {
        "tender_id": tender_id,
        "filename": file.filename,
        "technical_criteria": criteria.get("technical_criteria", []),
        "financial_criteria": criteria.get("financial_criteria", []),
        "compliance_criteria": criteria.get("compliance_criteria", []),
        "extracted_at": datetime.utcnow().isoformat(),
    }
    save_json(tender_dir / "criteria.json", result)

    return result


# ---------------------------------------------------------------------------
# POST /upload/bid — Accept PDF + bidder ID, run Agent B
# ---------------------------------------------------------------------------
@app.post("/upload/bid")
async def upload_bid(
    file: UploadFile = File(...),
    bidder_id: str = Form(...),
    tender_id: str = Form(...),
):
    """Upload a bidder document PDF, extract data using Agent B."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Verify tender exists
    tender_dir = TENDERS_DIR / tender_id
    if not tender_dir.exists():
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")

    bid_dir = BIDS_DIR / tender_id / bidder_id
    bid_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded PDF
    pdf_path = bid_dir / file.filename
    content = await file.read()
    with open(pdf_path, "wb") as f:
        f.write(content)

    logger.info("Bid uploaded: %s (Bidder: %s, Tender: %s)", file.filename, bidder_id, tender_id)

    # Run Agent B
    try:
        bidder_data = parse_bidder_document(str(pdf_path))
    except Exception as e:
        logger.error("Agent B failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Document parsing failed: {str(e)}")

    # Add metadata
    bidder_data["bidder_id"] = bidder_id
    bidder_data["tender_id"] = tender_id
    bidder_data["filename"] = file.filename
    bidder_data["parsed_at"] = datetime.utcnow().isoformat()

    save_json(bid_dir / "bidder_data.json", bidder_data)

    return bidder_data


# ---------------------------------------------------------------------------
# POST /evaluate/{tender_id} — Run Agent C on all bids
# ---------------------------------------------------------------------------
@app.post("/evaluate/{tender_id}")
async def evaluate_tender(tender_id: str):
    """Evaluate all bids for a tender using Agent C."""
    tender_dir = TENDERS_DIR / tender_id
    criteria_path = tender_dir / "criteria.json"

    if not criteria_path.exists():
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} criteria not found")

    criteria = load_json(criteria_path)
    bids_dir = BIDS_DIR / tender_id

    if not bids_dir.exists() or not any(bids_dir.iterdir()):
        raise HTTPException(status_code=404, detail=f"No bids found for tender {tender_id}")

    evaluations = []
    for bidder_dir in bids_dir.iterdir():
        if not bidder_dir.is_dir():
            continue

        bidder_data_path = bidder_dir / "bidder_data.json"
        if not bidder_data_path.exists():
            continue

        bidder_data = load_json(bidder_data_path)
        bidder_id = bidder_dir.name

        logger.info("Evaluating bidder: %s", bidder_id)

        try:
            evaluation = evaluate_bid(criteria, bidder_data)
            evaluation["tender_id"] = tender_id
            save_json(bidder_dir / "evaluation.json", evaluation)
            evaluations.append(evaluation)
        except Exception as e:
            logger.error("Evaluation failed for bidder %s: %s", bidder_id, e)
            evaluations.append({
                "bidder_id": bidder_id,
                "tender_id": tender_id,
                "error": str(e),
                "overall_status": "manual_review",
                "criteria_results": [],
                "rejection_reasons": [f"Evaluation system error: {str(e)}"],
            })

    # Save all evaluations
    save_json(tender_dir / "evaluations.json", {"evaluations": evaluations})

    return {"tender_id": tender_id, "evaluations": evaluations}


# ---------------------------------------------------------------------------
# GET /audit/{tender_id} — Run Agent D, return flagged items
# ---------------------------------------------------------------------------
@app.get("/audit/{tender_id}")
async def audit_tender(tender_id: str):
    """Run audit on all evaluations for a tender using Agent D."""
    tender_dir = TENDERS_DIR / tender_id
    evaluations_path = tender_dir / "evaluations.json"

    if not evaluations_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Evaluations not found for tender {tender_id}. Run /evaluate first.",
        )

    evaluations_data = load_json(evaluations_path)
    evaluations = evaluations_data.get("evaluations", [])

    audits = []
    for evaluation in evaluations:
        if evaluation.get("error"):
            # Skip errored evaluations
            audits.append({
                "tender_id": tender_id,
                "bidder_id": evaluation.get("bidder_id", "unknown"),
                "flagged_items": [{
                    "criterion_name": "System Error",
                    "current_verdict": "manual_review",
                    "confidence": 0.0,
                    "review_note": f"Evaluation failed with error: {evaluation['error']}",
                    "evidence_field": None,
                }],
                "human_review_required": True,
            })
            continue

        try:
            audit = audit_evaluation(evaluation)
            audit["tender_id"] = tender_id
            audits.append(audit)
        except Exception as e:
            logger.error("Audit failed for bidder %s: %s", evaluation.get("bidder_id"), e)
            audits.append({
                "tender_id": tender_id,
                "bidder_id": evaluation.get("bidder_id", "unknown"),
                "flagged_items": [],
                "human_review_required": False,
                "error": str(e),
            })

    # Save audits
    save_json(tender_dir / "audits.json", {"audits": audits})

    return {"tender_id": tender_id, "audits": audits}


# ---------------------------------------------------------------------------
# GET /report/{tender_id} — Generate PDF report
# ---------------------------------------------------------------------------
@app.get("/report/{tender_id}")
async def generate_report(tender_id: str):
    """Generate a comprehensive PDF report with full audit trail."""
    tender_dir = TENDERS_DIR / tender_id

    criteria = load_json(tender_dir / "criteria.json")
    evaluations_data = load_json(tender_dir / "evaluations.json")
    audits_data = load_json(tender_dir / "audits.json")

    if not criteria:
        raise HTTPException(status_code=404, detail="Tender criteria not found")
    if not evaluations_data:
        raise HTTPException(status_code=404, detail="Evaluations not found. Run /evaluate first.")

    evaluations = evaluations_data.get("evaluations", [])
    audits = audits_data.get("audits", []) if audits_data else []

    # Build summary
    eligible = sum(1 for e in evaluations if e.get("overall_status") == "eligible")
    not_eligible = sum(1 for e in evaluations if e.get("overall_status") == "not_eligible")
    review = sum(1 for e in evaluations if e.get("overall_status") == "manual_review")

    report_data = {
        "tender_id": tender_id,
        "generated_at": datetime.utcnow().isoformat(),
        "total_bidders": len(evaluations),
        "eligible_count": eligible,
        "not_eligible_count": not_eligible,
        "manual_review_count": review,
        "bidder_summaries": [],
    }

    for ev in evaluations:
        bid_id = ev.get("bidder_id", "unknown")
        audit_match = next((a for a in audits if a.get("bidder_id") == bid_id), {})
        report_data["bidder_summaries"].append({
            "bidder_id": bid_id,
            "overall_status": ev.get("overall_status", "manual_review"),
            "rejection_reasons": ev.get("rejection_reasons", []),
            "flagged_count": len(audit_match.get("flagged_items", [])),
            "human_review_required": audit_match.get("human_review_required", False),
        })

    # Generate PDF
    pdf_path = REPORTS_DIR / f"report_{tender_id}.pdf"
    _generate_pdf_report(pdf_path, report_data, criteria, evaluations, audits)

    report_data["report_pdf_path"] = str(pdf_path)
    save_json(tender_dir / "report.json", report_data)

    return FileResponse(
        path=str(pdf_path),
        filename=f"CRPF_Tender_Report_{tender_id}.pdf",
        media_type="application/pdf",
    )


def _generate_pdf_report(
    pdf_path: Path, report: dict, criteria: dict,
    evaluations: list, audits: list
):
    """Generate a formatted PDF report using ReportLab."""
    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"],
        fontSize=20, textColor=HexColor("#1a237e"),
        spaceAfter=20,
    )
    heading_style = ParagraphStyle(
        "CustomHeading", parent=styles["Heading2"],
        fontSize=14, textColor=HexColor("#283593"),
        spaceBefore=15, spaceAfter=8,
    )
    body_style = styles["Normal"]

    elements = []

    # Title
    elements.append(Paragraph("CRPF Tender Evaluation Report", title_style))
    elements.append(Paragraph(
        f"Tender ID: {report['tender_id']} | Generated: {report['generated_at']}",
        body_style,
    ))
    elements.append(Spacer(1, 20))

    # Summary
    elements.append(Paragraph("Executive Summary", heading_style))
    summary_data = [
        ["Metric", "Count"],
        ["Total Bidders", str(report["total_bidders"])],
        ["Eligible", str(report["eligible_count"])],
        ["Not Eligible", str(report["not_eligible_count"])],
        ["Manual Review", str(report["manual_review_count"])],
    ]
    summary_table = Table(summary_data, colWidths=[3 * inch, 2 * inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1a237e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f5f5f5"), HexColor("#ffffff")]),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Per-bidder results
    elements.append(Paragraph("Bidder-wise Results", heading_style))
    for ev in evaluations:
        bid_id = ev.get("bidder_id", "unknown")
        status = ev.get("overall_status", "unknown")
        status_display = {
            "eligible": "✓ ELIGIBLE",
            "not_eligible": "✗ NOT ELIGIBLE",
            "manual_review": "⚠ MANUAL REVIEW",
        }.get(status, status.upper())

        elements.append(Paragraph(
            f"<b>Bidder: {bid_id}</b> — {status_display}", body_style
        ))

        # Rejection reasons
        reasons = ev.get("rejection_reasons", [])
        if reasons:
            elements.append(Paragraph("<b>Rejection Reasons:</b>", body_style))
            for r in reasons:
                elements.append(Paragraph(f"  • {r}", body_style))

        # Criteria breakdown
        results = ev.get("criteria_results", [])
        if results:
            cr_data = [["Criterion", "Verdict", "Reason"]]
            for cr in results:
                verdict = cr.get("verdict", "unknown")
                cr_data.append([
                    cr.get("criterion_name", ""),
                    verdict.upper(),
                    cr.get("reason", "")[:80],
                ])
            cr_table = Table(cr_data, colWidths=[2 * inch, 1.2 * inch, 3.5 * inch])
            cr_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#37474f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#fafafa"), HexColor("#ffffff")]),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elements.append(Spacer(1, 8))
            elements.append(cr_table)

        elements.append(Spacer(1, 15))

    # Audit flags
    if audits:
        elements.append(PageBreak())
        elements.append(Paragraph("Audit Flags & Review Items", heading_style))
        for audit in audits:
            bid_id = audit.get("bidder_id", "unknown")
            flagged = audit.get("flagged_items", [])
            if flagged:
                elements.append(Paragraph(f"<b>Bidder: {bid_id}</b> — {len(flagged)} flagged items", body_style))
                for item in flagged:
                    elements.append(Paragraph(
                        f"  • <b>{item.get('criterion_name', 'N/A')}</b>: {item.get('review_note', '')}",
                        body_style,
                    ))
                elements.append(Spacer(1, 10))

    doc.build(elements)
    logger.info("PDF report generated: %s", pdf_path)


# ---------------------------------------------------------------------------
# GET /dashboard/{tender_id} — All data for React dashboard
# ---------------------------------------------------------------------------
@app.get("/dashboard/{tender_id}")
async def get_dashboard_data(tender_id: str):
    """Return all data needed for the React dashboard."""
    tender_dir = TENDERS_DIR / tender_id

    if not tender_dir.exists():
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")

    criteria = load_json(tender_dir / "criteria.json")
    evaluations_data = load_json(tender_dir / "evaluations.json")
    audits_data = load_json(tender_dir / "audits.json")
    report_data = load_json(tender_dir / "report.json")

    # Load all bidder data
    bidders = []
    bids_dir = BIDS_DIR / tender_id
    if bids_dir.exists():
        for bidder_dir in bids_dir.iterdir():
            if bidder_dir.is_dir():
                bd = load_json(bidder_dir / "bidder_data.json")
                if bd:
                    bidders.append(bd)

    return {
        "tender_id": tender_id,
        "criteria": criteria,
        "bidders": bidders,
        "evaluations": evaluations_data.get("evaluations", []) if evaluations_data else [],
        "audits": audits_data.get("audits", []) if audits_data else [],
        "report": report_data,
    }


# ---------------------------------------------------------------------------
# GET /tenders — List all tenders (utility endpoint)
# ---------------------------------------------------------------------------
@app.get("/tenders")
async def list_tenders():
    """List all uploaded tenders."""
    tenders = []
    if TENDERS_DIR.exists():
        for td in TENDERS_DIR.iterdir():
            if td.is_dir():
                criteria = load_json(td / "criteria.json")
                tenders.append({
                    "tender_id": td.name,
                    "filename": criteria.get("filename", "Unknown") if criteria else "Unknown",
                    "has_criteria": criteria is not None,
                    "has_evaluations": (td / "evaluations.json").exists(),
                    "has_audits": (td / "audits.json").exists(),
                    "has_report": (td / "report.json").exists(),
                })
    return {"tenders": tenders}


# ---------------------------------------------------------------------------
# POST /review/{tender_id}/{bidder_id} — Submit HITL review decision
# ---------------------------------------------------------------------------
@app.post("/review/{tender_id}/{bidder_id}")
async def submit_review(tender_id: str, bidder_id: str, decision: dict):
    """Submit a human-in-the-loop review decision for flagged items."""
    bid_dir = BIDS_DIR / tender_id / bidder_id

    if not bid_dir.exists():
        raise HTTPException(status_code=404, detail="Bidder not found")

    # Save review decision
    review_path = bid_dir / "review_decision.json"
    decision["reviewed_at"] = datetime.utcnow().isoformat()
    decision["bidder_id"] = bidder_id
    decision["tender_id"] = tender_id
    save_json(review_path, decision)

    logger.info("Review decision saved for bidder %s: %s", bidder_id, decision.get("action"))

    return {"status": "ok", "message": f"Review saved for bidder {bidder_id}"}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """Return service health status with version and uptime information."""
    now = datetime.utcnow()
    uptime_seconds = int((now - SERVER_START_TIME).total_seconds())
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "uptime": f"{hours}h {minutes}m {seconds}s",
        "uptime_seconds": uptime_seconds,
        "timestamp": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /stats — System-wide statistics
# ---------------------------------------------------------------------------
@app.get("/stats")
async def get_stats():
    """Return system-wide statistics: total tenders, bids, evaluations, and audits."""
    total_tenders = 0
    total_bids = 0
    total_evaluated = 0
    total_audited = 0
    total_reports = 0

    if TENDERS_DIR.exists():
        for td in TENDERS_DIR.iterdir():
            if td.is_dir():
                total_tenders += 1
                if (td / "evaluations.json").exists():
                    total_evaluated += 1
                if (td / "audits.json").exists():
                    total_audited += 1
                if (td / "report.json").exists():
                    total_reports += 1

    if BIDS_DIR.exists():
        for tender_bid_dir in BIDS_DIR.iterdir():
            if tender_bid_dir.is_dir():
                for bidder_dir in tender_bid_dir.iterdir():
                    if bidder_dir.is_dir():
                        total_bids += 1

    return {
        "total_tenders": total_tenders,
        "total_bids": total_bids,
        "total_evaluated": total_evaluated,
        "total_audited": total_audited,
        "total_reports_generated": total_reports,
        "server_version": APP_VERSION,
        "server_uptime_seconds": int((datetime.utcnow() - SERVER_START_TIME).total_seconds()),
    }
