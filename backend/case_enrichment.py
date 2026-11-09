"""Cross-category follow-up questions and fact-only case summary building."""
from __future__ import annotations

import re
from typing import Any

from .case_policy import get_case_policy

UNKNOWN_ANSWERS = {
    "unknown", "not known", "not sure", "unsure", "i don't know",
    "i do not know", "don't know", "do not know", "none known",
    "not available", "i cannot remember", "can't remember",
}


def _sanitize(value: Any, limit: int = 500) -> str:
    return re.sub(r"[\x00-\x1f]", " ", str(value or "")).strip()[:limit]


def answer_status(value: str) -> str:
    if not value:
        return "missing"
    return "not_known" if value.strip().casefold().strip(". ") in UNKNOWN_ANSWERS else "reported"


EVENT_DATE_FOLLOWUP_PREFIX = "When did this reported event happen: "


def match_primary_question(question: str, primary_questions: dict[str, str]) -> str | None:
    """Recognize standard or event-specific questions without guessing a field."""
    normalized = _sanitize(question, 550)
    for field, template in primary_questions.items():
        if normalized == template:
            return field
    if normalized.startswith(EVENT_DATE_FOLLOWUP_PREFIX) and normalized.endswith("If you do not know, say 'not known'."):
        return "event_date"
    return None


def build_context(
    category: str, subtype: str, messages: list[dict],
    overrides: dict[str, str] | None = None,
) -> dict:
    """Record explicit answers to category/subtype prompts without model guesses."""
    policy = get_case_policy(category, subtype)
    rows = []
    entered = overrides if isinstance(overrides, dict) else {}
    for item in policy["detail_questions"]:
        identifier = item["id"]
        response = ""
        source_message = None
        for index in range(1, len(messages)):
            prior = messages[index - 1]
            current = messages[index]
            if prior.get("role") != "assistant" or current.get("role") != "user":
                continue
            if _sanitize(prior.get("content"), 550) != item["question"]:
                continue
            response = _sanitize(current.get("content"), 500)
            source_message = index
        if identifier not in entered and not response:
            # Reuse only a sentence actually supplied by the user and matching
            # the curated subject-specific pattern. No LLM guesses or implied
            # contract terms are treated as evidence.
            patterns = item.get("source_patterns", [])
            for index, message in enumerate(messages):
                if message.get("role") != "user":
                    continue
                for sentence in re.split(r"(?<=[.!?])\s+|\n+", _sanitize(message.get("content"), 2000)):
                    snippet = _sanitize(sentence, 330)
                    if len(snippet) > 12 and any(re.search(pattern, snippet, re.I)
                                                 for pattern in patterns):
                        response = snippet
                        source_message = index
                        break
                if response:
                    break
        if identifier in entered:
            # An explicit correction, including a deliberate blank, wins.
            response = _sanitize(entered[identifier])
            source_message = None
        status = answer_status(response)
        rows.append({
            "id": identifier, "label": item["label"], "question": item["question"],
            "purpose": item["purpose"], "answer": response,
            "status": "user_edited" if identifier in entered and response
                      else status,
            "source_message": source_message,
        })
    return {
        "questions": rows,
        "answered": sum(row["status"] not in ("missing",) for row in rows),
        "total": len(rows),
        "description": "Optional factual questions; answers may be unknown and are not legal findings.",
    }


def explicit_unknown_fields(messages: list[dict], primary_questions: dict[str, str]) -> list[str]:
    """Recognize an explicit 'I don't know', not merely that a question was asked."""
    unknown = set()
    for i in range(1, len(messages)):
        before, after = messages[i-1], messages[i]
        if before.get("role") != "assistant" or after.get("role") != "user":
            continue
        response = _sanitize(after.get("content"), 120)
        field = match_primary_question(before.get("content"), primary_questions)
        if field:
            if answer_status(response) == "not_known":
                unknown.add(field)
            else:
                unknown.discard(field)
    return sorted(unknown)


def structured_facts_summary(category_label: str, subtype_label: str,
                             facts: dict, evidence: list[dict],
                             context: dict) -> dict:
    """Compose a plain-language fact ledger; no invented acts or case merits."""
    labels = [
        ("user_role", "User's reported role"),
        ("counterparty", "Reported other party"),
        ("location", "Reported location"),
        ("key_event", "Reported event"),
        ("event_date", "Reported relevant date"),
        ("amount", "Reported disputed amount"),
        ("desired_resolution", "Requested outcome"),
    ]
    items = [
        {"key": "category", "label": "Issue type", "value": subtype_label or category_label}
    ]
    for key, label in labels:
        value = _sanitize(facts.get(key, {}).get("value"), 350)
        if value and value.casefold() not in ("unknown", "not known", "n/a"):
            items.append({"key": key, "label": label, "value": value})
    if evidence:
        recorded = [
            item["description"] for item in evidence
            if item.get("availability") in ("user_says_available", "mentioned")
        ]
        if recorded:
            items.append({"key": "evidence", "label": "Reported supporting material",
                          "value": ", ".join(recorded[:8])})
    for question in context.get("questions", []):
        if question.get("status") not in ("missing",) and question.get("answer"):
            items.append({"key": "context:" + question["id"], "label": question["label"],
                          "value": question["answer"]})
    # This text is a structured collection of *reported facts*, not an
    # unreviewed paraphrase claiming that a legal case was established.
    text = " | ".join(f"{item['label']}: {item['value']}" for item in items)
    values = {item["key"]: item["value"] for item in items}
    narrative = ["The user reports an issue categorized as " + values["category"] + "."]
    ordered = (
        ("user_role", "Reported role"),
        ("counterparty", "Other party"),
        ("location", "Reported location"),
        ("key_event", "Reported event"),
        ("event_date", "Reported relevant date"),
        ("amount", "Reported disputed amount"),
        ("desired_resolution", "Requested outcome"),
        ("evidence", "User-mentioned supporting material (not independently checked)"),
    )
    for key, label in ordered:
        if values.get(key):
            narrative.append(label + ": " + values[key].rstrip(" .") + ".")
    for item in items:
        if item["key"].startswith("context:"):
            narrative.append("Additional reported detail (" + item["label"] + "): "
                             + item["value"].rstrip(" .") + ".")
    narrative.append("These statements are user-reported and have not been independently verified.")
    return {
        "items": items,
        "narrative": " ".join(narrative)[:3200],
        "text": text[:3200],
        "status": "compiled_from_reported_fields",
        "disclaimer": "Compiled from user-provided statements; completeness does not verify accuracy or legal merit.",
    }


def event_kind(text: str) -> str:
    """Label ongoing reported conditions rather than silently merge events."""
    if re.search(r"\b(?:refused|denied|served|delivered|sent|paid|issued|requested|replied)\b", text, re.I):
        return "event"
    if re.search(r"\b(?:has not|have not|did not|not received|not returned|unpaid|remains|still)\b", text, re.I):
        return "ongoing_status"
    return "event"
