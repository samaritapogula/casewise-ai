# CaseWise AI — Indian Civil Dispute Assistant (MVP)

**An explainable, cautious conversational prototype** for four everyday civil categories in India: property/rental, consumer refunds, unpaid salary/employment, and contract/payment disputes.

CaseWise AI is a **demonstration, not a lawyer**. It never guarantees outcomes, sets legal deadlines, or invents statutes. State-specific property and employment rules are intentionally not summarized as universal national law.

## Multilingual case-building workflow (November 2026 upgrade)

- **Text:** English, Hindi and Telugu are available using the language switcher. Gemini can suggest an English case narrative, dated events, explicitly mentioned proof, missing facts and a follow-up question. Every extracted detail is **unverified until the user reviews it**. Without Gemini, the app still runs in basic English guided mode; full multilingual understanding is not guaranteed.
- **Voice input:** The microphone uses the browser's SpeechRecognition / webkitSpeechRecognition implementation. Language tags are en-IN, hi-IN and te-IN. Browser compatibility and language availability vary; some browsers send microphone audio to their recognition service. Recognized text stays editable and must be sent deliberately. Voice recognition is not a separately hosted transcription service.
- **Where the user stands:** The app distinguishes reported facts from uncertain information. It offers cautious general options and official starting points, not eligibility determinations or predictions.
- **Documents:** The review form lets a user choose a factual request, proposed notice outline, complaint, reply, or application. Every PDF is clearly labelled as a **draft**, never a formal legal notice or filing. The PDF templates are English-only, require an English narrative, missing fields, and explicit review confirmation; any formal notice/reply should be reviewed by a lawyer.
- **Argument practice:** `/api/practice` challenges a user with a factual opposing-side question and offers evidence-focused feedback. It never estimates odds of winning or fabricates precedents. In offline mode it uses a generic practice prompt.
- **Limits:** A Gemini key activates the language features but does not guarantee accuracy. Multilingual and voice quality have not been validated across all browsers or Indian dialects. The legal sources are curated navigation links rather than live authoritative conclusions. Do not enter sensitive identifying information during testing.

To try the enhanced interface after pulling the latest code on macOS:

```bash
cd ~/Desktop/casewise-ai
git pull origin main
bash scripts/setup_mac.sh
bash scripts/run_mac.sh
```

Use the language picker and microphone in the chat. After sharing a case, review the **Structured case file**, select a document type in the PDF review dialog, or try **Practise your argument**. Check browser microphone permissions if dictation is unavailable.

## What works

- React chat interface and free-text issue classification (or manual category choice)
- Fact capture, editable case details, missing-information prompts and next-step guidance
- Safe source links to India Code, NALSA, NCH, e-Jagriti and Chief Labour Commissioner
- A downloadable **PDF factual request for resolution**, generated after user fact review and confirmation (not a formal legal notice)
- Safety alerts for urgent/criminal matters, with document generation blocked in those cases
- Optional Gemini-assisted **multilingual intake, structured case extraction and factual argument practice** with a configurable provider and model
- Fully functional, deterministic **guided-demo** mode without any API key
- No database / no intentional server-side case persistence

## Run locally

Requirements: **Python 3.10+** and **Node 18+**.

Open two terminals from the repository root.

**Terminal 1 — Backend**

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — React frontend**

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The Vite development proxy forwards `/api` to the FastAPI backend.

### Optional: real LLM-assisted follow-ups

In the backend shell, **before starting Uvicorn**, set an API key using your own free-tier Gemini account:

```bash
# macOS / Linux
export GEMINI_API_KEY='your-key-here'
export GEMINI_MODEL='gemini-2.5-flash'

# Windows PowerShell
$env:GEMINI_API_KEY='your-key-here'
$env:GEMINI_MODEL='gemini-2.5-flash'
```

No key is required for the guided demo. With a key, user conversation snippets are sent to the external Gemini API. The language model proposes **unverified structured case facts, multilingual intake wording, optional translations, and argument practice**; fixed rules retain source-linked next steps and safety conditions. Never treat model text as verified law. If the API fails, the app falls back gracefully. **Do not put the API key in React/Vite or commit it to GitHub.**

For a separately hosted frontend, set `VITE_API_BASE_URL=https://your-backend-host` in `frontend/.env.local` before building. In the backend configure `CASEWISE_ALLOWED_ORIGINS=https://your-frontend-host`. Hosting the frontend on Vercel does **not** automatically host FastAPI; deploy both services or use a Python-capable host for the backend.

## Reviewed PDF drafting (new)

Once the chatbot has collected case information, click **Review & generate PDF** in Case overview. A review dialog displays a cleaned, editable narrative sourced from the user's own statements (not the AI's questions), plus the six case fields and optional sender details. Confirm or correct the information and tick the explicit review checkbox before generating the PDF.

The server also enforces confirmation and requires the **other party, city/state, relevant event date and requested resolution** (enter "Not known" when a date genuinely cannot be established rather than guessing). The amount and evidence are optional. A draft is still preliminary: it should be checked before sending and is not a formal legal notice.

The `POST /api/draft` endpoint now requires `"confirmed": true` and the required `profile` fields; older direct calls without confirmation return HTTP 422. The PDF generator no longer reproduces conversational requests such as "What should I do?". Manually edited narrative text is supplied as `profile.facts_narrative`.

`outputs/reviewed_draft_test_runs.json` contains **four raw end-to-end sample runs** (one per civil category), including the extracted PDF text. These use fictional inputs and demonstrate program behavior, not legal accuracy.

## Test the actual backend

```bash
python -m pytest -q
```

The `tests/` folder tests classifications, no invented facts or statutes, urgent-case blocking, source links and generated PDF. `outputs/raw_test_runs.json` holds **nine unedited engine run results** on synthetic inputs; these are samples rather than evidence of legal accuracy.

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Service / LLM mode |
| `/api/sources` | GET | Curated references |
| `/api/analyze` | POST | Analysis and conversation follow-up |
| `/api/draft` | POST | Reviewed PDF draft; set `document_type` and `confirmed=true` |
| `/api/practice` | POST | Civil-dispute argument rehearsal and feedback |

Example:

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"The seller denied my refund of Rs 3000 for a damaged product."}],"category":"auto","profile":{}}'
```

## Architecture / hybrid choice

Reuses the **React + FastAPI architecture and explanation-oriented interaction design** explored in the earlier joint case-outcome-prediction project. It is a new implementation focused on intake and concrete user actions. The old ILDC/XGBoost `ACCEPTED/REJECTED` model, SHAP predictions and criminal-case argument rules are **not reused** because they have not been validated for these civil-advice scenarios. Optional future extensions could add verified precedents with provenance after evaluation.

## Source-verification approach

`backend/knowledge.py` contains a **small, reviewed whitelist** of government/official links as of **2026-11-08**. Users can open each original source. The product does not claim that the URLs were freshly checked on every request, does not invent section citations, and avoids definitive advice about eligibility, jurisdiction or limitation periods. If facts indicate urgent litigation/safety issues or criminal cases, it recommends professional help. Source links alone do not prove the legal advice is correct.

## Known limitations

1. Guided mode uses lightweight keyword classification and generic fact-finding, **not** a complete legal reasoner. It can misclassify mixed or ambiguous issues.
2. Optional Gemini follow-ups improve natural conversation but cannot guarantee fully safe or accurate output; no unverified legal citations are promoted as authorities.
3. Location/date/amount detection is incomplete; users should review the case details panel, and dates or missing information may remain unknown.
4. India-specific legal remedies and deadlines depend on jurisdiction, case facts, and changes to law. A lawyer must verify before filing.
5. PDF drafts can contain user allegations; they are preliminary factual letters, not legal notices ready for court filing. The frontend currently offers PDF download rather than a WYSIWYG editor.
6. No persistent chat history, uploaded document analysis, authentication, voice input, Hindi translation, or formal case prediction.

## Assignment integrity

The earlier legal-outcome predictor was a joint project and is referenced for architecture only. This new MVP is a separate implementation with explicit limitations and synthetic tests. AI assistants were used to scaffold code and content; the developer must independently review and be ready to explain each component. One common AI failure to document: confidently fabricated or overgeneralized legal provisions. This implementation prevents citation generation in the fallback and restricts the LLM to intake wording, but still requires human review.

## Confidentiality

This repo contains only synthetic test examples and published official URLs. **Do not** commit real case documents, personal details, or private API keys.
