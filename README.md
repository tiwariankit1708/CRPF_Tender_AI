# CRPF Tender AI

An end-to-end multi-agent AI system that automates government procurement tender evaluation — from PDF ingestion to audit-ready reports.

## Architecture

Four specialised AI agents work in a sequential pipeline:
1. **Agent A (Criteria)** — Extracts eligibility criteria from tender PDFs
2. **Agent B (Parser)** — Extracts key facts from bidder documents
3. **Agent C (Evaluator)** — Evaluates bids against criteria with clear verdicts
4. **Agent D (Auditor)** — Flags low-confidence items for human review

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- [Poppler](https://github.com/ossamamehmood/Poppler-windows/releases) (for PDF processing)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (for text extraction)
- OpenAI API key

### Backend
```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your API key and paths

# Start server
uvicorn api.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload/tender` | POST | Upload tender PDF, extract criteria |
| `/upload/bid` | POST | Upload bidder PDF, extract data |
| `/evaluate/{tender_id}` | POST | Evaluate all bids for a tender |
| `/audit/{tender_id}` | GET | Audit evaluations, flag items |
| `/report/{tender_id}` | GET | Generate PDF report |
| `/dashboard/{tender_id}` | GET | Get all dashboard data |

## License
MIT
