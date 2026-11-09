"""Phase 4 regression tests: cross-category, document-specific and safety focused."""
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.main import app
from backend.case_builder import build_case
from backend.phase4 import build_document_intelligence, build_argument_outline

client = TestClient(app)

STORIES = {
    "property": "My landlord Redwood Property Services refused to return my ₹25,000 deposit after I vacated in Kanpur on 2 October 2026. I have the agreement.",
    "consumer": "I purchased a laptop from TechZone Electronics for ₹55,000 in Hyderabad on 10 October 2026. It stopped working and the seller denied a refund. I have the invoice.",
    "employment": "My employer Aurora Systems refused to pay ₹40,000 salary in Pune on 1 October 2026. I have a payslip and email reminders.",
    "contract": "My client Horizon Studio refused to pay my ₹60,000 invoice for a completed project in Delhi on 7 October 2026. I have our email agreement.",
}
PROFILE = {
    "counterparty": "A Reported Party", "location": "City, State",
    "event_date": "1 October 2026", "desired_resolution": "Payment requested",
    "amount": "₹10,000", "evidence": "Email messages",
}


@pytest.mark.parametrize("category,story", STORIES.items())
@pytest.mark.parametrize("kind", ("request", "notice", "complaint", "reply", "application"))
def test_phase4_guidance_generic_across_five_documents_and_four_disputes(category, story, kind):
    case = build_case([{"role": "user", "content": story}], category=category)
    guidance = build_document_intelligence(case, kind, PROFILE)
    assert guidance["document_type"] == kind
    assert guidance["schema_version"] == "4.0"
    assert guidance["readiness"]["status"] == "needs_review"
    assert "NOT a legal filing" in guidance["readiness"]["message"]
    assert len(guidance["questions"]) >= 4
    assert guidance["fact_trace"]
    assert all(item["verified"] is False for item in guidance["fact_trace"])
    if kind == "reply":
        assert "received_communication" in [q["key"] for q in guidance["questions"]]
        assert guidance["readiness"]["required_answered"] < guidance["readiness"]["required_total"]
    if kind in ("complaint", "application"):
        assert any(q["key"] == "recipient_name" and not q["answered"] for q in guidance["questions"])


def test_reply_readiness_changes_only_when_actual_incoming_message_supplied():
    case = build_case([{"role": "user", "content": STORIES["consumer"]}], category="consumer")
    no_reply = build_document_intelligence(case, "reply", PROFILE)
    yes_reply = build_document_intelligence(case, "reply", {
        **PROFILE,
        "received_communication": "Written demand dated 3 October 2026",
        "reply_points": "The other party claims I failed to pay",
    })
    assert yes_reply["readiness"]["required_answered"] == no_reply["readiness"]["required_answered"] + 2
    assert not any(q["required"] and not q["answered"] for q in yes_reply["questions"])
    assert yes_reply["readiness"]["status"] == "needs_review"


def test_phase4_reality_checks_when_case_is_incomplete():
    case = build_case([{"role": "user", "content": "My seller has not refunded me."}])
    guidance = build_document_intelligence(case, "complaint")
    assert guidance["readiness"]["required_answered"] < guidance["readiness"]["required_total"]
    assert any("Missing:" in s for s in guidance["readiness"]["warnings"])
    assert all(not q["answered"] for q in guidance["questions"] if q["key"] == "recipient_name")


@pytest.mark.parametrize("category,story", STORIES.items())
def test_argument_outline_never_claims_verification_or_legal_outcome(category, story):
    case = build_case([{"role": "user", "content": story}], category=category)
    outline = build_argument_outline(case)
    assert len(outline["key_points"]) == 4
    assert all(item["verified"] is False for item in outline["key_points"])
    assert "Not a court argument" in outline["disclaimer"]
    combined = str(outline).lower()
    assert "guaranteed win" not in combined
    assert "section 999" not in combined


def test_document_guidance_endpoint_uses_case_and_user_profile():
    payload = {"messages": [{"role": "user", "content": STORIES["consumer"]}],
               "document_type": "complaint", "category": "consumer",
               "profile": PROFILE}
    r = client.post("/api/document-intelligence", json=payload)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["document_type"] == "complaint"
    assert any(row["key"] == "recipient_name" and not row["answered"] for row in doc["questions"])
    a = client.post("/api/argument-outline", json=payload)
    assert a.status_code == 200
    assert "factual" in a.json()["heading"].lower()


def test_invalid_doc_type_rejected_and_urgent_refuses_argument():
    case = build_case([{"role": "user", "content": STORIES["consumer"]}])
    with pytest.raises(ValueError):
        build_document_intelligence(case, "court-filing", PROFILE)
    case["risk_flag"] = "urgent_or_criminal"
    assert build_document_intelligence(case, "notice", PROFILE)["readiness"]["status"] == "blocked_urgent"
    with pytest.raises(ValueError):
        build_argument_outline(case)
    response = client.post("/api/argument-outline", json={
        "messages": [{"role":"user","content":"I received a court summons and my hearing is tomorrow."}]
    })
    assert response.status_code == 422


def test_edited_document_is_exported_verbatim_with_mandatory_warning():
    messages = [{"role": "user", "content": STORIES["consumer"]}]
    payload = {"messages": messages, "category": "consumer", "profile": PROFILE,
               "document_type": "request", "confirmed": True}
    preview = client.post("/api/draft-preview", json=payload)
    assert preview.status_code == 200, preview.text
    edited = preview.json()["draft"].replace("Payment requested", "I request a factual payment explanation")
    pdf = client.post("/api/draft", json={**payload, "edited_draft": edited})
    assert pdf.status_code == 200, pdf.text
    body = "\n".join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    assert "I request a factual payment explanation" in body
    assert "USER-EDITED PRELIMINARY DRAFT" in body
    assert "REVIEW BEFORE SENDING" in body
    assert "not legal advice or an official filing" in body.lower()


def test_user_cannot_bypass_review_gate_using_edited_draft():
    payload = {"messages": [{"role":"user","content":STORIES["consumer"]}], "profile": PROFILE,
               "document_type":"notice", "edited_draft":"Send a notice immediately.",
               "confirmed":False}
    response = client.post("/api/draft", json=payload)
    assert response.status_code == 422
    urgent = client.post("/api/draft", json={
        **payload, "confirmed":True,
        "messages":[{"role":"user","content":"A court summons has arrived for a hearing tomorrow."}],
    })
    assert urgent.status_code == 422


def test_preview_draft_remains_unedited_for_prior_consumers():
    payload = {"messages":[{"role":"user","content":STORIES["property"]}],
               "category":"property", "profile":PROFILE, "document_type":"request","confirmed":True}
    preview = client.post("/api/draft-preview", json=payload)
    assert preview.status_code == 200
    assert "edited_draft" not in preview.json()
    pdf = client.post("/api/draft", json=payload)
    assert pdf.status_code == 200
    body = "\n".join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    assert "USER-EDITED PRELIMINARY DRAFT" not in body
