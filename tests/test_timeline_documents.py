"""Regression checks for reported-event timelines and visible document choices."""
import pytest

from backend.case_builder import build_case
from backend.engine import make_draft


def make_chat(*statements):
    return [{"role": "user", "content": statement} for statement in statements]


def sample_messages():
    return [
        {"role": "assistant", "content": "Hello! Tell me about your civil dispute."},
        {"role": "user", "content": (
            "I paid my landlord a ₹30,000 security deposit when I rented an apartment in Kanpur. "
            "I moved out on 5 October 2026, but my landlord has not returned the deposit. "
            "I have the rental agreement, bank transfer receipt and WhatsApp messages. "
            "I want my full deposit back."
        )},
        {"role": "assistant", "content": "Who is the other party involved (for example, the landlord, seller, employer or client)?"},
        {"role": "user", "content": "sweet home owner dev"},
    ]


def test_user_uploaded_case_story_produces_three_relevant_events_only():
    result = build_case(sample_messages())
    events = result["timeline"]
    assert len(events) == 3, [event["event"] for event in events]
    assert "paid my landlord" in events[0]["event"].lower()
    assert events[0]["date"] == ""
    assert "moved out" in events[1]["event"].lower()
    assert events[1]["date"] == "5 October 2026"
    assert "not returned" in events[2]["event"].lower()
    assert events[2]["date"] == ""
    assert not any("rental agreement" in e["event"].lower() for e in events)
    assert not any("want my full" in e["event"].lower() for e in events)
    assert not any("sweet home" in e["event"].lower() for e in events)
    assert all(e["status"] == "reported" and e["source_message"] == 1 for e in events)


def test_short_answer_fills_other_party_but_does_not_pollute_case_story():
    result = build_case(sample_messages())
    assert result["facts"]["counterparty"]["value"] == "sweet home owner dev"
    assert "sweet home owner dev" not in result["narrative"]["text"]
    assert "not returned" in result["facts"]["key_event"]["value"].lower()
    assert "whatsapp" not in result["facts"]["key_event"]["value"].lower()
    assert result["subtype"]["code"] == "rental_deposit"


def test_only_evidence_and_desired_outcome_are_not_timeline_events():
    case = build_case(make_chat(
        "I have the rental agreement, bank-transfer receipt, and WhatsApp messages.",
        "I want a refund of my deposit.",
        "My landlord's name is Sam Example."
    ))
    assert case["timeline"] == []


def test_separate_calendar_dates_sort_when_both_known():
    case = build_case(make_chat(
        "I complained on 12 October 2026.",
        "I paid the invoice on 1 October 2026.",
    ))
    assert [e["date"] for e in case["timeline"]] == ["1 October 2026", "12 October 2026"]


def test_conversation_order_kept_when_some_event_dates_are_unknown():
    case = build_case(make_chat(
        "I signed the agreement.",
        "I moved out on 5 October 2026.",
        "The landlord has not returned my deposit.",
    ))
    assert [e["date"] for e in case["timeline"]] == ["", "5 October 2026", ""]


def reviewed_profile():
    return {
        "counterparty": "Example Seller", "location": "Kanpur",
        "event_date": "5 October 2026", "amount": "₹30,000",
        "desired_resolution": "Full refund", "evidence": "receipt",
        "facts_narrative": "I purchased a damaged product. I have the receipt.",
    }


@pytest.mark.parametrize("draft_type,heading", [
    ("request", "DRAFT REQUEST FOR RESOLUTION"),
    ("notice", "DRAFT NOTICE OUTLINE - LAWYER REVIEW REQUIRED"),
    ("complaint", "DRAFT COMPLAINT - CHECK RECIPIENT AND PROCEDURE"),
    ("reply", "DRAFT REPLY - LAWYER REVIEW ADVISED"),
    ("application", "DRAFT APPLICATION FOR ASSISTANCE"),
])
def test_all_five_document_drafts_remain_available(draft_type, heading):
    result = make_draft(
        make_chat("I purchased a damaged product and the seller refused my refund."),
        reviewed_profile(), category="consumer", confirmed=True, document_type=draft_type,
    )
    assert heading in result
    assert "not a court filing" in result.lower()
    if draft_type in ("application", "complaint"):
        assert "To: [Relevant office or authority - verify before use]" in result
        assert "Party concerned: Example Seller" in result
    else:
        assert "To: Example Seller" in result


def test_explicit_authority_recipient_overrides_placeholder_without_changing_opposing_party():
    profile = reviewed_profile()
    profile["recipient_name"] = "Example Grievance Office"
    result = make_draft(
        make_chat("I purchased a damaged product and the seller refused my refund."),
        profile, category="consumer", confirmed=True, document_type="complaint",
    )
    assert "To: Example Grievance Office" in result
    assert "Party concerned: Example Seller" in result


def test_unreviewed_or_urgent_notice_cannot_be_generated():
    with pytest.raises(ValueError, match="Review"):
        make_draft(make_chat("The seller denied my refund."), reviewed_profile(), confirmed=False, document_type="notice")
    with pytest.raises(ValueError, match="disabled"):
        make_draft(make_chat("I have a court hearing tomorrow"), reviewed_profile(), confirmed=True, document_type="reply")
