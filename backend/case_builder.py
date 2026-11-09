"""CaseWise Phase 2: explainable, reviewable civil-dispute case files.

This module organizes reported facts. It does NOT verify evidence or provide
legal findings. No case is stored on the server.
"""
from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from datetime import datetime
from typing import Any

from .engine import AMOUNT_PATTERN, clean, analyze, draft_narrative
from .evidence_recognition import extract_evidence
from .date_intake import reported_date_mentions, assess_event_date_reply, date_clarification_question
from .case_enrichment import (build_context, explicit_unknown_fields, structured_facts_summary,
                              event_kind, match_primary_question, EVENT_DATE_FOLLOWUP_PREFIX)

FIELD_LABELS = {
    "user_role": "Your role",
    "counterparty": "Other party",
    "location": "City / State",
    "key_event": "What happened",
    "event_date": "Relevant date",
    "amount": "Amount in dispute",
    "evidence": "Evidence status",
    "desired_resolution": "Requested resolution",
}
FIELD_ORDER = ("counterparty", "location", "event_date", "desired_resolution", "user_role", "key_event", "amount", "evidence")
COMPLETENESS_FIELDS = ("subtype", "counterparty", "location", "key_event", "event_date", "amount", "evidence", "desired_resolution")
QUESTIONS = {
    "subtype": "What is the specific problem: a deposit, defective product, unpaid salary, unpaid invoice, or something else?",
    "counterparty": "Who is the other party involved (for example, the landlord, seller, employer or client)?",
    "location": "In which city and state did this dispute take place?",
    "key_event": "What exactly happened? Please describe the key event in one or two sentences.",
    "event_date": "When did the key event happen? Give the date if known, or say you do not know.",
    "amount": "What amount is involved? If there is no money in dispute, say 'not applicable'.",
    "evidence": "Which documents or messages do you have? If you have none, please say so.",
    "desired_resolution": "What outcome are you asking for from the other party?",
    "user_role": "Are you the tenant, customer, employee, contractor, owner, or another party?",
}
SUBTYPES = {
    "property": [
        ("rental_deposit", "Rental deposit", r"deposit|security money"),
        ("eviction", "Possession or eviction", r"evict|possession|vacat"),
        ("repairs", "Property repairs", r"repair|leak|maintenance"),
        ("ownership", "Ownership / title", r"title deed|ownership|boundary|inherit"),
    ],
    "consumer": [
        ("refund", "Refund dispute", r"refund|return|money back"),
        ("defective_product", "Damaged or defective product", r"damage|broken|defect|faulty"),
        ("delivery", "Delivery issue", r"deliver|arriv|shipment"),
        ("service", "Service complaint", r"service|subscription"),
    ],
    "employment": [
        ("unpaid_salary", "Unpaid salary", r"salary|wages|payslip|unpaid"),
        ("final_settlement", "Final settlement", r"final settlement|resign|relieving"),
        ("contract_terms", "Employment terms", r"offer letter|employment contract"),
    ],
    "contract": [
        ("unpaid_invoice", "Unpaid invoice", r"invoice|unpaid|payment"),
        ("breach", "Contract performance", r"breach|failed to|deliverable"),
        ("advance", "Advance payment", r"advance|deposit"),
    ],
}
DATE_RE = re.compile(
    r"\b(?:\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}|20\d{2}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]20\d{2})\b",
    re.I,
)
RELATIVE_DATE_RE = re.compile(r"\b(?:yesterday|today|last month|last week|two weeks ago|three days ago|recently)\b", re.I)
EVIDENCE_TERMS = (
    ("invoice", r"\binvoices?\b"),
    ("receipt", r"\breceipts?\b"),
    ("agreement", r"\b(?:agreements?|rent agreements?|contracts?)\b"),
    ("payment record", r"\b(?:bank transfer|payment proof|bank statements?|transaction record)\b"),
    ("messages", r"\b(?:whatsapp|messages?|texts?|chats?)\b"),
    ("email", r"\bemails?\b"),
    ("photograph", r"\b(?:photos?|pictures?|photographs?)\b"),
    ("notice", r"\bnotices?\b"),
    ("payslip", r"\bpayslips?\b"),
)
UNKNOWN = ("", "unknown", "not known", "not sure", "unsure", "n/a?", "pending", "none given")


def _value(value: Any, limit: int = 350) -> str:
    return clean(value, limit)


def _present(value: str) -> bool:
    return bool(value.strip()) and value.lower().strip() not in UNKNOWN and not value.startswith("[")


def _message_refs(messages: list[dict], term: str) -> list[dict]:
    refs = []
    for number, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        content = _value(message.get("content"), 2000)
        if term and term.lower() in content.lower():
            refs.append({"message_index": number, "excerpt": content[:160]})
    return refs[:4]


def _date_sort(value: str) -> str | None:
    if not value:
        return None
    for fmt in ("%d %B %Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip().title(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _subtype(category: str, text: str, override: str = "") -> dict:
    rules = SUBTYPES.get(category, [])
    for code, label, _ in rules:
        if override == code:
            return {"code": code, "label": label, "status": "user_edited"}
    for code, label, pattern in rules:
        if re.search(pattern, text, re.I):
            return {"code": code, "label": label, "status": "suggested"}
    return {"code": "", "label": "Not yet specified", "status": "missing"}


# A timeline is for events, not every sentence in the chat. Deliberately
# conservative: false negatives can be added by the user; false positives
# (a party's name presented as an event) undermine trust.
EVENT_PATTERN = re.compile(
    r"\b(?:paid|purchased|bought|ordered|rented|signed|moved out|vacated|"
    r"handed over|delivered|arrived|received|returned|refunded|refus(?:e|es|ed|ing|al)|denied|"
    r"withheld|complain(?:ed|t)|contacted|emailed|sent|requested|"
    r"terminated|resigned|dismissed|fired|repaired|damaged|broke|"
    r"charged|deducted|issued|completed|supplied|cancelled|canceled|"
    r"stopped working|stopped functioning|ceased working|malfunctioned|"
    r"became unusable|broke down|developed a fault|did not work|"
    r"breached|overdue|defaulted|failed to pay|did not pay|not paid|"
    r"has not paid|have not paid|not returned|has not returned|"
    r"haven't returned|hasn't returned|did not return|"
    r"didn't return|not received|has not received|didn't receive|"
    r"hasn't received)\b", re.I
)
NON_EVENT_START = re.compile(
    r"^\s*(?:i\s+(?:want|wish|need|hope|would like|am seeking|have (?:the|an?|my|"
    r"copies of|proof of))\b|my\s+(?:goal|desired result)\b|"
    r"please\s+|could you\s+|what should\s+|how can\s+)", re.I
)


def _event_segments(messages: list[dict]) -> list[tuple[int, str, str]]:
    """Produce distinct candidate event clauses with their exact spoken dates."""
    found = []
    seen = set()
    for index, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        original = _value(message.get("content"), 2000)
        # Never attach a date from one act to another act connected with
        # 'and', 'but', or 'however'. Only split 'and' if BOTH parts have
        # independent event verbs, so compound descriptions stay intact.
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", original):
            for part in re.split(r"\s*,?\s*\b(?:but|however)\b\s+", sentence, flags=re.I):
                alternatives = re.split(r"\s+\band\b\s+", part, flags=re.I)
                clauses = (alternatives if len(alternatives) > 1
                           and sum(bool(EVENT_PATTERN.search(p)) for p in alternatives) >= 2
                           else [part])
                for clause in clauses:
                    segment = _value(clause, 420).strip(" .,:;")
                    if len(segment) < 8 or segment.endswith("?"):
                        continue
                    if NON_EVENT_START.search(segment) or not EVENT_PATTERN.search(segment):
                        continue
                    identity = re.sub(r"\s+", " ", segment).casefold()
                    if identity in seen:
                        continue
                    seen.add(identity)
                    mention = next(iter(reported_date_mentions(segment)), None)
                    date = str(mention["text"]) if mention else ""
                    if mention and mention["kind"] == "partial":
                        date += " (year not supplied)"
                    found.append((index, segment, date))
                    if len(found) >= 12:
                        return found
    return found


def _sort_events(events: list[dict]) -> list[dict]:
    """Only order by date when every event has an unambiguous calendar date.

    Otherwise keep the conversation order; unknown-date events cannot safely
    be placed on a chronological axis.
    """
    if events and all(_date_sort(event["date"]) for event in events):
        return sorted(events, key=lambda event: _date_sort(event["date"]))
    return events


def _timeline(messages: list[dict], ai: dict | None, edits: list[dict] | None) -> list[dict]:
    if edits is not None:
        valid = []
        for i, row in enumerate(edits[:14]):
            if not isinstance(row, dict):
                continue
            event = _value(row.get("event"), 500)
            if not event:
                continue
            date = _value(row.get("date"), 80)
            valid.append({
                "id": _value(row.get("id"), 70) or "edit-%d" % i,
                "date": date,
                "event": event,
                "event_kind": event_kind(event),
                "date_status": "explicit" if _date_sort(date) else "partial" if "year not supplied" in date else "relative_or_unknown",
                "status": "user_edited",
                "source_message": row.get("source_message") if isinstance(row.get("source_message"), int) else None,
                "source_excerpt": _value(row.get("source_excerpt"), 160),
            })
        return _sort_events(valid)

    events = []
    for n, (index, segment, date) in enumerate(_event_segments(messages)):
        events.append({
            "id": "m%d-e%d" % (index, n),
            "date": date,
            "event": segment,
            "event_kind": event_kind(segment),
            "date_status": "explicit" if _date_sort(date) else "partial" if "year not supplied" in date else "relative_or_unknown",
            "status": "reported",
            "source_message": index,
            "source_excerpt": _value(messages[index].get("content"), 160),
        })
    # If there are no user-identifiable events, show NO timeline rather than
    # smuggling potentially invented Gemini suggestions into a factual chronology.
    return _sort_events(events)


def _narrative_messages(messages: list[dict]) -> list[dict]:
    """Exclude short field-only follow-up answers from the general case narrative.

    They remain available to the corresponding structured field and source
    provenance, but should not become an awkward new sentence in the story.
    """
    cleaned = []
    for index, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        text = _value(message.get("content"), 2000)
        prev = messages[index - 1] if index else {}
        was_field_answer = (
            prev.get("role") == "assistant"
            and match_primary_question(prev.get("content"), QUESTIONS) is not None
        )
        field_answer = match_primary_question(prev.get("content"), QUESTIONS) if was_field_answer else None
        # A short answer to a date question is metadata about an event,
        # not a replacement for the user's factual case narrative.
        if was_field_answer and (
            (field_answer == "event_date" and len(text) < 320)
            or (len(text) < 140 and not EVENT_PATTERN.search(text))
        ):
            continue
        cleaned.append(message)
    return cleaned


def _evidence(messages: list[dict], edits: list[dict] | None) -> list[dict]:
    return extract_evidence(messages, edits)



def _issues(messages: list[dict], values: dict, resolved: set[str],
            timeline: list[dict] | None = None) -> list[dict]:
    text = "\n".join(_value(m.get("content"), 2000) for m in messages if m.get("role") == "user")
    amounts = sorted(set(m.group(1).replace(",", "") for m in AMOUNT_PATTERN.finditer(text)))
    issues = []
    if len(amounts) > 1:
        issues.append({
            "id": "amounts_vary",
            "type": "possible_conflict",
            "field": "amount",
            "message": "Different monetary amounts were mentioned. Confirm whether they refer to the same transaction.",
            "examples": amounts[:5],
        })
    elif amounts and _present(values.get("amount", "")):
        try:
            corrected = re.sub(r"[^0-9.]", "", values["amount"])
            if corrected and float(corrected) != float(amounts[0]):
                issues.append({
                    "id": "amount_edited",
                    "type": "possible_conflict",
                    "field": "amount",
                    "message": "The edited disputed amount differs from an amount mentioned in the conversation. Confirm the correction.",
                    "examples": [amounts[0], values["amount"]],
                })
        except ValueError:
            pass
    # Multiple calendar dates are normal (purchase, failure, complaint).
    # Flag only if two *similar descriptions of the same event* report
    # different dates. This is a clarification, never an automatic conflict.
    dated = [row for row in (timeline or []) if _date_sort(row.get("date", ""))]
    for index, first in enumerate(dated):
        for second in dated[index + 1:]:
            if _date_sort(first["date"]) == _date_sort(second["date"]):
                continue
            def identity(row):
                event_text = DATE_RE.sub(" ", row["event"]).casefold()
                event_text = re.sub(r"[^a-z0-9 ]", " ", event_text)
                event_text = re.sub(r"\b(?:on|at|the|a|an)\b", " ", event_text)
                return re.sub(r"\s+", " ", event_text).strip()
            left, right = identity(first), identity(second)
            if len(left) >= 18 and len(right) >= 18 and SequenceMatcher(None, left, right).ratio() >= 0.86:
                issues.append({
                    "id": "multiple_dates",
                    "type": "clarification",
                    "field": "event_date",
                    "message": "A similar event was reported with different dates. Check whether these are two separate events or a corrected date.",
                    "examples": [first["date"], second["date"]],
                })
                break
        if any(issue["id"] == "multiple_dates" for issue in issues):
            break
    # Contradictory claims are only suggestions for the user to clarify.
    # They may describe different dates, transactions or partial payments.
    statement_pairs = (
        ("refund_status", r"\b(?:i received|i got|seller refunded)\b.{0,25}\brefund\b",
         r"\b(?:not received|never received|did not receive|haven't received|no refund|refused (?:the )?refund)\b"),
        ("payment_status", r"\b(?:client|company|employer)\b.{0,35}\b(?:has paid|paid me|sent the payment)\b",
         r"\b(?:client|company|employer)\b.{0,35}\b(?:has not paid|didn't pay|refused to pay)\b"),
    )
    for issue_id, positive, negative in statement_pairs:
        if re.search(positive, text, re.I) and re.search(negative, text, re.I):
            issues.append({
                "id": "statement_" + issue_id,
                "type": "possible_conflict",
                "field": "key_event",
                "message": "Statements about payment or refund status appear different. Clarify whether these describe different events, a partial payment or a correction.",
                "examples": ["Different outcome statements were mentioned"],
            })
    return [{**issue, "resolved": issue["id"] in resolved} for issue in issues]


def build_case(
    messages: list[dict],
    profile: dict | None = None,
    category: str = "auto",
    ai: dict | None = None,
    *,
    case_overrides: dict | None = None,
    context_overrides: dict | None = None,
    timeline_edits: list[dict] | None = None,
    evidence_edits: list[dict] | None = None,
    asked_fields: list[str] | None = None,
    resolved_issues: list[str] | None = None,
    story_override: str = "",
    reviewed: bool = False,
    case_id: str = "",
) -> dict:
    """Rebuild a case on each call. Corrections win over suggestions; nothing persists."""
    ai_category = (ai or {}).get("category")
    effective_category = ai_category if category == "auto" and ai_category in SUBTYPES else category
    original = analyze(messages, profile, effective_category)
    chosen = original["summary"]["category"]
    text = "\n".join(_value(m.get("content"), 2000) for m in messages if m.get("role") == "user")
    base = original["profile_used"]
    overrides = {k: _value(v, 500) for k, v in (case_overrides or {}).items()
                 if k in FIELD_LABELS or k == "subtype"}
    narrative_messages = _narrative_messages(messages)
    # Prefer the actual disputed event to the entire chat story. Evidence,
    # requests for a remedy and party-name answers are separate fields.
    event_segments = _event_segments(messages)
    disputed = re.compile(
        r"\b(?:refused|denied|withheld|not returned|has not returned|"
        r"not paid|has not paid|unpaid|failed to|damaged|broken|breached|overdue)\b",
        re.I,
    )
    # Replies to date questions may mention a *different* event (such as
    # a complaint). Do not let those replies replace the original disputed
    # event or make their date the refusal / payment / eviction date.
    date_answer_indices = {
        i for i in range(1, len(messages))
        if messages[i].get("role") == "user"
        and messages[i - 1].get("role") == "assistant"
        and match_primary_question(messages[i - 1].get("content"), QUESTIONS) == "event_date"
    }
    core_events = [row for row in event_segments if row[0] not in date_answer_indices]
    chosen_events = core_events or event_segments
    central_event = next(
        (segment for _, segment, _ in reversed(chosen_events) if disputed.search(segment)),
        chosen_events[-1][1] if chosen_events else draft_narrative(narrative_messages),
    )
    fields = {
        "counterparty": base["counterparty"],
        "location": base["location"],
        "event_date": base["event_date"],
        "amount": base["amount"],
        "evidence": base["evidence"],
        "desired_resolution": base["desired_resolution"],
        "user_role": "",
        "key_event": _value(central_event, 500),
    }
    # Suggest user role only when straightforward, not an assertion of legal standing.
    role_patterns = [
        ("Tenant", r"\b(?:my landlord|i rent|as a tenant)\b"),
        ("Customer", r"\b(?:i purchased|i bought|i ordered|seller)\b"),
        ("Employee", r"\b(?:my employer|my salary|i resigned)\b"),
        ("Contractor", r"\b(?:my client|i completed the project|my invoice)\b"),
    ]
    for role, pattern in role_patterns:
        if re.search(pattern, text, re.I):
            fields["user_role"] = role
            break
    # Extract explicit dates and requested outcomes from user messages, never guess.
    if not fields["event_date"]:
        # Only the date attached to the selected key event may populate this
        # field. A purchase date must never silently become a refusal date.
        event_date = next(
            (row for row in reported_date_mentions(central_event) if row["kind"] != "partial"), None,
        )
        if event_date:
            fields["event_date"] = str(event_date["text"])
    if not fields["desired_resolution"]:
        wishes = re.findall(r"\b(?:i want|i request|i need)\s+([^.!?\n]{4,140})", text, re.I)
        for wish in reversed(wishes):
            if re.search(r"refund|deposit|payment|salary|replacement|repair|compensation|return|resolve", wish, re.I):
                fields["desired_resolution"] = _value(wish, 200)
                break
    # A short answer immediately following a CaseWise follow-up may fill that
    # specific missing field. Refuse long/general text as a field value.
    date_review: dict | None = None
    for i in range(1, len(messages)):
        previous = messages[i - 1]
        current = messages[i]
        if previous.get("role") != "assistant" or current.get("role") != "user":
            continue
        matching = match_primary_question(previous.get("content"), QUESTIONS)
        if not matching or matching not in fields or fields[matching] or matching in overrides:
            continue
        response = _value(current.get("content"), 300)
        if not response or response.endswith("?") or len(response) > (300 if matching == "event_date" else 130):
            continue
        if matching == "event_date":
            if response.strip().casefold() not in ("yes", "no", "okay", "ok") or date_review:
                date_review = assess_event_date_reply(response, central_event, date_review)
                if date_review["status"] == "accepted":
                    fields[matching] = date_review["value"]
        elif response.strip().lower() not in ("yes", "no", "okay", "ok"):
            if matching == "amount":
                detected = AMOUNT_PATTERN.search(response)
                fields[matching] = "₹" + detected.group(1) if detected else response if response.strip().lower() in ("not applicable", "n/a") else ""
            elif matching == "counterparty":
                fields[matching] = response if len(response.split()) <= 12 else ""
            elif matching in ("location", "desired_resolution", "user_role", "evidence", "key_event"):
                fields[matching] = response
    fields.update(overrides)
    # Empty default frontend fields must not convert user-reported facts into
    # user-confirmed edits. Only nonempty explicitly supplied values count.
    provided = {key for key, value in (profile or {}).items() if _present(str(value or ""))} | {
        key for key, value in overrides.items() if _present(value)
    }
    facts = {}
    for key, value in fields.items():
        source_phrase = value.replace(" (mentioned by user; availability unconfirmed)", "")
        facts[key] = {
            "value": value,
            "status": "user_edited" if key in provided and _present(value) else "reported" if _present(value) else "missing",
            "sources": _message_refs(messages, source_phrase) if key not in provided and _present(source_phrase) else [],
        }

    subtype = _subtype(chosen, text, overrides.get("subtype", ""))
    timeline = _timeline(messages, ai, timeline_edits)
    evidence = _evidence(messages, evidence_edits)
    context = build_context(chosen, subtype["code"], messages, context_overrides)
    unknown_fields = explicit_unknown_fields(messages, QUESTIONS)
    if evidence and not _present(fields["evidence"]):
        facts["evidence"]["value"] = ", ".join(item["type"] for item in evidence[:5])
        facts["evidence"]["status"] = "reported"
    issues = _issues(messages, fields, set(resolved_issues or []), timeline)

    # A case-completeness indicator measures filled factual fields, never case strength.
    checks = {
        "subtype": bool(subtype["code"]),
        "counterparty": _present(fields["counterparty"]),
        "location": _present(fields["location"]),
        "key_event": _present(fields["key_event"]),
        "event_date": bool(_date_sort(fields["event_date"])) or bool(RELATIVE_DATE_RE.search(fields["event_date"])),
        "amount": _present(fields["amount"]) or fields["amount"].strip().lower() in ("not applicable", "n/a"),
        "evidence": bool(evidence) or _present(fields["evidence"]) or fields["evidence"].strip().lower() in ("none available", "no evidence"),
        "desired_resolution": _present(fields["desired_resolution"]),
    }
    completed = sum(checks.values())
    missing = [{"key": key, "label": "Dispute subtype" if key == "subtype" else FIELD_LABELS.get(key, key)}
               for key, filled in checks.items() if not filled]
    # Handle unanswered questions: do not ask the same field again during a session.
    allowed_context = {"context:" + row["id"] for row in context["questions"]}
    asked = [key for key in (asked_fields or [])
             if key in QUESTIONS or key in allowed_context]
    unanswered = [item["key"] for item in missing if item["key"] not in unknown_fields]
    ordered_missing = [key for key in (
        "counterparty", "location", "event_date", "desired_resolution",
        "evidence", "amount", "subtype", "key_event", "user_role",
    ) if key in unanswered]
    # Asked is not answered: do not drop a missing field permanently just
    # because the question has already appeared in the chat.
    next_field = next((key for key in ordered_missing if key not in asked),
                      ordered_missing[0] if ordered_missing else None)
    question = QUESTIONS.get(next_field)
    if next_field == "event_date" and central_event:
        # Ask about the actual disputed event instead of silently equating
        # an earlier purchase, payment or failure date with its date.
        description = DATE_RE.sub("", _value(central_event, 160)).strip(" ,.;:")
        question = (date_clarification_question(description, date_review)
                    if date_review and date_review["status"] != "accepted"
                    else EVENT_DATE_FOLLOWUP_PREFIX + description
                    + "? If you do not know, say 'not known'.")
    # Additional issue-specific questions start only when the core intake is
    # answered (an explicitly unknown fact is an acknowledged answer).
    core_addressed = all(
        check or key in unknown_fields
        for key, check in checks.items()
    )
    if next_field is None and core_addressed and chosen != "other":
        outstanding_context = [row for row in context["questions"]
                               if row["status"] == "missing"]
        next_context = next(
            (row for row in outstanding_context if "context:" + row["id"] not in asked),
            outstanding_context[0] if outstanding_context else None,
        )
        if next_context:
            next_field = "context:" + next_context["id"]
            question = next_context["question"]
    if question is None:
        question = "I've noted the available information. Please review the case file and correct any missing or inconsistent details."

    story = _value(story_override, 1400) or _value((ai or {}).get("story_english"), 1400) or _value(draft_narrative(narrative_messages), 1400)
    if not story:
        story = "A factual account has not yet been provided."
    story_status = "user_edited" if story_override.strip() else "ai_suggested" if (ai or {}).get("story_english") else "reported"
    identity = _value(case_id, 48) or "CW-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:10].upper()
    compiled_summary = structured_facts_summary(original["summary"]["category_label"], subtype["label"], facts, evidence, context)

    return {
        "schema_version": "2.0",
        "case_id": identity,
        "category": chosen,
        "category_label": original["summary"]["category_label"],
        "subtype": subtype,
        "facts": facts,
        "timeline": timeline,
        "evidence": evidence,
        "context": context,
        "unknown_fields": unknown_fields,
        "date_clarification": date_review if date_review and date_review["status"] != "accepted" else None,
        "structured_summary": compiled_summary,
        "issues": issues,
        "missing": missing,
        "completeness": {
            "completed": completed, "total": 8, "percent": round(completed * 100 / 8),
            "checks": [{"key": k, "label": "Dispute subtype" if k == "subtype" else FIELD_LABELS.get(k, k), "complete": bool(v)}
                       for k, v in checks.items()],
            "description": "Information collected, not legal merit, advice or filing readiness.",
        },
        "next_question": {"field": next_field, "text": question},
        "asked_fields": asked,
        "narrative": {"text": story, "status": story_status, "reviewed": bool(reviewed)},
        "review": {
            "confirmed": bool(reviewed),
            "unresolved_issues": sum(not item["resolved"] for item in issues),
            "disclaimer": "Reported case information only. Documents and allegations have not been independently verified.",
        },
        "risk_flag": "urgent_or_criminal" if original["needs_lawyer"] or (ai or {}).get("risk_flag") in ("urgent", "criminal") else "none",
        "evidence_uploaded": False,
    }
