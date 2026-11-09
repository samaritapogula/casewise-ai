"""Synthetic cross-category tests for case-driven adaptive behavior."""
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.case_builder import build_case
from backend.case_policy import get_case_policy
from backend.legal_plan import build_legal_plan
from backend.main import app

client = TestClient(app)


def msgs(*values):
    return [{"role": "user", "content": value} for value in values]


EXAMPLES = [
    ("property", "My landlord refused to return the rental security deposit.",
     "rental_deposit", "Rental Manager", "Return the deposit"),
    ("consumer", "I purchased a damaged laptop and the seller refused a refund.",
     "refund", "Example Retailer", "Refund the purchase"),
    ("employment", "My employer has not paid my salary for work completed.",
     "unpaid_salary", "Example Employer", "Pay unpaid salary"),
    ("contract", "A client has not paid my invoice for services delivered under a contract.",
     "unpaid_invoice", "Example Client", "Pay the outstanding invoice"),
]


def full_case(category, story, counterparty, goal):
    return build_case(
        msgs(story + " I have an agreement, a payment receipt and email messages."),
        category=category,
        profile={
            "counterparty": counterparty, "location": "Example City, Example State",
            "event_date": "20 October 2026", "amount": "₹30,000",
            "evidence": "Agreement, payment receipt and emails",
            "desired_resolution": goal,
        },
    )


@pytest.mark.parametrize("category,story,subtype,party,goal", EXAMPLES)
def test_stages_depend_on_reported_facts_for_every_category(category, story, subtype, party, goal):
    initial = build_legal_plan(build_case(msgs(story), category=category))
    assert initial["stage"]["code"] == "intake"
    assert not any(a["id"] == "contact" for a in initial["actions"])

    developing = build_legal_plan(build_case(
        msgs(story), category=category,
        profile={"counterparty": party, "location": "Example City",
                 "event_date": "20 October 2026", "desired_resolution": goal}
    ))
    assert developing["stage"]["code"] == "preliminary"
    assert not any(a["id"] == "contact" for a in developing["actions"])

    case = full_case(category, story, party, goal)
    plan = build_legal_plan(case)
    assert case["subtype"]["code"] == subtype
    assert plan["stage"]["code"] == "personalized"
    assert plan["stage"]["code"] != initial["stage"]["code"]
    tasks = {item["id"]: item for item in plan["actions"]}
    assert "contact" in tasks and "review_evidence" in tasks
    assert party in tasks["contact"]["instructions"]
    assert goal in tasks["contact"]["instructions"]
    assert "₹30,000" in tasks["contact"]["instructions"]
    assert "20 October 2026" in tasks["contact"]["instructions"]
    assert plan["document_recommendations"][0]["type"] == "request"
    assert plan["document_recommendations"][0]["status"] == "recommended"


def test_generic_data_registry_supports_fallback_and_subtypes_without_case_example_values():
    for category, _, subtype, _, _ in EXAMPLES:
        policy = get_case_policy(category, subtype)
        assert policy["detail_questions"]
        assert policy["focus"]
        assert policy["records"]
        assert len({q["id"] for q in policy["detail_questions"]}) == len(policy["detail_questions"])
        assert all("30,000" not in q["question"] for q in policy["detail_questions"])
        assert all("Sweet Home" not in q["question"] for q in policy["detail_questions"])
    fallback = get_case_policy("unknown-new-category", "unknown-subtype")
    assert fallback["detail_questions"]


def test_targeted_questions_begin_after_core_questions_complete_and_capture_followup():
    category, story, subtype, party, goal = EXAMPLES[0]
    case = full_case(category, story, party, goal)
    next_q = case["next_question"]
    assert next_q["field"].startswith("context:")
    assert len(case["context"]["questions"]) >= 2
    response = [
        *msgs(story + " I have an agreement, a payment receipt and email messages."),
        {"role": "assistant", "content": next_q["text"]},
        {"role": "user", "content": "The signed agreement states the deposit can be adjusted for damage."},
    ]
    updated = build_case(response, category=category, profile={
        "counterparty": party, "location": "Example City", "event_date": "20 October 2026",
        "amount": "₹30,000", "desired_resolution": goal, "evidence": "Agreement and receipt",
    }, asked_fields=[next_q["field"]])
    answered = next(q for q in updated["context"]["questions"]
                    if "context:" + q["id"] == next_q["field"])
    assert answered["status"] == "reported"
    assert "adjusted for damage" in answered["answer"]
    assert updated["next_question"]["field"] != next_q["field"]
    assert any(item["key"] == next_q["field"] for item in updated["structured_summary"]["items"])


def test_not_known_is_acknowledged_without_inventing_a_date():
    category, story, _, party, goal = EXAMPLES[1]
    messages = [
        *msgs(story),
        {"role": "assistant", "content": "When did the key event happen? Give the date if known, or say you do not know."},
        {"role": "user", "content": "I don't know"},
    ]
    case = build_case(messages, category=category, profile={
        "counterparty": party, "location": "Example City", "amount": "₹1,000",
        "evidence": "No evidence", "desired_resolution": goal,
    })
    assert "event_date" in case["unknown_fields"]
    assert case["facts"]["event_date"]["value"] == ""
    assert next(c for c in case["completeness"]["checks"] if c["key"] == "event_date")["complete"] is False
    assert build_legal_plan(case)["stage"]["code"] == "personalized"


def test_receipt_and_bank_transfer_not_double_counted_when_one_physical_record():
    case = build_case(msgs(
        "My landlord has not returned a deposit. "
        "I have a signed rental agreement, a bank transfer receipt, and WhatsApp messages."
    ))
    types = [entry["type"] for entry in case["evidence"]]
    assert types.count("Receipt") == 1
    assert "Payment Record" not in types
    assert set(types) == {"Agreement", "Receipt", "Messages"}
    assert len(types) == 3
    assert any("transfer receipt" in item["description"].lower() for item in case["evidence"])
    assert all(item["verified"] is False for item in case["evidence"])


def test_separate_bank_statement_and_receipt_remain_separate():
    case = build_case(msgs(
        "I have a payment receipt and a separate bank statement, plus an invoice. The seller refused the refund."
    ))
    assert {"Receipt", "Payment Record", "Invoice"} <= {x["type"] for x in case["evidence"]}


def test_corrected_case_summaries_include_final_amount_goal_and_evidence_without_changing_narrative():
    category, story, _, party, goal = EXAMPLES[0]
    case = full_case(category, story, party, goal)
    summary = case["structured_summary"]
    assert "₹30,000" in summary["text"]
    assert goal in summary["text"]
    assert party in summary["text"]
    assert "Receipt" in summary["text"] or "receipt" in summary["text"]
    assert summary["status"] == "compiled_from_reported_fields"
    assert "₹30,000" not in case["narrative"]["text"]


def test_ongoing_nonpayment_is_not_silently_deleted_or_pretended_to_be_second_dated_refusal():
    case = build_case(msgs(
        "My landlord has not returned the security deposit.",
        "The landlord refused the return on 20 October 2026.",
    ))
    assert len(case["timeline"]) == 2
    assert case["timeline"][0]["event_kind"] == "ongoing_status"
    assert case["timeline"][1]["event_kind"] == "event"
    assert case["timeline"][0]["date"] == ""
    assert case["timeline"][1]["date"] == "20 October 2026"


def test_user_changes_and_unresolved_conflicts_do_not_create_false_legal_findings():
    case = build_case(msgs(
        "I paid ₹30,000 as a deposit.", "The landlord says only ₹25,000 is refundable."
    ), profile={"counterparty": "Example", "location": "Example City",
                "event_date": "20 October 2026",
                "evidence": "No records", "desired_resolution": "Return the deposit"})
    plan = build_legal_plan(case)
    assert any(x["id"] == "amounts_vary" for x in case["issues"])
    assert any(x["id"] == "resolve_issues" for x in plan["actions"])
    assert "different" in " ".join(plan["evidence_gaps"]).lower() or "clarification" in " ".join(plan["evidence_gaps"]).lower()
    assert all("guarantee" not in x["instructions"].lower() for x in plan["actions"])


def test_plan_and_case_pdf_include_dynamic_stage_and_collected_facts():
    category, story, _, party, goal = EXAMPLES[2]
    payload = {
        "messages": msgs(story + " I have an agreement and a payment receipt."),
        "category": category, "profile": {
            "counterparty": party, "location": "Example City",
            "event_date": "20 October 2026", "amount": "₹30,000",
            "evidence": "Agreement and payment receipt", "desired_resolution": goal,
        },
        "case_id": "CW-ADAPTIVE-TEST", "reviewed": True,
        "plan_reviewed": True, "story_override": story,
    }
    plan_pdf = client.post("/api/legal-plan/export", json=payload)
    assert plan_pdf.status_code == 200, plan_pdf.text
    plan_text = " ".join(p.extract_text() for p in PdfReader(BytesIO(plan_pdf.content)).pages)
    assert "Case-specific action plan" in plan_text
    assert "Example Employer" in plan_text
    assert "INR 30,000" in plan_text
    case_pdf = client.post("/api/case-export", json={**payload, "export_format": "pdf"})
    assert case_pdf.status_code == 200, case_pdf.text
    case_text = " ".join(p.extract_text() for p in PdfReader(BytesIO(case_pdf.content)).pages)
    assert "Compiled reported facts" in case_text
    assert "Example Employer" in case_text
    assert "INR 30,000" in case_text


def test_urgent_and_unknown_categories_never_trigger_routine_recommendation():
    urgent = build_legal_plan(build_case(msgs(
        "I have a court summons and hearing tomorrow about my job."
    )))
    assert urgent["stage"]["code"] == "urgent"
    ids = [a["id"] for a in urgent["actions"]]
    assert "urgent_advice" in ids and "contact" not in ids and "channels" not in ids
    unknown = build_legal_plan(build_case(msgs("I have an unusual disagreement with someone.")))
    assert unknown["stage"]["code"] == "triage"
    assert not any(a["id"] == "contact" for a in unknown["actions"])
