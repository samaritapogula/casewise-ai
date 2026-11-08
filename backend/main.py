"""CaseWise AI — FastAPI service. No user-case persistence by default."""
from __future__ import annotations

from io import BytesIO
import os
from xml.sax.saxutils import escape

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from .engine import analyze, make_draft
from .knowledge import SOURCES, VERIFIED_ON
from .llm import conversational_followup, is_configured

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


def as_dict(request: Request) -> list[dict]:
    return [message.model_dump() for message in request.messages]


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0", "llm_configured": is_configured(), "stored_cases": False}


@app.get("/api/sources")
def get_sources():
    return {"verified_on": VERIFIED_ON, "sources": list(SOURCES.values())}


@app.post("/api/analyze")
def analyze_case(request: Request):
    try:
        data = analyze(as_dict(request), request.profile, request.category)
        answer = conversational_followup(data, as_dict(request))
        if answer:
            data["assistant_message"] = answer
            data["mode"] = "gemini-assisted"
        return data
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/draft")
def make_pdf(request: Request):
    try:
        draft_text = make_draft(as_dict(request), request.profile, request.category)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = BytesIO()
    doc = SimpleDocTemplate(result, pagesize=A4, topMargin=44, bottomMargin=46, leftMargin=48, rightMargin=48)
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("LetterText", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=15, spaceAfter=6)
    header = ParagraphStyle("LetterHeader", parent=normal, fontName="Helvetica-Bold", fontSize=12, leading=17, textColor=colors.HexColor("#102840"), alignment=TA_CENTER)
    story = []
    for index, line in enumerate(draft_text.split("\n")):
        if not line.strip():
            story.append(Spacer(1, 7))
        else:
            # Only escaped user input is ever passed to ReportLab markup.
            story.append(Paragraph(escape(line.replace("₹", "INR ")).replace("\n", " "), header if index == 0 else normal))
    doc.build(story)
    result.seek(0)
    return StreamingResponse(result, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="casewise-draft-request.pdf"', "Cache-Control": "no-store"})
