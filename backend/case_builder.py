"""CaseWise Phase 2: explainable, reviewable civil-dispute case files.

This module organizes reported facts. It does NOT verify evidence or provide
legal findings. No case is stored on the server.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from .engine import AMOUNT_PATTERN, clean, analyze, draft_narrative

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
                "date_status": "explicit" if _date_sort(date) else "relative_or_unknown",
                "status": "user_edited",
                "source_message": row.get("source_message") if isinstance(row.get("source_message"), int) else None,
                "source_excerpt": _value(row.get("source_excerpt"), 160),
            })
        return sorted(valid, key=lambda e: (not bool(_date_sort(e["date"])), _date_sort(e["date"]) or "", e["id"]))

    events = []
    for index, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        text = _value(message.get("content"), 2000)
        for piece in re.split(r"(?<=[.!?])\s+|\n+", text):
            segment = _value(piece, 420)
            if len(segment) < 16 or segment.endswith("?") or segment.lower().startswith(("what should", "how can", "please help")):
                continue
            match = DATE_RE.search(segment) or RELATIVE_DATE_RE.search(segment)
            date = match.group(0) if match else ""
            events.append({
                "id": "m%d-e%d" % (index, len(events)),
                "date": date,
                "event": segment,
                "date_status": "explicit" if _date_sort(date) else "relative_or_unknown",
                "status": "reported",
                "source_message": index,
                "source_excerpt": text[:160],
            })
            if len(events) >= 12:
                break
        if len(events) >= 12:
            break
    # AI may suggest an event, but only as an explicitly unverified item.
    if not events and ai:
        for i, item in enumerate((ai.get("timeline") or [])[:4]):
            if isinstance(item, dict) and _value(item.get("event")):
                events.append({
                    "id": "suggestion-%d" % i,
                    "date": _value(item.get("date"), 80),
                    "event": _value(item.get("event"), 420),
                    "date_status": "unverified",
                    "status": "ai_suggested",
                    "source_message": None,
                    "source_excerpt": "",
                })
    return sorted(events, key=lambda e: (not bool(_date_sort(e["date"])), _date_sort(e["date"]) or "", e["id"]))


def _evidence(messages: list[dict], edits: list[dict] | None) -> list[dict]:
    if edits is not None:
        result = []
        for i, row in enumerate(edits[:18]):
            if not isinstance(row, dict) or not _value(row.get("description")):
                continue
            status = row.get("availability")
            result.append({
                "id": _value(row.get("id"), 60) or "evidence-edit-%d" % i,
                "type": _value(row.get("type"), 60) or "Other",
                "description": _value(row.get("description"), 300),
                "availability": status if status in ("mentioned", "user_says_available", "user_says_unavailable", "unknown") else "unknown",
                "verified": False,
                "source_message": row.get("source_message") if isinstance(row.get("source_message"), int) else None,
                "source_excerpt": _value(row.get("source_excerpt"), 160),
            })
        return result

    found = {}
    for index, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        content = _value(message.get("content"), 2000)
        for name, regex in EVIDENCE_TERMS:
            if not re.search(regex, content, re.I):
                continue
            local_context = content
            unavailable = bool(re.search(r"\b(?:lost|do not have|don't have|no)\b.{0,24}" + regex.replace(r"\b", ""), local_context, re.I))
            has = bool(re.search(r"\b(?:i have|i've got|i possess|i kept|i saved)\b", local_context, re.I))
            found[name] = {
                "id": "evidence-" + name.replace(" ", "-"),
                "type": name.title(),
                "description": name.title() + " mentioned in the conversation",
                "availability": "user_says_unavailable" if unavailable else "user_says_available" if has else "mentioned",
                "verified": False,
                "source_message": index,
                "source_excerpt": content[:160],
            }
    return list(found.values())[:18]


def _issues(messages: list[dict], values: dict, resolved: set[str]) -> list[dict]:
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
    dates = sorted(set(match.group(0) for match in DATE_RE.finditer(text)))
    if len(dates) > 1:
        issues.append({
            "id": "multiple_dates",
            "type": "clarification",
            "field": "event_date",
            "message": "Several dates appear in the story. Confirm which date belongs to the key event; different dates do not automatically conflict.",
            "examples": dates[:5],
        })
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
    fields = {
        "counterparty": base["counterparty"],
        "location": base["location"],
        "event_date": base["event_date"],
        "amount": base["amount"],
        "evidence": base["evidence"],
        "desired_resolution": base["desired_resolution"],
        "user_role": "",
        "key_event": _value(draft_narrative(messages), 500),
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
        dates = DATE_RE.findall(text)
        if dates:
            fields["event_date"] = dates[-1]
    if not fields["desired_resolution"]:
        wishes = re.findall(r"\b(?:i want|i request|i need)\s+([^.!?\n]{4,140})", text, re.I)
        for wish in reversed(wishes):
            if re.search(r"refund|deposit|payment|salary|replacement|repair|compensation|return|resolve", wish, re.I):
                fields["desired_resolution"] = _value(wish, 200)
                break
    # A short answer immediately following a CaseWise follow-up may fill that
    # specific missing field. Refuse long/general text as a field value.
    for i in range(1, len(messages)):
        previous = messages[i - 1]
        current = messages[i]
        if previous.get("role") != "assistant" or current.get("role") != "user":
            continue
        question = _value(previous.get("content"), 500).lower()
        response = _value(current.get("content"), 300)
        if len(response) > 130 or response.endswith("?") or response.strip().lower() in ("yes", "no", "okay", "ok"):
            continue
        matching = next((key for key, template in QUESTIONS.items() if template.lower() == question), None)
        if not matching or matching not in fields or fields[matching] or matching in overrides:
            continue
        if matching == "event_date":
            detected = DATE_RE.search(response) or RELATIVE_DATE_RE.search(response)
            fields[matching] = detected.group(0) if detected else ""
        elif matching == "amount":
            detected = AMOUNT_PATTERN.search(response)
            fields[matching] = "₹" + detected.group(1) if detected else response if response.strip().lower() in ("not applicable", "n/a") else ""
        elif matching == "counterparty":
            fields[matching] = response if len(response.split()) <= 12 else ""
        elif matching in ("location", "desired_resolution", "user_role", "evidence", "key_event"):
            fields[matching] = response
    fields.update(overrides)
    # A field is user-entered when explicitly provided in an editable form.
    provided = set((profile or {}).keys()) | set(overrides.keys())
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
    if evidence and not _present(fields["evidence"]):
        facts["evidence"]["value"] = ", ".join(item["type"] for item in evidence[:5])
        facts["evidence"]["status"] = "reported"
    issues = _issues(messages, fields, set(resolved_issues or []))

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
    asked = [key for key in (asked_fields or []) if key in QUESTIONS]
    unanswered = [item["key"] for item in missing]
    next_field = next((key for key in ("counterparty", "location", "event_date", "desired_resolution", "evidence", "amount", "subtype", "key_event", "user_role")
                       if key in unanswered and key not in asked), None)
    question = QUESTIONS.get(next_field) if next_field else (
        "I've noted the available information. Please review the case file and correct any missing or inconsistent details."
    )

    story = _value(story_override, 1400) or _value((ai or {}).get("story_english"), 1400) or _value(draft_narrative(messages), 1400)
    if not story:
        story = "A factual account has not yet been provided."
    story_status = "user_edited" if story_override.strip() else "ai_suggested" if (ai or {}).get("story_english") else "reported"
    identity = _value(case_id, 48) or "CW-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:10].upper()

    return {
        "schema_version": "2.0",
        "case_id": identity,
        "category": chosen,
        "category_label": original["summary"]["category_label"],
        "subtype": subtype,
        "facts": facts,
        "timeline": timeline,
        "evidence": evidence,
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
