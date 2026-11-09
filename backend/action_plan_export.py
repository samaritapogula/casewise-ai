"""A readable, source-linked export of a user-reviewed Phase 3 action plan."""
from __future__ import annotations
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

def as_pdf(plan: dict) -> bytes:
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=49, leftMargin=49,
                            topMargin=43, bottomMargin=44, title="CaseWise AI | Personal Action Plan")
    base_styles = getSampleStyleSheet()
    normal = ParagraphStyle("ActionNormal", parent=base_styles["Normal"], fontSize=9.2,
                            leading=14.0, spaceAfter=6, textColor=colors.HexColor("#284354"))
    h1 = ParagraphStyle("ActionHeading", parent=normal, fontSize=14, leading=20,
                        fontName="Helvetica-Bold", spaceAfter=12, alignment=TA_CENTER)
    h2 = ParagraphStyle("ActionSection", parent=normal, fontSize=10.5,
                        leading=15, fontName="Helvetica-Bold", spaceBefore=10)
    small = ParagraphStyle("ActionCaption", parent=normal, fontSize=8, leading=11.5,
                           textColor=colors.HexColor("#5b6b73"))
    story = []
    def para(value, style=normal):
        story.append(Paragraph(escape(str(value or "")).replace("₹", "INR "), style))
    para("CASEWISE AI - PERSONAL ACTION PLAN", h1)
    para("For information and user review only. Not a legal opinion, filing instruction or guarantee of outcome.", small)
    para("Case reference: " + plan.get("case_id", ""), small)
    if plan.get("stage"):
        para("Guidance stage: " + plan["stage"].get("title", "Preliminary"), h2)
        para(plan["stage"].get("description", ""), small)
    if plan.get("case_focus", {}).get("items"):
        para("Facts driving this plan (user-reported only)", h2)
        para(plan["case_focus"].get("narrative", ""), small)
        for item in plan["case_focus"]["items"]:
            para(item["label"] + ": " + item["value"])
    para("Legal position - cautious orientation", h2)
    para(plan["position"]["heading"] + ": " + plan["position"]["explanation"])
    for point in plan["position"]["considerations"]:
        para("- " + point)
    para("Reported supporting information (not evidence verified)", h2)
    para("Statements and supporting documents in this report have NOT been independently verified.", small)
    for statement in plan["supporting_reports"]:
        para("- " + statement)
    para("Unknowns and review gaps", h2)
    for gap in (plan["evidence_gaps"] + plan["uncertainties"]):
        para("- " + gap)
    if plan.get("context_questions"):
        para("Additional questions for a better case record", h2)
        for detail in plan["context_questions"]:
            answer = detail["answer"] if detail.get("status") != "missing" else "Not yet answered"
            para(detail["label"] + ": " + answer)
            if detail.get("status") == "missing":
                para(detail["question"], small)
    para("Possible official channels", h2)
    for route in plan["routes"]:
        para(route["title"] + ": " + route["when_to_consider"])
        para("Eligibility and jurisdiction have not been assessed.", small)
    if plan.get("document_recommendations"):
        para("Possible document types - not filing instructions", h2)
        for suggestion in plan["document_recommendations"]:
            if suggestion.get("status") == "recommended":
                para(suggestion["label"] + " - " + suggestion["reason"])
    para("Personal action checklist", h2)
    for idx, task in enumerate(plan["actions"], 1):
        state = "[user marked complete]" if task["completed"] else "[not marked complete]"
        para(f"{idx}. {task['title']} {state}")
        para(task["instructions"])
    para("Escalation and professional review", h2)
    para(plan["escalation"]["message"])
    for reason in plan["escalation"]["reasons"]:
        para("- " + reason)
    para("Official reference links", h2)
    for src in plan["sources"]:
        # Trusted whitelist constants; URL values cannot be supplied by a client or LLM.
        title = escape(src["title"])
        url = escape(src["url"], {'"': '&quot;'})
        story.append(Paragraph(f'<link href="{url}" color="#216B88">{title}</link>', normal))
        para(src["url"], small)
    story.append(Spacer(1, 10))
    para(plan["source_status"], small)
    para(plan["disclaimer"], small)
    doc.build(story)
    return output.getvalue()
