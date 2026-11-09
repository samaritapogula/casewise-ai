# CaseWise AI

**Understand your legal situation. Organize your case. Take the next step with clarity.**

CaseWise AI is an India-focused civil-dispute guidance application that helps people turn an everyday problem into a structured case record, understand what information may matter, explore possible next steps, and prepare documents for review. It combines a conversational interface with rule-based case handling and optional Google Gemini assistance.

**Live application:** [casewise-ai.onrender.com](https://casewise-ai.onrender.com)  
**Source code:** [github.com/samaritapogula/casewise-ai](https://github.com/samaritapogula/casewise-ai)

> **Important:** CaseWise AI provides general legal information and drafting assistance, **not legal advice, representation, an official filing, or a prediction of case success**. Facts, evidence, legal applicability, jurisdiction and deadlines require independent verification.

## What CaseWise AI does

| Capability | Description |
| --- | --- |
| **Conversational case intake** | Describe a dispute in plain English, answer follow-up questions, and correct the information collected. |
| **Text and voice input** | Type or dictate in English. Browser-based speech recognition produces an editable transcript that must be reviewed before sending. |
| **Case classification** | Identify the likely civil-dispute category and subtype, with manual corrections available. |
| **Structured case file** | Organize reported parties, events, dates, amounts, requested outcomes and other details. Export the reviewed case file as PDF or JSON. |
| **Timeline and evidence tracker** | Organize reported incidents and supporting materials, edit entries, and distinguish user-reported evidence from independent verification. |
| **Missing-information checks** | Ask context-aware questions, flag possible inconsistencies, and show an information-coverage indicator. |
| **Legal information and action plan** | Present cautious explanations, relevant official starting points, case-dependent next steps, possible channels and an interactive checklist. Export the acknowledged action plan as PDF. |
| **Document preparation** | Choose a document type, review required details and source references, preview or edit the full draft, and download a reviewed PDF. |
| **Argument preparation** | Generate a factual speaking outline, anticipate possible counterquestions and practice explaining your position. |

### Civil disputes covered

- **Property and rental:** rental deposits, tenancy-related disagreements and property arrangements.
- **Consumer complaints and refunds:** defective goods, service issues, seller responses and refund disputes.
- **Employment and unpaid salary:** unpaid wages, employer-related payment problems and employment disagreements.
- **Contracts and payments:** unpaid invoices, client payments, agreements and contractual disputes.

The application may identify issues outside these categories, but does not pretend to provide comprehensive guidance for every type of case.

## How it works

1. **Describe the situation.** Share what happened using text or reviewed voice transcription.
2. **Build the case.** CaseWise AI identifies reported facts and asks targeted questions about missing details.
3. **Review the record.** Check the overview, timeline, evidence list and editable case summary. Unknown facts can remain unknown; they are not silently guessed.
4. **Explore next steps.** Review an information-based action plan, possible official resources, evidence gaps and any reasons to consult a lawyer.
5. **Prepare a document.** Select the appropriate draft, supply purpose-specific details, review the preview and edit it before exporting.
6. **Export or practise.** Download case records and action plans, or prepare a factual argument.

An **8/8 information score** means the basic intake fields have been addressed. It does **not** mean the evidence is verified, the case is strong, or a legal filing is ready.

## Documents you can prepare

| Document | Intended use |
| --- | --- |
| **Resolution request** | Ask the other party to explain or resolve the reported problem. |
| **Legal notice outline** | Organize points for a proposed notice that requires qualified legal review. |
| **Complaint draft** | Set out a grievance and requested action for a recipient or organization whose jurisdiction must be confirmed. |
| **Reply draft** | Prepare a factual response to an actual communication or allegation, using the received text and disputed points. |
| **Application for assistance** | Explain the background and the help sought from a relevant institution. |

Each document has a purpose-specific information check. The review screen distinguishes provided details, missing fields, user-reported source references and warnings. The complete text can be edited before PDF export. **No draft is automatically sent, filed or certified as legally valid.** Notices, formal replies and complaints should be checked by a qualified professional.

## Technology and approach

CaseWise AI uses a **hybrid architecture**:

- **React + Vite:** conversation interface, case review, document workflow and in-browser state.
- **Python + FastAPI:** structured case processing, safety rules, legal-information routing and document APIs.
- **Google Gemini (optional):** natural-language assistance for intake, follow-up wording and case understanding.
- **Rule-based case logic:** case-specific questions, validation, evidence tracking, action-plan construction and document requirements. The logic uses category/subtype configuration rather than fixed example stories.
- **ReportLab:** downloadable PDF case records, action plans and reviewed document drafts.
- **Browser SpeechRecognition API:** English voice dictation with manual transcript review.
- **Docker + Render:** one hosted service serving the React frontend and FastAPI backend under the same website.

The case is reconstructed from the current conversation and user corrections. Gemini-generated suggestions are **not treated as verified facts or legal authorities**. Official links come from a maintained source list rather than model-invented citations.

### Project layout

```text
casewise-ai/
├── frontend/          React interface, voice input and document review
├── backend/           FastAPI, case processing, legal plan and PDF generation
├── tests/             Backend functional and safety tests
├── scripts/           Local setup and startup scripts
├── outputs/           Synthetic test artifacts
├── Dockerfile         Combined production application
├── render.yaml        Render deployment configuration
└── requirements.txt   Python dependencies
```

## Run locally

**Requirements:** Python 3.10+, Node.js 18+ and npm.

### macOS

```bash
git clone https://github.com/samaritapogula/casewise-ai.git
cd casewise-ai
bash scripts/setup_mac.sh
bash scripts/run_mac.sh
```

Open **http://localhost:5173**. The backend runs at **http://localhost:8000**.

The setup script creates a private `.env` file. Leaving `GEMINI_API_KEY` empty enables the built-in guided mode. To enable Gemini-assisted responses, edit **your local** `.env` file:

```dotenv
GEMINI_API_KEY=your_private_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Restart the app after changing the key. Never commit `.env` or expose the key in frontend variables.

### Manual setup (Windows / Linux / macOS)

Start the backend in a Python virtual environment:

```bash
python -m venv .venv
# Activate the environment for your operating system.
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

The development frontend forwards `/api` requests to the Python backend. For production, the provided Docker setup serves both on the same origin.

## Deployment

The public application is hosted at **[https://casewise-ai.onrender.com](https://casewise-ai.onrender.com)**.

The repository includes a `render.yaml` Blueprint and a multi-stage `Dockerfile`. Render builds the React frontend, starts the FastAPI service and checks `/api/health`.

To deploy a new instance:

1. In [Render](https://dashboard.render.com/), create a **Blueprint** from this GitHub repository's `main` branch.
2. Review the `render.yaml` service settings and deploy.
3. If you want Gemini assistance, configure `GEMINI_API_KEY` in **Render → Environment**, not in GitHub or client-side code.
4. Confirm the health endpoint responds, then test chat, case-file review, exports and document generation.

The free hosting plan can sleep when idle. Production deployment requires additional operational, privacy and security review before handling real legal matters.

## API overview

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Backend status and Gemini configuration flag |
| GET | `/api/sources` | Curated official-information links |
| POST | `/api/analyze` | Conversation and case analysis |
| POST | `/api/case-file` | Rebuild the structured case record |
| POST | `/api/case-export` | Export a reviewed case record as PDF or JSON |
| POST | `/api/legal-plan` | Build the case-dependent action plan |
| POST | `/api/legal-plan/export` | Export the acknowledged action plan PDF |
| POST | `/api/document-intelligence` | Document-specific questions, warnings and reported source trail |
| POST | `/api/draft-preview` | Return reviewed draft text for editing |
| POST | `/api/draft` | Generate a reviewed draft PDF |
| POST | `/api/argument-outline` | Prepare a factual speaking outline |
| POST | `/api/practice` | Practise an argument with feedback |

Example request:

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"My landlord has not returned my security deposit."}],"category":"auto","profile":{}}'
```

## Testing

Run the backend and frontend checks from the repository root:

```bash
python -m pytest -q
cd frontend
npm test
npm run build
```

The repository also includes a GitHub Actions deployment smoke test that builds the production container and checks that both the website and API are reachable. Tests use fictional case scenarios; **passing tests does not establish legal accuracy**.

## Safety, privacy and limitations

CaseWise AI is designed to be transparent about what it can and cannot know:

- **Reported, not verified:** The application does not authenticate documents, check whether evidence proves a claim, or hear the other party's account.
- **No fabricated legal certainty:** It does not guarantee results, determine court jurisdiction or deadlines, or claim a statute applies simply because it is linked.
- **Official sources are starting points:** Government resources can change. Applicability, eligibility, procedures and current law must be checked independently.
- **Human review is required:** Users must review extracted facts and acknowledge limitations before generating key exports. Urgent or potentially criminal matters are redirected toward qualified help, and relevant drafting or argument features are restricted.
- **English input only:** Multilingual dictation and responses are not supported. Browser speech recognition varies by device and may rely on an external speech service.
- **No document authenticity checks:** The evidence tracker records what the user says they have; it does not validate uploaded files or independently inspect supporting material.
- **No case database by default:** Case data stays in the current browser session and is processed per request rather than intentionally persisted on the server. With Gemini enabled, relevant conversation text is sent to the provider. Voice input may be processed by the browser's speech provider.
- **Not a legal filing service:** Drafts are preliminary and may omit details required by a specific court, agency or recipient.

**Use fictional or non-sensitive information when exploring the public site.** Do not submit private identity records, confidential legal documents or secrets.

---

**Developed by Samarita Pogula**  
CaseWise AI — Civil legal guidance, made clearer.
