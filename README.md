# CaseWise AI — Indian Civil Dispute Assistant (MVP)

**An explainable, cautious conversational prototype** for four everyday civil categories in India: property/rental, consumer refunds, unpaid salary/employment, and contract/payment disputes.

CaseWise AI is a **demonstration, not a lawyer**. It never guarantees outcomes, sets legal deadlines, or invents statutes. State-specific property and employment rules are intentionally not summarized as universal national law.

## English case-building and voice typing

- **Language:** CaseWise AI operates in English. The language selector and experimental translations have been removed because voice transcription was unreliable in testing.
- **Text:** Type your civil-dispute story directly in English. Gemini may propose a case narrative, timeline, proof checklist, missing details and a follow-up question. Review all AI-extracted facts before relying on them.
- **Voice:** Dictation is set to English (India, `en-IN`) using the browser's SpeechRecognition / webkitSpeechRecognition API. Click the microphone, speak naturally, then press **Stop recording**. Short pauses should not intentionally end dictation; the client attempts to reconnect if a browser recognition session ends. Browser limits may still interrupt recording.
- **Transcription review:** Recognition output appears in a separate editable review panel. You must select **Add to message for review**, then manually press **Send**. Audio may be processed by the browser's speech provider; this application does not intentionally store audio.
- **Existing legal support:** Structured case summary, fact checking, source-linked general steps, reviewed PDF draft types, and argument practice remain available. The product is not a substitute for a lawyer, and sources are starting points rather than claims of verified entitlement.
- **Testing:** `cd frontend && npm test` runs continuous-dictation checks. `python -m pytest -q` covers backend behavior. These tests do not establish speech-recognition accuracy or legal correctness.

To use the updated app on macOS, stop the current process with Control+C and run:

```bash
cd ~/Desktop/casewise-ai
git pull --ff-only origin main
bash scripts/run_mac.sh
```

Open http://localhost:5173, try an English test case, and review the voice transcription before sending.

## What works

- React chat interface and free-text issue classification (or manual category choice)
- Fact capture, editable case details, missing-information prompts and next-step guidance
- Safe source links to India Code, NALSA, NCH, e-Jagriti and Chief Labour Commissioner
- A downloadable **PDF factual request for resolution**, generated after user fact review and confirmation (not a formal legal notice)
- Safety alerts for urgent/criminal matters, with document generation blocked in those cases
- Optional Gemini-assisted **English intake, structured case extraction and factual argument practice** with a configurable provider and model
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

No key is required for the guided demo. With a key, user conversation snippets are sent to the external Gemini API. The language model proposes **unverified structured case facts, English intake wording, and argument practice**; fixed rules retain source-linked next steps and safety conditions. Never treat model text as verified law. If the API fails, the app falls back gracefully. **Do not put the API key in React/Vite or commit it to GitHub.**

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
6. No persistent chat history, uploaded document analysis, authentication, speech audio storage, or formal case prediction. Speech recognition depends on browser availability and may not capture spoken English reliably in every accent or device.

## Assignment integrity

The earlier legal-outcome predictor was a joint project and is referenced for architecture only. This new MVP is a separate implementation with explicit limitations and synthetic tests. AI assistants were used to scaffold code and content; the developer must independently review and be ready to explain each component. One common AI failure to document: confidently fabricated or overgeneralized legal provisions. This implementation prevents citation generation in the fallback and restricts the LLM to intake wording, but still requires human review.

## Confidentiality

This repo contains only synthetic test examples and published official URLs. **Do not** commit real case documents, personal details, or private API keys.

## English voice-input test checklist

1. Open the app, click the microphone, and speak a **fictional English** civil-dispute description.
2. Pause between sentences, then press **Stop recording** and review the accumulated text.
3. Edit the transcript as needed; choose **Add to message for review** and manually select **Send**.
4. Verify Gemini responds in English. Check the structured case file, document review and argument practice.
5. Also test microphone permission denied or speech service unavailable. Text entry must continue working.

Browser speech recognition can rely on an external browser speech provider and may have availability/time limits. See the [SpeechRecognition API](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition).


## Phase 2 — Intelligent Case Builder

**Approved features A, B, C, D, E, F, G, H and J** are implemented in the existing React/FastAPI app. No document upload (Feature I) is included.

- **Classification:** Detect the civil category and a narrower subtype; select the category manually or correct the subtype in Review & export.
- **Facts and provenance:** Extract reported parties, location, amount, important dates, event, role and requested remedy. Case fields are labelled reported, user-edited or missing. Original conversation references are retained when deterministically identifiable. Gemini suggestions are never described as verified facts.
- **Timeline:** Order explicitly dated reported events, preserve uncertain dates as unknown/relative, and allow user edits.
- **Evidence:** List mentioned supporting material, distinguish reported availability from actual verification, and allow user edits without uploading files.
- **Follow-ups:** Ask the next high-priority missing question. The browser tracks asked fields to avoid repeatedly asking the same question.
- **Review:** Edit the narrative and case values; the review checkbox resets after changes.
- **Contradictions:** Flag potentially differing monetary amounts, dates and obvious payment/refund wording for clarification; flags are not legal findings.
- **Completeness:** An eight-check information-collection indicator; it does not measure legal strength, likelihood of success or filing readiness.
- **Export:** Download reviewed case data as PDF or JSON. Both contain review and verification limitations. The API requires an explicitly reviewed, non-empty case narrative.

**New endpoints:** \`POST /api/case-file\` rebuilds the current case from messages, edits and reviewed fields. \`POST /api/case-export\` requires \`reviewed=true\` and \`story_override\`; set \`export_format=pdf\` or \`export_format=json\`. The original \`/api/analyze\`, \`/api/draft\` and \`/api/practice\` remain available.

Case data is held in the current React browser session and reconstructed per request; no server-side database is added. Be cautious with identifying details because configured Gemini calls can send the conversation to an external model. Browser speech recognition can also use an external speech provider.

### Test Phase 2 on a Mac

\`\`\`bash
cd ~/Desktop/casewise-ai
git pull --ff-only origin main
bash scripts/run_mac.sh
\`\`\`

Type a **fictional** dispute (for example a rental deposit not returned), answer the follow-up questions, then open **Timeline**, **Evidence**, and **Review & export**. Edit one fact, save, confirm the narrative, and download a case-file PDF and JSON. Try different amounts to exercise discrepancy flags. Avoid real personal or legal-case data in the demonstration.

Automated checks: \`python -m pytest -q\`, then \`cd frontend && npm test && npm run build\`. These are functional tests, **not** validation of legal accuracy. Human legal review remains necessary.



## Phase 3 — Legal Position & Personalized Action Plan

The **Action plan** tab adds all eight approved features to the Phase 2 case-file workflow:

- **A — Legal position:** A cautious category-specific explanation and questions to check, not a legal decision or prediction.
- **B — Official laws and sources:** A fixed whitelist of official Indian legal/statute and government-service URLs, manually reviewed on **9 November 2026**. Their inclusion does **not** prove a statute applies to the user's facts, and they are not revalidated live on each request.
- **C — Personalized steps:** Ordered tasks use the current Phase 2 case category, missing facts, reported evidence and possible urgency.
- **D — Supporting information and limitations:** Shows **reported** supporting material, conflicting statements and evidence gaps. The heading deliberately does not call unverified evidence a legal strength.
- **E — Appropriate channels:** Offers possible dispute-resolution or government-service starting points, subject to eligibility and jurisdiction checks (not an instruction to file).
- **F — Urgency and lawyer escalation:** Time-sensitive and criminal issues are steered toward qualified help; normal filing-oriented task suggestions are suppressed in those cases.
- **G — PDF action plan:** Requires explicit user acknowledgement and includes current checklist status, source links and all legal disclaimers.
- **H — Interactive checklist:** User-marked progress during the current session. Marking a task complete does not mean legal compliance.

**Supported issue categories:** Property/rental, consumer/refund, employment/pay and contract/payment. Civil cases outside these categories are deliberately routed to human triage. For property, the Uttar Pradesh tenancy statute appears only when the reported location suggests UP, and the app still requires a local lawyer to check scope and applicability.

**New endpoints:**
- \`POST /api/legal-plan\` computes guidance from the current Phase 2 case, user edits and optional \`completed_actions\` mapping.
- \`POST /api/legal-plan/export\` produces an informational PDF when \`plan_reviewed=true\`.

The backend's legal-source registry is deterministic (\`backend/legal_plan.py\`); Gemini cannot supply statute names, URLs, court jurisdictions, statutory deadlines or legal entitlements through that registry. The core \`/api/analyze\` now also includes \`legal_plan\` in its response without changing the existing \`case_file\`, \`/api/draft\` or \`/api/practice\` APIs.

For local testing:
\`\`\`bash
cd ~/Desktop/casewise-ai
git pull --ff-only origin main
bash scripts/run_mac.sh
\`\`\`
Enter a **fictional** civil story, inspect the **Action plan** tab, mark one checklist task, review the acknowledgement and download the PDF. Also inspect the **Review & export** case file, document drafting and argument-practice features.

\`\`\`bash
python -m pytest -q
cd frontend && npm test && npm run build
\`\`\`

**Legal safety:** This app does not verify that a law is applicable, that a user qualifies for a particular remedy or forum, or that a document is ready for filing. It must never invent a limitation period, venue or guaranteed outcome. Official government links can change, and live legal advice, deadlines and case-sensitive procedure require a qualified professional.


## Timeline quality and explicit document choices (November 2026)

**Timeline:** Phase 2 no longer treats every user sentence as an event. It retains user-reported *actions and incidents* (payments, move-outs, complaints, refusals, missed payments and similar events) but excludes mere evidence lists, requests for relief, and short answers giving names or other field values. When all reported event dates are precise, entries are sorted chronologically. If some dates are unknown, their original conversation order is preserved; no date is invented. The user can still edit, add or remove events before PDF/JSON export. When no genuine events are identified, the timeline remains empty instead of inventing AI events.

**Document choices:** The Overview and Action plan tabs now display five direct draft choices: **Resolution request**, **Legal notice outline**, **Complaint draft**, **Reply draft**, and **Application for assistance**. Choosing one opens the pre-existing fact-review dialog with that type selected. The recipient may be edited separately; complaint and application drafts use a neutral unverified authority placeholder rather than assuming the counterparty is the recipient. These are *drafts*, never official submissions. Urgent/criminal intake and reviewed-facts constraints remain enforced by the backend.

**Test:** Enter the fictional ₹30,000 rental-deposit example, answer the other-party question with a name, then check that the timeline includes payment of deposit, move-out date and non-return—not the name, requested outcome or evidence list. Download the reviewed Case File PDF/JSON; then choose a document type and review its recipient and text before generating.


## Purpose-specific document generator (November 2026)

The five **Overview** and **Action plan** document choices generate distinct, downloadable documents rather than renaming one general-purpose letter. Each choice opens the review form and uses the same reviewed data to generate a **text preview** or a PDF:

| Choice | Actual generated sections |
| --- | --- |
| Resolution request | Purpose, factual account, key details, earlier attempts, requested resolution and written response request |
| Legal notice outline | Parties, alleged facts, reported materials, earlier communications, proposed remedy and questions for qualified lawyer review |
| Complaint draft | Grievance, reported facts, evidence, earlier complaint steps, requested action from the receiving office and procedural checks |
| Reply draft | Actual incoming communication, specific disputed points, factual response, supporting materials, clarifications and legal-review warnings |
| Application for assistance | Type of help requested, reason, background, evidence, previous steps and assistance requested |

Relevant additional fields appear in the review form. If important information (such as the original notice being answered) is missing, the document clearly displays a placeholder rather than inventing an allegation, law, or deadline. Complaints and applications address the reviewed recipient/office or show an unverified-office placeholder. Name and contact remain optional.

**Preview API:** \`POST /api/draft-preview\` accepts the same reviewed payload as \`POST /api/draft\` and returns the exact draft body as text. Both routes require explicit user review, enforce the urgent/criminal case block and never send or file a document automatically. Each downloadable PDF contains the review warnings.

To check: run CaseWise locally, describe a **fictional** dispute, open **Overview**, choose each document card, enter relevant extra details, check the acknowledgment, click **Generate text preview**, and then **Download PDF**. Compare the sections across the five documents. For a reply, enter the actual received communication or verify that the draft shows a visible missing-information placeholder.

Automated checks: \`python -m pytest -q\` (backend) and \`cd frontend && npm test && npm run build\` (frontend).


## Adaptive case guidance and contextual follow-ups (November 2026)

The case builder is **case-driven**, not programmed for the example rental deposit, amount or landlord. All four supported civil categories use the same algorithms. Subject-specific *question wording and evidence focus* are configured in \`backend/case_policy.json\`; adding a supported subtype requires extending that configuration rather than inserting if/else branches for a specific party or incident.

### How it works
1. **Essential facts:** when the other party, dispute or desired result are missing, only preservation and fact-collection tasks are shown. The chatbot asks one question at a time.
2. **Developing record:** when core facts exist but amount, date, location or evidence status need clarification, the plan focuses on these gaps and existing materials.
3. **Case-specific plan:** when key information has been addressed, tasks reference the **actual reported** other party, desired outcome, disputed amount, date and evidence descriptions. Facts remain unverified.
4. **Optional issue-specific questions:** after the basic intake, the chatbot can ask prompts configured for the issue's category/subtype. They can also be answered under **Review & export**, and affect the next plan refresh. **8/8 is only a basic information score, not completion of case investigation.**
5. **Unknown facts are valid:** explicitly saying "not known" does not invent a date or turn an unknown into a positive fact; it allows cautious planning while keeping the gap visible.
6. **Evidence:** a bank-transfer receipt is one evidence item, not two because matching aliases overlap. Separate records remain separate. User-entered evidence edits are preserved and documents are not verified.
7. **Timeline:** an ongoing nonpayment or non-return is distinguished from a dated refusal; neither is silently erased.
8. **Documents:** the five draft options remain available, with contextual suitability labels. No official forum, outcome, entitlement or deadline is invented; existing reviewed-draft and urgent-case safeguards remain.

### Source and AI safety
The planner is deterministic and uses reviewed case data. Only the curated official-source whitelist can supply statute names/links; neither user input nor Gemini can create legal citations or invent a court route. The model can assist extraction and conversational clarity, but no generated legal opinion is asserted. Exports reproduce what the user reported, including unresolved questions and disclaimer text.

### Developer verification

\`\`\`bash
python -m pytest -q
cd frontend && npm test && npm run build
\`\`\`

Use **fresh case examples from each supported category** and compare the Action plan tab after each new answer. Check that the same case reference is retained, that the plan changes stages, that reported evidence is not duplicated, and that both case and action-plan PDFs reflect the latest facts. As before, cases live only in the current browser session.


## Phase 4 — document and argument intelligence

The existing five draft types (resolution request, legal notice outline, complaint, reply, and assistance application) now share a **document-specific readiness checker**. In the document review dialog, the app shows which required details are present, what is still missing, warnings about legal review, and a trace of reported facts back to chat messages and any user-mentioned evidence. Reported source references do **not** verify authenticity or legal sufficiency.

**Workflow:** describe the dispute → review the structured Case File → choose a document → complete purpose-specific questions → confirm the factual account → generate text preview → optionally edit the whole draft → confirm again → download the reviewed PDF. If the draft text was edited, the PDF carries an additional mandatory disclaimer; edits are not independently legally validated. The preview does not send or file any communication.

The **Prepare your factual argument** panel creates a neutral opening, reported key points, possible challenges, questions needing clarification, and closing wording directly from the case file. The existing practice chatbot remains available. No guaranteed outcomes, invented citations, unverified documents, or formal legal filings are produced. Urgent/criminal triggers retain the existing draft and argument restrictions. English-only and no default server-side case persistence continue to apply.

Phase 4 is an educational prototype; legal deadlines, current law, recipient, venue, procedure, evidence and eligibility must be confirmed independently by qualified professionals or official sources before real-world use.


## Public deployment: Render (single site with React + FastAPI)

The Dockerfile builds the React/Vite frontend and serves it with the FastAPI API from the same origin. The backend.serve:app production entrypoint preserves all /api routes and mounts the compiled website last. The Render Blueprint is render.yaml; its health check is /api/health. A GitHub Actions smoke workflow checks the built image.

### Publish

1. Visit https://dashboard.render.com/ and connect the GitHub account with access to samaritapogula/casewise-ai.
2. Choose New > Blueprint and choose this repository on its main branch. Approve the render.yaml configuration to create the web service.
3. Wait for a Live deployment, open its public HTTPS onrender.com URL, then visit /api/health (look for status: ok).
4. Test the chat, Timeline, Evidence, review/export, legal plan, document readiness, PDF download and argument preparation.
5. Optional: set GEMINI_API_KEY in the Render service's private Environment settings and redeploy. With no key, guided-demo mode still works. Never put keys in VITE_* environment variables or Git.

The Blueprint uses the Render free web service plan for a demonstration, which can spin down when idle and has reliability and usage limits. Do not use the public prototype for real or sensitive legal cases without appropriate privacy, security, legal and operational reviews.

Local production check: docker build -t casewise-ai . ; docker run --rm -p 10000:10000 casewise-ai . Open http://localhost:10000/ and http://localhost:10000/api/health.

Ordinary local development remains available with bash scripts/run_mac.sh and http://localhost:5173/.