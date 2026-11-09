"""Phase 2 case-file regression checks using synthetic cases only."""
import io
import json

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.case_builder import build_case, QUESTIONS
from backend.case_export import case_as_json, case_as_pdf
from backend.main import app

client = TestClient(app)


def chat(*statements):
    return [{"role": "user", "content": statement} for statement in statements]


def test_subtype_and_reported_fields_are_not_legal_findings():
    case = build_case(chat("My landlord will not return my ₹30,000 rental security deposit in Kanpur. I have the rental agreement."))
    assert case["category"] == "property"
    assert case["subtype"]["code"] == "rental_deposit"
    assert case["facts"]["amount"]["value"] == "₹30,000"
    assert case["facts"]["user_role"]["value"] == "Tenant"
    assert case["evidence_uploaded"] is False
    assert all(item["verified"] is False for item in case["evidence"])


@pytest.mark.parametrize("story,category,subtype", [
    ("I bought a defective phone and the seller denied a refund.", "consumer", "refund"),
    ("My employer did not pay my salary.", "employment", "unpaid_salary"),
    ("The client has not paid my website invoice.", "contract", "unpaid_invoice"),
])
def test_categories_and_subtypes(story, category, subtype):
    case = build_case(chat(story))
    assert case["category"] == category
    assert case["subtype"]["code"] == subtype


def test_date_extraction_timeline_and_provenance():
    case = build_case(chat("On 10 November 2026 the seller refused my refund.",
                           "I first complained on 5 November 2026 and have the invoice."))
    assert case["facts"]["event_date"]["value"] == "5 November 2026"
    dates = [row["date"] for row in case["timeline"]]
    assert dates == ["5 November 2026", "10 November 2026"]
    assert all(row["status"] == "reported" for row in case["timeline"])
    assert all(row["source_message"] in (0, 1) for row in case["timeline"])


def test_evidence_availability_is_user_reported_not_verified():
    case = build_case(chat("I bought an item. I have the invoice and payment receipt."))
    values = {e["type"]: e["availability"] for e in case["evidence"]}
    assert values["Invoice"] == "user_says_available"
    assert values["Receipt"] == "user_says_available"
    assert all(e["verified"] is False for e in case["evidence"])


def test_missing_questions_progress_without_repeating():
    user = chat("My landlord refused to return my deposit.")
    first = build_case(user)
    question = first["next_question"]
    assert question["field"] == "counterparty"
    next_case = build_case(user, asked_fields=["counterparty"])
    assert next_case["next_question"]["field"] != "counterparty"
    assert next_case["next_question"]["field"] in [item["key"] for item in next_case["missing"]]


def test_chat_response_to_targeted_question_populates_field():
    messages = [
        {"role": "user", "content": "I bought a faulty phone from a seller."},
        {"role": "assistant", "content": QUESTIONS["counterparty"]},
        {"role": "user", "content": "Example Retailer"},
    ]
    result = build_case(messages, asked_fields=["counterparty"])
    assert result["facts"]["counterparty"]["value"] == "Example Retailer"


def test_possible_amount_conflicts_are_not_assumed_as_genuine_conflicts():
    case = build_case(chat("I paid ₹30,000 as a rental deposit.",
                           "Later the landlord said ₹25,000 would be returned."))
    assert any(issue["id"] == "amounts_vary" for issue in case["issues"])
    assert "whether they refer to the same transaction" in case["issues"][0]["message"]


def test_multiple_dates_are_clarifications_not_automatic_contradictions():
    case = build_case(chat("I moved out on 2 October 2026.",
                           "I requested my deposit on 5 November 2026."))
    flag = next(i for i in case["issues"] if i["id"] == "multiple_dates")
    assert flag["type"] == "clarification"


def test_completeness_is_information_only_and_unknown_date_does_not_count():
    case = build_case(chat("My employer refused to pay my salary."),
                      profile={"event_date": "Not known"})
    assert case["completeness"]["total"] == 8
    assert not next(row for row in case["completeness"]["checks"] if row["key"] == "event_date")["complete"]
    assert "not legal merit" in case["completeness"]["description"]


def test_user_corrections_override_ai_and_are_marked():
    ai = {
        "category": "consumer",
        "story_english": "The user reports a broken laptop.",
        "timeline": [{"date": "", "event": "A broken laptop was delivered."}],
    }
    result = build_case(chat("I bought a damaged laptop."),
                        case_overrides={"counterparty": "Example Seller", "subtype": "defective_product"},
                        story_override="I ordered one laptop which arrived with screen damage.",
                        ai=ai, reviewed=True)
    assert result["facts"]["counterparty"]["value"] == "Example Seller"
    assert result["facts"]["counterparty"]["status"] == "user_edited"
    assert result["subtype"]["code"] == "defective_product"
    assert result["narrative"]["status"] == "user_edited"
    assert result["review"]["confirmed"] is True


def test_timeline_and_evidence_review_edits_are_not_misrepresented():
    case = build_case(chat("I purchased a faulty laptop."),
                      timeline_edits=[{"id": "manual-1", "date": "10 November 2026", "event": "User-confirmed delivery date"}],
                      evidence_edits=[{"id": "e1", "type": "Invoice", "description": "Electronic purchase invoice",
                                       "availability": "user_says_available"}])
    assert case["timeline"][0]["status"] == "user_edited"
    assert case["evidence"][0]["availability"] == "user_says_available"
    assert case["evidence"][0]["verified"] is False


def test_no_automatic_evidence_upload_or_server_storage():
    case = build_case(chat("The seller denied a refund for my item."))
    assert case["evidence_uploaded"] is False
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["stored_cases"] is False


def test_reviewed_json_and_pdf_exports_and_unreviewed_rejection():
    payload = {
        "messages": [{"role": "user", "content": "I bought a broken laptop for ₹45,000 and the shop refused a refund."}],
        "category": "consumer", "profile": {"location": "Kanpur", "counterparty": "Example Shop"},
        "story_override": "I received a damaged laptop and requested a refund.",
        "case_overrides": {"desired_resolution": "Full refund"}, "case_id": "CW-TEST123",
    }
    unconfirmed = client.post("/api/case-export", json={**payload, "reviewed": False})
    assert unconfirmed.status_code == 422

    response = client.post("/api/case-export", json={**payload, "reviewed": True, "export_format": "json"})
    assert response.status_code == 200
    doc = response.json()
    assert doc["case_id"] == "CW-TEST123"
    assert doc["review"]["confirmed"]
    assert doc["facts"]["counterparty"]["value"] == "Example Shop"
    assert doc["narrative"]["text"] == payload["story_override"]

    pdf = client.post("/api/case-export", json={**payload, "reviewed": True, "export_format": "pdf"})
    assert pdf.status_code == 200
    text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "REVIEWED CASE FILE" in text
    assert "not independently verified" in text.lower()
    assert "Example Shop" in text


def test_case_file_endpoint_returns_structured_payload():
    r = client.post("/api/case-file", json={
        "messages": [{"role": "user", "content": "A seller denied my refund."}],
        "asked_fields": ["counterparty"],
        "case_overrides": {"location": "Kanpur"},
    })
    assert r.status_code == 200, r.text
    case = r.json()
    assert "timeline" in case and "evidence" in case and "issues" in case
    assert case["facts"]["location"]["value"] == "Kanpur"
    assert case["next_question"]["field"] != "counterparty"


def test_legacy_ai_safety_and_drafting_endpoints_remain():
    urgent = client.post("/api/analyze", json={
        "messages": [{"role": "user", "content": "I have a court summons and a hearing tomorrow."}],
    })
    assert urgent.status_code == 200
    assert urgent.json()["needs_lawyer"]
    assert urgent.json()["case_file"]["risk_flag"] == "urgent_or_criminal"
    blocked = client.post("/api/draft", json={
        "messages": [{"role": "user", "content": "I have a court summons and a hearing tomorrow."}],
        "confirmed": True,
        "profile": {"counterparty": "Other party", "location": "Delhi",
                    "event_date": "Tomorrow", "desired_resolution": "Advice"},
    })
    assert blocked.status_code == 422


def test_empty_react_profile_defaults_do_not_claim_user_correction():
    profile = {"location": "", "counterparty": "", "amount": "", "event_date": "", "evidence": "", "desired_resolution": ""}
    case = build_case(chat("I paid a ₹15,000 rental deposit and have a receipt."), profile=profile)
    assert case["facts"]["amount"]["value"] == "₹15,000"
    assert case["facts"]["amount"]["status"] == "reported"
    assert case["facts"]["amount"]["sources"]
