"""CaseWise AI — FastAPI service. No user-case persistence by default."""
from __future__ import annotations

from io import BytesIO
import json
from typing import Any
import os
from xml.sax.saxutils import escape

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from .engine import analyze, make_draft
from .knowledge import SOURCES, VERIFIED_ON
from .llm import conversational_followup, is_configured
from .workflow import extract_case, practice_argument
from .case_builder import build_case
from .case_export import case_as_json, case_as_pdf
from .legal_plan import build_legal_plan
from .action_plan_export import as_pdf as action_plan_pdf

app = FastAPI(title="CaseWise AI", version="0.1.0", description="Cautious Indian civil-dispute intake demo")
origins = [origin.strip() for origin in os.getenv("CASEWISE_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


class Message(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=2000)


class Request(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=25)
    category: str = "auto"
    profile: dict[str, str] = Field(default_factory=dict)
    language: str = Field(default="en", pattern="^en$")  # English-only interface; old non-English client requests are rejected.
    document_type: str = Field(default="request", pattern="^(request|notice|complaint|reply|application)$")
    confirmed: bool = False  # Explicit user review, required for document drafting.
    case_id: str = Field(default="", max_length=48)
    case_overrides: dict[str, str] = Field(default_factory=dict)
    context_overrides: dict[str, str] = Field(default_factory=dict, max_length=12)
    timeline_edits: list[dict[str, Any]] | None = Field(default=None, max_length=14)
    evidence_edits: list[dict[str, Any]] | None = Field(default=None, max_length=18)
    asked_fields: list[str] = Field(default_factory=list, max_length=16)
    resolved_issues: list[str] = Field(default_factory=list, max_length=16)
    story_override: str = Field(default="", max_length=1400)
    reviewed: bool = False
    ai_suggestion: dict[str, Any] | None = None
    export_format: str = Field(default="pdf", pattern="^(pdf|json)$")
    completed_actions: dict[str, bool] = Field(default_factory=dict, max_length=16)
    plan_reviewed: bool = False


class PracticeRequest(Request):
    argument: str = Field(min_length=10, max_length=1600)


def as_dict(request: Request) -> list[dict]:
    return [message.model_dump() for message in request.messages]


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0", "llm_configured": is_configured(), "stored_cases": False}


@app.get("/api/sources")
def get_sources():
    return {"verified_on": VERIFIED_ON, "sources": list(SOURCES.values())}


def build_case_from_request(request: Request, ai: dict | None = None) -> dict:
    return build_case(
        as_dict(request), request.profile, request.category, ai,
        case_overrides=request.case_overrides,
        context_overrides=request.context_overrides,
        timeline_edits=request.timeline_edits,
        evidence_edits=request.evidence_edits,
        asked_fields=request.asked_fields,
        resolved_issues=request.resolved_issues,
        story_override=request.story_override,
        reviewed=request.reviewed,
        case_id=request.case_id,
    )


@app.post("/api/analyze")
def analyze_case(request: Request):
    try:
        preliminary = analyze(as_dict(request), request.profile, request.category)
        proposed = extract_case(as_dict(request)) if is_configured() and not preliminary["needs_lawyer"] else None
        chosen = request.category
        if chosen == "auto" and proposed and proposed.get("category") not in ("other", None):
            chosen = proposed["category"]
        data = analyze(as_dict(request), request.profile, chosen)
        data["summary"]["ai_extracted_case"] = proposed
        if proposed and proposed.get("risk_flag") in ("urgent", "criminal"):
            data["needs_lawyer"] = True
            data["next_steps"] = ["Consult a qualified local lawyer promptly and preserve relevant dates, documents and notices."]
            data["safety_flags"].insert(0, "Potential urgent/criminal issue flagged by AI; this prototype cannot assess it. Seek professional advice.")
        case = build_case(
            as_dict(request), request.profile, chosen, proposed,
            case_overrides=request.case_overrides,
            context_overrides=request.context_overrides,
            timeline_edits=request.timeline_edits,
            evidence_edits=request.evidence_edits,
            asked_fields=request.asked_fields,
            resolved_issues=request.resolved_issues,
            story_override=request.story_override,
            reviewed=request.reviewed,
            case_id=request.case_id,
        )
        data["case_file"] = case
        data["legal_plan"] = build_legal_plan(case, completed_actions=request.completed_actions)
        data["language"] = "en"
        if data["needs_lawyer"]:
            data["assistant_message"] = "This may be urgent or outside the civil-only prototype. Seek help from a qualified local lawyer promptly; do not rely on generated legal advice."
        else:
            data["assistant_message"] = case["next_question"]["text"]
            data["mode"] = "gemini-assisted" if proposed else "guided-demo"
        return data
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/case-file")
def get_case_file(request: Request):
    """Recompute a case from the current conversation and user corrections; no server state."""
    try:
        return build_case_from_request(request, request.ai_suggestion)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/case-export")
def export_case_file(request: Request):
    """Only export case files after explicit user review; never a legal filing."""
    if not request.reviewed or not request.story_override.strip():
        raise HTTPException(status_code=422, detail="Review and confirm a nonempty case narrative before export.")
    try:
        case = build_case_from_request(request, request.ai_suggestion)
        if request.export_format == "json":
            return Response(content=case_as_json(case), media_type="application/json",
                            headers={"Content-Disposition": 'attachment; filename="casewise-case-file.json"',
                                     "Cache-Control": "no-store"})
        return Response(content=case_as_pdf(case), media_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="casewise-case-file.pdf"',
                                 "Cache-Control": "no-store"})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/legal-plan")
def legal_plan(request: Request):
    """Build cautious legal information from the most recent Phase 2 facts and edits."""
    try:
        case = build_case_from_request(request, request.ai_suggestion)
        return build_legal_plan(case, completed_actions=request.completed_actions)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/legal-plan/export")
def export_legal_plan(request: Request):
    """Only create a downloadable action plan after explicit user acknowledgement."""
    if not request.plan_reviewed:
        raise HTTPException(status_code=422, detail="Please review the action plan disclaimer and confirm before downloading.")
    try:
        case = build_case_from_request(request, request.ai_suggestion)
        plan = build_legal_plan(case, completed_actions=request.completed_actions)
        return Response(content=action_plan_pdf(plan), media_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="casewise-action-plan.pdf"',
                                 "Cache-Control": "no-store"})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/practice")
def rehearse(request: PracticeRequest):
    try:
        data = analyze(as_dict(request), request.profile, request.category)
        return practice_argument(data, request.argument)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/draft-preview")
def preview_draft(request: Request):
    """Preview the same reviewed draft text that the PDF generator will use.

    Acknowledgement is required just as for exporting a PDF. This preview
    remains informational and does not send or file any communication.
    """
    try:
        draft_text = make_draft(
            as_dict(request), request.profile, request.category,
            confirmed=request.confirmed, document_type=request.document_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=json.dumps({
            "document_type": request.document_type,
            "draft": draft_text,
            "disclaimer": "Editable, user-reviewed text only. Never an automatic filing or legal opinion.",
        }),
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/draft")
def make_pdf(request: Request):
    try:
        draft_text = make_draft(as_dict(request), request.profile, request.category, confirmed=request.confirmed, document_type=request.document_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = BytesIO()
    doc = SimpleDocTemplate(result, pagesize=A4, topMargin=40, bottomMargin=42, leftMargin=50, rightMargin=50)
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("LetterText", parent=styles["Normal"], fontName="Helvetica", fontSize=9.7, leading=14.2, spaceAfter=4)
    header = ParagraphStyle("LetterHeader", parent=normal, fontName="Helvetica-Bold", fontSize=12.5, leading=17, spaceAfter=8, textColor=colors.HexColor("#102840"), alignment=TA_CENTER)
    caption = ParagraphStyle("LetterCaption", parent=normal, fontSize=8.5, leading=11.5, textColor=colors.HexColor("#6E7E88"))
    subject = ParagraphStyle("LetterSubject", parent=normal, fontName="Helvetica-Bold", fontSize=10.3, leading=14.5, textColor=colors.HexColor("#183F55"))
    story = []
    for index, line in enumerate(draft_text.split("\n")):
        if not line.strip():
            story.append(Spacer(1, 4.5))
        else:
            # Only escaped user input is ever passed to ReportLab markup.
            chosen_style = header if index == 0 else caption if index == 1 or line.startswith("REVIEW BEFORE") else subject if line.startswith("Subject:") or line.rstrip().endswith(":") or line.startswith("PURPOSE - ") else normal
            story.append(Paragraph(escape(line.replace("₹", "INR ")).replace("\n", " "), chosen_style))
    doc.build(story)
    result.seek(0)
    return StreamingResponse(result, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="casewise-{request.document_type}-draft.pdf"', "Cache-Control": "no-store"})
