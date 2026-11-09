"""Regression cases for data-driven intake, event chronology and export clarity.

Business names and amounts here are *test fixtures*, never extraction rules.
"""
from io import BytesIO
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.case_builder import build_case, QUESTIONS
from backend.main import app

client = TestClient(app)

BUYER_STORY = (
    "I purchased a laptop from TechZone Electronics for ₹55,000 on 10 October 2026 "
    "in Hyderabad, Telangana. The laptop stopped working on 18 October 2026. "
    "The seller refused to provide a refund or replacement. "
    "I have the purchase invoice, payment receipt, and email conversations "
    "with the seller. I want a full refund."
)


def user(value):
    return [{"role": "user", "content": value}]


def test_complete_initial_consumer_story_extracts_party_and_full_location():
    case = build_case(user(BUYER_STORY))
    assert case["category"] == "consumer"
    assert case["facts"]["counterparty"]["value"] == "TechZone Electronics"
    assert case["facts"]["counterparty"]["status"] == "reported"
    assert case["facts"]["counterparty"]["sources"]
    assert case["facts"]["location"]["value"] == "Hyderabad, Telangana"
    assert case["facts"]["location"]["sources"]
    assert case["facts"]["amount"]["value"] == "₹55,000"
    assert case["facts"]["desired_resolution"]["value"] == "a full refund"
    assert case["completeness"]["completed"] == 7
    assert case["next_question"]["field"] == "event_date"
    assert "The seller refused to provide a refund or replacement" in case["next_question"]["text"]


def test_multiple_events_keep_the_correct_dates_and_missing_refusal_date():
    case = build_case(user(BUYER_STORY))
    assert len(case["timeline"]) == 3
    assert [row["date"] for row in case["timeline"]] == [
        "10 October 2026", "18 October 2026", "",
    ]
    assert "purchased" in case["timeline"][0]["event"]
    assert "stopped working" in case["timeline"][1]["event"]
    assert "refused" in case["timeline"][2]["event"]
    assert case["facts"]["event_date"]["value"] == ""
    assert not any(issue["id"] == "multiple_dates" for issue in case["issues"])


def test_date_is_not_promoted_across_actions_and_can_be_confirmed_by_user():
    case = build_case(user(BUYER_STORY), profile={"event_date": "22 October 2026"})
    assert case["facts"]["event_date"]["value"] == "22 October 2026"
    assert case["facts"]["event_date"]["status"] == "user_edited"
    assert [event["date"] for event in case["timeline"]] == [
        "10 October 2026", "18 October 2026", "",
    ]


def test_optional_questions_reuse_already_stated_purchase_and_response():
    case = build_case(user(BUYER_STORY))
    context = {item["id"]: item for item in case["context"]["questions"]}
    assert "purchased a laptop" in context["consumer_purchase"]["answer"]
    assert context["consumer_purchase"]["status"] == "reported"
    assert "refused to provide" in context["consumer_contact"]["answer"]
    assert context["consumer_contact"]["status"] == "reported"
    assert context["consumer_refund_terms"]["status"] == "missing"


def test_an_unanswered_asked_field_is_not_silently_dropped():
    messages = user("The seller refused to return my payment.")
    after_first_ask = build_case(messages, asked_fields=["counterparty"])
    assert after_first_ask["facts"]["counterparty"]["status"] == "missing"
    assert after_first_ask["next_question"]["field"] in {x["key"] for x in after_first_ask["missing"]}
    # Once every missing question has been asked, an outstanding question
    # remains present rather than becoming "everything has been collected".
    case = build_case(messages, asked_fields=list(QUESTIONS))
    assert case["next_question"]["field"] == "counterparty"
    assert case["next_question"]["text"] == QUESTIONS["counterparty"]


def test_chat_answer_recovers_party_even_if_text_was_not_initially_detected():
    story = "I purchased a laptop in Mumbai and need a refund from the seller."
    messages = [
        *user(story),
        {"role": "assistant", "content": QUESTIONS["counterparty"]},
        {"role": "user", "content": "Nova Digital Store"},
    ]
    case = build_case(messages, asked_fields=["counterparty"])
    assert case["facts"]["counterparty"]["value"] == "Nova Digital Store"
    assert case["next_question"]["field"] != "counterparty"


@pytest.mark.parametrize("story,expected_category,expected_party", [
    ("I paid my landlord Silver Grove Properties a ₹20,000 rental deposit, but it was not returned.",
     "property", "Silver Grove Properties"),
    ("My employer Aurora Systems has not paid my salary for October.",
     "employment", "Aurora Systems"),
    ("My client Horizon Studio has not paid my invoice for the completed project.",
     "contract", "Horizon Studio"),
    ("I bought a monitor from Galaxy Retailers for ₹15,000. The seller denied my refund.",
     "consumer", "Galaxy Retailers"),
])
def test_category_independent_named_entity_extraction(story, expected_category, expected_party):
    case = build_case(user(story))
    assert case["category"] == expected_category
    assert case["facts"]["counterparty"]["value"] == expected_party


def test_generic_roles_are_not_promoted_to_named_parties():
    for story in (
        "The seller refused to refund my purchase.",
        "My landlord has not returned my security deposit.",
        "My employer refused to pay my salary.",
        "My client did not pay my invoice.",
    ):
        assert not build_case(user(story))["facts"]["counterparty"]["value"]


def test_explicit_city_and_state_but_no_city_to_state_guessing():
    assert build_case(user("I bought a faulty monitor in Mysuru, Karnataka."))["facts"]["location"]["value"] == "Mysuru, Karnataka"
    assert build_case(user("I bought a faulty monitor in Kanpur."))["facts"]["location"]["value"] == "Kanpur"


def test_same_action_with_two_different_dates_is_a_clarification_not_a_fact():
    story = ("The seller refused my refund on 18 October 2026. "
             "The seller refused my refund on 19 October 2026.")
    case = build_case(user(story))
    flag = next(i for i in case["issues"] if i["id"] == "multiple_dates")
    assert flag["type"] == "clarification"
    assert flag["resolved"] is False


def test_reviewed_pdf_is_compact_and_json_reflects_corrected_extraction():
    payload = {
        "messages": user(BUYER_STORY),
        "reviewed": True,
        "story_override": BUYER_STORY,
        "export_format": "json",
    }
    j = client.post("/api/case-export", json=payload)
    assert j.status_code == 200, j.text
    result = j.json()
    assert result["facts"]["counterparty"]["value"] == "TechZone Electronics"
    assert result["facts"]["location"]["value"] == "Hyderabad, Telangana"
    assert result["facts"]["event_date"]["value"] == ""
    assert len(result["timeline"]) == 3
    assert result["issues"] == []

    pdf = client.post("/api/case-export", json={**payload, "export_format": "pdf"})
    assert pdf.status_code == 200, pdf.text
    pages = PdfReader(BytesIO(pdf.content)).pages
    text = "\n".join(page.extract_text() for page in pages)
    assert len(pages) <= 2
    assert text.count("Reviewed case narrative") == 1
    assert text.count("Compiled reported facts") == 1
    assert "TechZone Electronics" in text
    assert "Hyderabad, Telangana" in text
    assert "Date unknown" in text
    assert "18 October 2026" in text
    assert "not independently verified" in text.lower()


def test_legal_plan_intake_follows_actual_missing_fact():
    data = client.post("/api/analyze", json={"messages": user(BUYER_STORY)})
    assert data.status_code == 200, data.text
    result = data.json()
    assert result["case_file"]["next_question"]["field"] == "event_date"
    assert result["legal_plan"]["stage"]["code"] == "preliminary"  # Main facts known; refusal date still needs clarification.
    assert "event_date" in result["legal_plan"]["stage"]["missing_followups"]



def test_date_question_identifies_event_and_accepts_reply_without_polluting_story():
    initial = build_case(user(BUYER_STORY))
    conversation = [
        *user(BUYER_STORY),
        {"role": "assistant", "content": initial["next_question"]["text"]},
        {"role": "user", "content": "22 October 2026"},
    ]
    updated = build_case(conversation, asked_fields=["event_date"])
    assert updated["facts"]["event_date"]["value"] == "22 October 2026"
    assert updated["next_question"]["field"] != "event_date"
    assert "22 October 2026" not in updated["narrative"]["text"]


def test_unknown_event_date_is_recorded_as_unknown_not_fabricated():
    initial = build_case(user(BUYER_STORY))
    conversation = [
        *user(BUYER_STORY),
        {"role": "assistant", "content": initial["next_question"]["text"]},
        {"role": "user", "content": "I don't know"},
    ]
    updated = build_case(conversation, asked_fields=["event_date"])
    assert "event_date" in updated["unknown_fields"]
    assert updated["facts"]["event_date"]["value"] == ""
    assert updated["next_question"]["field"] != "event_date"



def test_ambiguous_yearless_complaint_date_is_not_assigned_to_refusal():
    initial = build_case(user(BUYER_STORY))
    question = initial["next_question"]["text"]
    messages = [
        *user(BUYER_STORY),
        {"role": "assistant", "content": question},
        {"role": "user", "content": "I complaint on October 20 and salary refuse to provide a refund your replacement"},
    ]
    case = build_case(messages, asked_fields=["event_date"])
    assert case["facts"]["event_date"]["value"] == ""
    assert case["completeness"]["completed"] == 7
    assert case["date_clarification"]["candidate"] == "20 October"
    assert case["date_clarification"]["status"] == "different_event"
    assert "20 October" in case["next_question"]["text"]
    assert case["next_question"]["text"] != question
    assert case["facts"]["key_event"]["value"] == "The seller refused to provide a refund or replacement"
    assert case["narrative"]["text"] == BUYER_STORY
    assert any(row["date_status"] == "partial" for row in case["timeline"])
    assert not any(row["date"] == "20 October 2026" for row in case["timeline"])


@pytest.mark.parametrize("different_event", [
    "I complained on 20 October 2026.",
    "I sent a reminder on 20 October 2026.",
    "I complained on 20 October 2026 and the seller refused to refund.",
])
def test_date_of_separate_action_is_not_assumed_to_date_key_event(different_event):
    case = build_case([
        *user(BUYER_STORY),
        {"role": "assistant", "content": build_case(user(BUYER_STORY))["next_question"]["text"]},
        {"role": "user", "content": different_event},
    ], asked_fields=["event_date"])
    assert case["facts"]["event_date"]["value"] == ""
    assert case["date_clarification"]["status"] == "different_event"


def test_unambiguous_month_first_full_year_answer_is_accepted():
    initial = build_case(user(BUYER_STORY))
    case = build_case([
        *user(BUYER_STORY),
        {"role": "assistant", "content": initial["next_question"]["text"]},
        {"role": "user", "content": "October 20, 2026"},
    ], asked_fields=["event_date"])
    assert case["facts"]["event_date"]["value"] == "20 October 2026"
    assert case["completeness"]["completed"] == 8
    assert case["next_question"]["field"] != "event_date"


def test_partial_date_and_year_followup_resolve_without_year_inference():
    initial = build_case(user(BUYER_STORY))
    messages = [
        *user(BUYER_STORY),
        {"role": "assistant", "content": initial["next_question"]["text"]},
        {"role": "user", "content": "October 20"},
    ]
    intermediate = build_case(messages, asked_fields=["event_date"])
    assert intermediate["date_clarification"]["status"] == "partial_year"
    assert intermediate["facts"]["event_date"]["value"] == ""
    assert "year is not confirmed" in intermediate["next_question"]["text"]
    messages += [
        {"role": "assistant", "content": intermediate["next_question"]["text"]},
        {"role": "user", "content": "2026"},
    ]
    final = build_case(messages, asked_fields=["event_date"])
    assert final["facts"]["event_date"]["value"] == "20 October 2026"
    assert final["next_question"]["field"] != "event_date"
    assert final["narrative"]["text"] == BUYER_STORY  # A short field reply never rewrites the story.


def test_complaint_date_confirmed_as_refusal_date_only_after_yes():
    initial = build_case(user(BUYER_STORY))
    messages = [
        *user(BUYER_STORY),
        {"role": "assistant", "content": initial["next_question"]["text"]},
        {"role": "user", "content": "I complained on 20 October 2026"},
    ]
    intermediate = build_case(messages, asked_fields=["event_date"])
    assert intermediate["facts"]["event_date"]["value"] == ""
    assert intermediate["date_clarification"]["status"] == "different_event"
    messages += [
        {"role": "assistant", "content": intermediate["next_question"]["text"]},
        {"role": "user", "content": "Yes"},
    ]
    final = build_case(messages, asked_fields=["event_date"])
    assert final["facts"]["event_date"]["value"] == "20 October 2026"
    assert final["completeness"]["completed"] == 8


def test_two_distinct_dates_in_reply_selects_date_for_matching_action():
    initial = build_case(user(BUYER_STORY))
    case = build_case([
        *user(BUYER_STORY),
        {"role": "assistant", "content": initial["next_question"]["text"]},
        {"role": "user", "content": "I complained on 20 October 2026 and the seller refused on 21 October 2026."},
    ], asked_fields=["event_date"])
    assert case["facts"]["event_date"]["value"] == "21 October 2026"
    assert case["facts"]["key_event"]["value"] == "The seller refused to provide a refund or replacement"


def test_other_categories_receive_adaptive_yearless_date_clarification():
    examples = [
        "My landlord refused to return my security deposit.",
        "My employer refused to pay my salary.",
        "My client refused to pay my invoice.",
    ]
    for story in examples:
        initial = build_case(user(story))
        question = initial["next_question"]
        # Answering for every category doesn't create an invented year.
        if question["field"] != "event_date":
            # The other required facts may be missing; supply them as edits.
            profile = {"counterparty": "Other party", "location": "Delhi",
                       "desired_resolution": "Payment requested", "amount": "₹1000"}
            initial = build_case(user(story), profile=profile)
            question = initial["next_question"]
        assert question["field"] == "event_date"
        answered = build_case([
            *user(story),
            {"role": "assistant", "content": question["text"]},
            {"role": "user", "content": "20 October"},
        ], profile={"counterparty": "Other party", "location": "Delhi",
                    "desired_resolution": "Payment requested", "amount": "₹1000"},
           asked_fields=["event_date"])
        assert answered["facts"]["event_date"]["value"] == ""
        assert answered["date_clarification"]["status"] == "partial_year"
        assert "year" in answered["next_question"]["text"]


def test_unknown_answer_after_date_clarification_does_not_loop():
    initial = build_case(user(BUYER_STORY))
    messages = [
        *user(BUYER_STORY),
        {"role": "assistant", "content": initial["next_question"]["text"]},
        {"role": "user", "content": "I complained on October 20"},
    ]
    intermediate = build_case(messages, asked_fields=["event_date"])
    messages += [
        {"role": "assistant", "content": intermediate["next_question"]["text"]},
        {"role": "user", "content": "not known"},
    ]
    final = build_case(messages, asked_fields=["event_date"])
    assert "event_date" in final["unknown_fields"]
    assert final["next_question"]["field"] != "event_date"
