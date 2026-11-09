"""Check that the five chosen document options generate genuinely different drafts."""
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.main import app
from backend.engine import make_draft

client = TestClient(app)
MESSAGE = [{"role": "user", "content": (
    "I paid my landlord a ₹30,000 deposit in Kanpur and moved out on 5 October 2026. "
    "My landlord has not returned the deposit. I have the rental agreement and WhatsApp messages."
)}]
PROFILE = {
    "counterparty": "Example landlord", "location": "Kanpur", "event_date": "5 October 2026",
    "amount": "₹30,000", "evidence": "receipt, messages, whatsapp, agreement",
    "desired_resolution": "Return my full deposit",
    "facts_narrative": MESSAGE[0]["content"],
}


@pytest.mark.parametrize("kind,unique", [
    ("request", ["Purpose of this request:", "Previous attempts to resolve the matter:",
                 "Resolution I am asking for:"]),
    ("notice", ["1. Parties and relationship:", "2. Facts alleged by the sender",
                "3. Relevant transaction", "6. Questions for the reviewing lawyer:"]),
    ("complaint", ["Nature of grievance:", "Statement of reported facts:",
                   "Steps taken before this complaint:", "Action requested from the receiving organization:"]),
    ("reply", ["REFERENCE TO COMMUNICATION RECEIVED:", "The points I am responding to:",
               "My factual account for review:", "Reservation for professional review:"]),
    ("application", ["Type of assistance sought:", "Why I am requesting assistance:",
                     "Assistance or response requested from this office:", "Eligibility and procedure:"]),
])
def test_document_type_changes_full_body_not_just_title(kind, unique):
    result = make_draft(MESSAGE, PROFILE, category="property", confirmed=True, document_type=kind)
    for section in unique:
        assert section in result
    assert "not a court filing" in result.lower()
    assert "an INR 30,000 deposit" in result
    assert "Supporting materials mentioned by the user: receipt, WhatsApp messages, agreement" in result
    assert "Section 9999" not in result
    assert "liable under section" not in result.lower()


def test_all_draft_bodies_are_meaningfully_distinct():
    result = {
        kind: make_draft(MESSAGE, PROFILE, category="property", confirmed=True, document_type=kind)
        for kind in ("request", "notice", "complaint", "reply", "application")
    }
    assert len(set(result.values())) == 5
    assert "Questions for the reviewing lawyer" in result["notice"]
    assert "Questions for the reviewing lawyer" not in result["complaint"]
    assert "No incoming notice has been verified" in result["reply"]
    assert "No incoming notice has been verified" not in result["request"]
    assert "eligibility rules or forms apply" in result["application"].lower()
    assert "eligibility rules or forms apply" not in result["request"].lower()


def test_reply_uses_only_supplied_incoming_communication_not_invented_defenses():
    amended = {
        **PROFILE,
        "received_communication": "A written demand dated 6 October 2026 asking for repair costs.",
        "reply_points": "The other party says there was damage at handover.",
    }
    result = make_draft(MESSAGE, amended, confirmed=True, document_type="reply")
    assert "A written demand dated 6 October 2026" in result
    assert "The other party says there was damage" in result
    assert "[Provide details" not in result
    assert "formal denial" in result
    assert "Section" not in result


def test_complaint_and_application_consume_additional_review_fields():
    profile = {
        **PROFILE,
        "recipient_name": "Example Assistance Office",
        "prior_contact": "I emailed the other party on 9 October 2026.",
        "office_action": "Please review the grievance and advise on the relevant process.",
        "assistance_requested": "I request information about access to legal aid.",
    }
    complaint = make_draft(MESSAGE, profile, confirmed=True, document_type="complaint")
    application = make_draft(MESSAGE, profile, confirmed=True, document_type="application")
    assert "To: Example Assistance Office" in complaint
    assert "I emailed the other party on 9 October 2026." in complaint
    assert "Please review the grievance and advise" in complaint
    assert "I request information about access to legal aid" in application
    assert "Party concerned: Example landlord" in complaint
    assert "Party concerned: Example landlord" in application


def test_notice_does_not_invent_a_response_deadline_or_a_statute():
    text = make_draft(MESSAGE, PROFILE, confirmed=True, document_type="notice")
    assert "No statutory provision or deadline is asserted by this outline." in text
    assert "within 15 days" not in text
    assert "Section 9999" not in text
    assert "LAWYER REVIEW REQUIRED" in text


def test_preview_returns_same_text_used_by_pdf_and_requires_review():
    payload = {"messages": MESSAGE, "profile": PROFILE,
               "category": "property", "document_type": "application"}
    blocked = client.post("/api/draft-preview", json={**payload, "confirmed": False})
    assert blocked.status_code == 422
    preview = client.post("/api/draft-preview", json={**payload, "confirmed": True})
    assert preview.status_code == 200, preview.text
    assert preview.headers["cache-control"] == "no-store"
    assert preview.json()["draft"] == make_draft(
        MESSAGE, PROFILE, category="property", confirmed=True, document_type="application")
    pdf = client.post("/api/draft", json={**payload, "confirmed": True})
    assert pdf.status_code == 200
    full_text = " ".join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
    assert "Type of assistance sought" in full_text
    assert "Eligibility and procedure" in full_text
    assert "not a court filing" in full_text


@pytest.mark.parametrize("kind", ["request", "notice", "complaint", "reply", "application"])
def test_urgent_cases_block_all_draft_kinds(kind):
    urgent = [{"role": "user", "content": "I was served a court summons and have a hearing tomorrow."}]
    response = client.post("/api/draft-preview", json={
        "messages": urgent, "profile": PROFILE,
        "document_type": kind, "confirmed": True,
    })
    assert response.status_code == 422
