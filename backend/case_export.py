"""Export a user-reviewed factual case file; never an official legal document."""
from __future__ import annotations

import json
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

FIELDS = (
    ("user_role", "Your role"),
    ("counterparty", "Other party"),
    ("location", "City / state"),
    ("key_event", "Key event"),
    ("event_date", "Relevant date"),
    ("amount", "Amount involved"),
    ("desired_resolution", "Requested outcome"),
)


def case_as_json(file: dict) -> bytes:
    """Keep provenance and verification labels in the exported data."""
    return json.dumps(file, ensure_ascii=False, indent=2).encode("utf-8")


def case_as_pdf(file: dict) -> bytes:
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=46, rightMargin=46, topMargin=44, bottomMargin=46)
    styles = getSampleStyleSheet()
    base = ParagraphStyle("CaseText", parent=styles["Normal"], fontName="Helvetica", fontSize=9.3, leading=14, spaceAfter=6)
    small = ParagraphStyle("CaseSmall", parent=base, fontSize=8, leading=11, textColor=colors.HexColor("#657783"))
    heading = ParagraphStyle("CaseHeading", parent=base, fontName="Helvetica-Bold", fontSize=13, leading=18,
                             textColor=colors.HexColor("#14364A"), alignment=TA_CENTER, spaceAfter=12)
    section = ParagraphStyle("CaseSection", parent=base, fontName="Helvetica-Bold", fontSize=10.6,
                             textColor=colors.HexColor("#14364A"), spaceBefore=9)
    body = []
    def add(value: str, style=base):
        # ReportLab Helvetica cannot render the rupee symbol consistently.
        safe = escape(str(value or "").replace("₹", "INR ")).replace("\n", " ")
        body.append(Paragraph(safe, style))
    add("CASEWISE AI | REVIEWED CASE FILE", heading)
    add("Factual information only. Not independently verified, legal advice, a legal notice or a court filing.", small)
    add("Case reference: " + file["case_id"], small)
    add("Civil issue: " + file["category_label"] + " / " + file["subtype"]["label"])
    add("Information completeness: %s/%s checks. This is NOT legal merit or filing readiness."
        % (file["completeness"]["completed"], file["completeness"]["total"]), small)
    # The user's reviewed account appears once, followed by one compact
    # structured ledger. Previously, the PDF printed the facts three times.
    add("Reviewed case narrative", section)
    add(file["narrative"]["text"])
    add("Compiled reported facts (not independently verified)", section)
    for key, title in FIELDS:
        if key == "key_event":
            continue  # Already represented in the account and timeline.
        entry = file["facts"].get(key, {})
        value = entry.get("value", "") or "Not supplied"
        add("%s: %s (%s)" % (title, value, entry.get("status", "missing")))
    add("Timeline", section)
    for row in file["timeline"]:
        add("%s — %s [status: %s; source: %s]" % (
            row["date"] or "Date unknown",
            ("[Ongoing status] " if row.get("event_kind") == "ongoing_status" else "") + row["event"], row["status"],
            "message %s" % (row["source_message"] + 1) if row["source_message"] is not None else "unverified suggestion"))
    if not file["timeline"]:
        add("No dated events collected.")
    add("Evidence mentioned", section)
    for entry in file["evidence"]:
        add("%s: %s — %s (not independently verified)" %
            (entry["type"], entry["description"], entry["availability"]))
    if not file["evidence"]:
        add("No evidence identified in the conversation.")
    detail_questions = file.get("context", {}).get("questions", [])
    answered = [item for item in detail_questions if item.get("status") != "missing"]
    pending = [item for item in detail_questions if item.get("status") == "missing"]
    if answered:
        add("Additional reported details", section)
        for item in answered:
            add(item["label"] + ": " + item["answer"])
    # Keep pending questions together with missing/ambiguous information.
    if pending:
        add("Further questions to clarify", section)
        for item in pending:
            add(item["question"])
    add("Unresolved clarifications", section)
    missing = file["missing"]
    if missing:
        add("Missing: " + ", ".join(item["label"] for item in missing))
    for issue in file["issues"]:
        if not issue["resolved"]:
            add("Please review: " + issue["message"])
    if not missing and not any(not item["resolved"] for item in file["issues"]):
        add("No current gaps flagged by the case-builder checklist. Legal review may still be needed.")
    if file.get("risk_flag") != "none":
        add("IMPORTANT: Urgent or criminal issue may exist. Seek professional help promptly.", small)
    body.append(Spacer(1, 10))
    add("USER REVIEWED: This export reflects user-supplied edits and acknowledgement, not external verification.", small)
    add("Before sending or filing any document, confirm jurisdiction, limitation periods, facts and legal advice with a qualified professional.", small)
    doc.build(body)
    return out.getvalue()
