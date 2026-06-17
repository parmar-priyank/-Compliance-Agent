# QC Compliance Checker — ADS Solar

Automated document verification tool using FastAPI + Groq AI (OCR + LLM).

## Setup

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install system dependency for PDF rendering
# macOS:
brew install poppler
# Ubuntu/Debian:
sudo apt-get install poppler-utils

# 3. Set your Groq API key (or enter it in the UI)
export GROQ_API_KEY=gsk_your_key_here

# 4. Run the app
uvicorn main:app --reload --port 8000
```

Then open http://localhost:8000

## How it works

1. **Upload Signed Agreement** (main PDF) — This is the reference document
2. **Select a checklist item** from the sidebar (e.g. "Signed Agreement", "Deposit", etc.)
3. **Upload the supporting document** (PDF, JPG, JPEG, PNG)
4. Click **Run Check** — Groq OCR extracts text, then the LLM checks if it matches the agreement
5. Results show **Yes / No / N/A** with a short remark
6. **Download Excel** generates the full QC checklist report

## Checklist Items

| # | Item | What to upload |
|---|------|---------------|
| 1 | Signed Agreement | Signed PDF from customer |
| 2 | Deposit | Deposit receipt/screenshot |
| 3 | Meter Photo/Switchboard | Photo of meter box |
| 4 | Phase and Upgrade | Phase approval doc/photo |
| 5 | Roof Pic/House Pic | Photo of roof/house |
| 6 | Storey and Roof Type | Photo showing storey/roof |
| 7 | Electricity Bill/NMI | Electricity bill PDF |
| 8 | Rate Notice | Council rates notice |
| 9 | Meter Approval | Meter approval document |
| 10 | Roof Layout Approved | Layout approval image |
| ... | ... | ... |

## Tech Stack
- **FastAPI** — Backend API
- **Groq** — OCR (Llama 4 Scout vision) + LLM matching (Llama 3.3 70B)
- **openpyxl** — Excel report generation
- **pypdf** — PDF text extraction
- **Pillow / pdf2image** — Image processing

## Project Structure
```
qc_app/
├── main.py           # FastAPI app
├── requirements.txt
├── templates/
│   └── index.html    # Frontend UI
├── static/           # Static assets
└── uploads/          # Session uploads (auto-created)
```
