"""Phase 3 functional and safety tests. All cases are synthetic."""
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.main import app
from backend.case_builder import build_case
from backend.legal_plan import build_legal_plan, SOURCES

client = TestClient(app)


def case_for(text, category="auto", profile=None):
    case = build_case([{"role": "user", "content": text}], profile=profile, category=category)
    return build_legal_plan(case)


@pytest.mark.parametrize("text,expected_category,expected_ids", [
    ("I bought a damaged phone and need a refund.", "consumer", {"consumer_law", "nch", "ejagriti"}),
    ("My landlord did not return my rental deposit.", "property", {"contract_law", "nalsa"}),
    ("My employer has not paid my salary.", "employment", {"labour", "nalsa"}),
    ("A client refuses to pay my invoice under the contract.", "contract", {"contract_law", "nalsa"}),
])
def test_all_four_civil_categories_have_grounded_sources(text, expected_category, expected_ids):
    result = case_for(text)
    assert result["category"] == expected_category
    assert expected_ids <= {s["id"] for s in result["sources"]}
    assert all(s["url"].startswith("https://") for s in result["sources"])
    assert all(s["url"] == SOURCES[s["id"]]["url"] for s in result["sources"])
    assert result["position"]["status"].startswith("Cautious orientation")
    assert result["escalation"]["level"] == "general_guidance"
    assert not any("guaranteed to win" in a["instructions"].lower() for a in result["actions"])


def test_statute_references_are_whitelisted_not_ai_generated():
    fake_ai = {"category": "consumer", "story_english": "The user reports a refund problem.",
               "position": "Section 9999 under an imaginary statute guarantees a refund."}
    case = build_case([{"role": "user", "content": "I need a refund for a damaged laptop."}], ai=fake_ai)
    plan = build_legal_plan(case)
    text = " ".join(x["title"] for x in plan["statute_references"])
    assert "9999" not in text
    assert plan["source_status"].startswith("Official source URLs")
    assert "2019" in text
    assert all("applicability" in x and "check" in x["applicability"].lower() for x in plan["statute_references"])


def test_state_specific_law_only_when_location_indicates_up_and_not_assumed_applicable():
    up = case_for("My landlord did not return the apartment deposit.",
                  profile={"location": "Kanpur, Uttar Pradesh"})
    other = case_for("My landlord did not return the apartment deposit.",
                     profile={"location": "Chennai, Tamil Nadu"})
    assert "up_tenancy" in {s["id"] for s in up["sources"]}
    assert "up_tenancy" not in {s["id"] for s in other["sources"]}
    state = next(s for s in up["sources"] if s["id"] == "up_tenancy")
    assert "scope" not in state["relevance"].lower() or "check" in state["relevance"].lower()
    assert "coverage must be checked" in state["relevance"]


def test_reported_items_are_never_misrepresented_as_verified():
    plan = case_for("I have an invoice and payment receipt. The seller refused my refund.",
                    profile={"location": "Kanpur", "amount": "₹20,000"})
    assert any("not verified" in x.lower() for x in plan["supporting_reports"])
    assert any("receipt" in x.lower() for x in plan["supporting_reports"])
    assert "not been independently assessed" in " ".join(plan["uncertainties"])


def test_action_checklist_is_user_marked_and_not_server_persistent():
    story = "I bought a broken product and the shop refused my refund."
    case = build_case([{"role": "user", "content": story}])
    first = build_legal_plan(case, completed_actions={"preserve": True})
    assert next(a for a in first["actions"] if a["id"] == "preserve")["completed"] is True
    second = build_legal_plan(case)
    assert next(a for a in second["actions"] if a["id"] == "preserve")["completed"] is False
    assert first["checklist"]["completed"] == 1
    assert "not evidence of legal compliance" in first["checklist"]["message"]


def test_urgent_cases_remove_routine_filing_channels_and_escalate():
    result = case_for("I have a court summons and hearing tomorrow about my tenancy.",
                      category="property")
    assert result["escalation"]["level"] == "urgent_review"
    ids = {a["id"] for a in result["actions"]}
    assert "urgent_advice" in ids and "contact" not in ids and "channels" not in ids
    assert [r["id"] for r in result["routes"]] == ["urgent"]
    assert "prompt" in result["escalation"]["message"].lower()


def test_unknown_categories_do_not_pick_random_statute_or_filing_forum():
    plan = case_for("I have an unusual disagreement I cannot describe.")
    assert plan["category"] == "other"
    assert plan["statute_references"] == []
    assert plan["escalation"]["level"] == "category_review"
    assert not any(r["id"] == "commission" for r in plan["routes"])


def test_api_plan_uses_user_corrected_phase_two_case():
    response = client.post("/api/legal-plan", json={
        "messages": [{"role": "user", "content": "My landlord has not returned the rental deposit."}],
        "profile": {"location": "Kanpur, Uttar Pradesh"},
        "case_overrides": {"counterparty": "Example landlord"},
        "completed_actions": {"preserve": True},
        "case_id": "CW-SAMPLE13",
    })
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["case_id"] == "CW-SAMPLE13"
    assert "up_tenancy" in {s["id"] for s in plan["sources"]}
    assert next(a for a in plan["actions"] if a["id"] == "preserve")["completed"]


def test_api_analyze_includes_both_phase_two_and_phase_three():
    response = client.post("/api/analyze", json={
        "messages": [{"role": "user", "content": "I paid for a damaged laptop and need a refund."}]
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert "case_file" in result and "legal_plan" in result
    assert result["legal_plan"]["category"] == result["case_file"]["category"]


def test_export_refuses_unreviewed_and_returns_readable_pdf():
    payload = {
        "messages": [{"role": "user", "content": "The seller refused a refund on a broken laptop."}],
        "category": "consumer",
        "case_id": "CW-PDFEXAMPLE",
        "completed_actions": {"preserve": True}
    }
    not_approved = client.post("/api/legal-plan/export", json=payload)
    assert not_approved.status_code == 422
    done = client.post("/api/legal-plan/export", json={**payload, "plan_reviewed": True})
    assert done.status_code == 200, done.text
    assert done.headers["content-type"].startswith("application/pdf")
    assert done.headers["cache-control"] == "no-store"
    reader = PdfReader(BytesIO(done.content))
    content = " ".join(p.extract_text() for p in reader.pages)
    assert "PERSONAL ACTION PLAN" in content
    assert "CW-PDFEXAMPLE" in content
    assert "National Consumer Helpline" in content
    assert "user marked complete" in content
    assert "not verified" in content.lower() or "not independently verified" in content.lower()
    assert len(reader.pages) >= 1


def test_existing_case_draft_and_argument_routes_remain_available():
    case_resp = client.post("/api/case-file", json={
        "messages": [{"role": "user", "content": "My employer did not pay my salary."}]
    })
    assert case_resp.status_code == 200
    practice = client.post("/api/practice", json={
        "messages": [{"role": "user", "content": "A seller refused to refund my laptop."}],
        "argument": "I have an invoice and written complaint messages.",
    })
    assert practice.status_code == 200
    letter = client.post("/api/draft", json={
        "messages": [{"role": "user", "content": "A seller refused my refund."}],
        "category": "consumer", "confirmed": True,
        "profile": {"counterparty": "Example merchant", "location": "Kanpur",
                    "event_date": "Not known", "desired_resolution": "Refund"},
    })
    assert letter.status_code == 200
