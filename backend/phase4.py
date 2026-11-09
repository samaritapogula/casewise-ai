"""Phase 4: cautious document intelligence from the live, reviewed case file.

Configuration is by document purpose, never by a specific client's names,
amounts or examples. This module does not verify evidence or determine law.
"""
from __future__ import annotations

from typing import Any

DOCUMENT_REQUIREMENTS = {
    "request": {
        "title": "Resolution request",
        "extra": [
            ("prior_contact", "What have you already asked the other party to do?", False),
        ],
        "recipient_required": False,
    },
    "notice": {
        "title": "Legal notice outline",
        "extra": [
            ("prior_contact", "What communications or attempts to settle have already occurred?", False),
        ],
        "recipient_required": False,
    },
    "complaint": {
        "title": "Complaint draft",
        "extra": [
            ("recipient_name", "Which office or organization will receive this complaint?", True),
            ("prior_contact", "Have you contacted the other party or attempted resolution?", False),
            ("office_action", "What would you like that office to consider doing?", True),
        ],
        "recipient_required": True,
    },
    "reply": {
        "title": "Reply draft",
        "extra": [
            ("received_communication", "What actual communication or allegation are you replying to? Include its sender and date if available.", True),
            ("reply_points", "Which exact statements in that communication do you want to respond to?", True),
        ],
        "recipient_required": False,
    },
    "application": {
        "title": "Application for assistance",
        "extra": [
            ("recipient_name", "Which institution will receive the application?", True),
            ("assistance_requested", "What specific assistance are you seeking?", True),
            ("prior_contact", "Have you taken any previous steps?", False),
        ],
        "recipient_required": True,
    },
}

CORE_FIELDS = (
    ("counterparty", "The other party's identity"),
    ("location", "Place of the dispute"),
    ("event_date", "Relevant event date"),
    ("desired_resolution", "Requested outcome"),
)
_REVIEW_WORDS = {"", "unknown", "not known", "not supplied", "n/a", "none", "not applicable"}


def _clean(value: Any, cap: int = 900) -> str:
    return str(value or "").strip()[:cap]


def _supplied(value: Any) -> bool:
    return _clean(value).casefold() not in _REVIEW_WORDS


def _fact(case: dict, key: str) -> dict:
    row = case.get("facts", {}).get(key, {})
    return row if isinstance(row, dict) else {}


def build_document_intelligence(case: dict, document_type: str, profile: dict | None = None) -> dict:
    """Expose gaps, relevant questions, and reported source trails for the UI."""
    if document_type not in DOCUMENT_REQUIREMENTS:
        raise ValueError("Unsupported document type.")
    config = DOCUMENT_REQUIREMENTS[document_type]
    values = profile or {}
    safety = case.get("risk_flag") == "urgent_or_criminal"
    prompts = []
    for key, label in CORE_FIELDS:
        value = _clean(values.get(key)) or _clean(_fact(case, key).get("value"))
        prompts.append({
            "key": key, "label": label, "question": f"Please confirm: {label.lower()}?",
            "required": True, "answered": _supplied(value), "value": value,
            "source": "user reviewed" if _supplied(values.get(key)) else _fact(case, key).get("status", "missing"),
        })
    for key, question, required in config["extra"]:
        value = _clean(values.get(key), 700)
        prompts.append({
            "key": key, "label": key.replace("_", " ").capitalize(), "question": question,
            "required": required, "answered": _supplied(value), "value": value,
            "source": "user reviewed" if _supplied(value) else "missing",
        })

    warnings = []
    if safety:
        warnings.append("Possible urgent or criminal matter: self-generated drafts are disabled. Seek qualified legal assistance.")
    if not case.get("narrative", {}).get("reviewed"):
        warnings.append("The narrative has not been confirmed in the Case File. Check it before relying on any statement.")
    for issue in case.get("issues", []):
        if not issue.get("resolved"):
            warnings.append("Review possible inconsistency: " + _clean(issue.get("message"), 240))
    for prompt in prompts:
        if prompt["required"] and not prompt["answered"]:
            warnings.append("Missing: " + prompt["label"])
    if not any(item.get("availability") == "user_says_available" for item in case.get("evidence", [])):
        warnings.append("Evidence has not been independently verified; confirm the actual documents and their relevance.")
    if document_type in ("reply", "notice"):
        warnings.append("Have a qualified professional review any legal notice or response with deadlines or procedural consequences.")
    if document_type in ("complaint", "application"):
        warnings.append("Check the receiving organization's eligibility, jurisdiction, process and current requirements.")
    warnings = list(dict.fromkeys(warnings))

    trace = []
    for key, label in (
        ("counterparty", "Other party"), ("location", "Location"),
        ("key_event", "Reported event"), ("event_date", "Reported event date"),
        ("amount", "Amount"), ("desired_resolution", "Requested outcome"),
    ):
        row = _fact(case, key)
        if not _supplied(row.get("value")):
            continue
        trace.append({
            "key": key, "label": label, "value": _clean(row.get("value"), 500),
            "status": row.get("status", "reported"),
            "sources": list(row.get("sources", []))[:6],
            "verified": False,
        })
    for i, item in enumerate(case.get("evidence", [])[:12]):
        trace.append({
            "key": f"evidence_{i}", "label": "Evidence mentioned: " + _clean(item.get("type"), 80),
            "value": _clean(item.get("description") or item.get("type"), 250),
            "status": item.get("availability", "mentioned"),
            "sources": [{"message_index": item["source_message"]}] if isinstance(item.get("source_message"), int) else [],
            "verified": False,
        })
    required_count = sum(item["required"] for item in prompts)
    answered_count = sum(item["required"] and item["answered"] for item in prompts)
    return {
        "schema_version": "4.0",
        "document_type": document_type,
        "title": config["title"],
        "readiness": {
            "status": "blocked_urgent" if safety else "needs_review",
            "required_answered": answered_count, "required_total": required_count,
            "message": "Information coverage only; NOT a legal filing or readiness certification.",
            "warnings": warnings,
        },
        "questions": prompts,
        "fact_trace": trace,
        "disclaimer": "Only reported or user-edited facts are displayed. All evidence and legal requirements need independent checking.",
    }


def build_argument_outline(case: dict) -> dict:
    """Factual practice structure, not prediction, legal advice or a pleading."""
    if case.get("risk_flag") == "urgent_or_criminal":
        raise ValueError("Argument building is disabled for urgent or possible criminal matters.")
    facts = case.get("facts", {})
    def get(key: str) -> str:
        value = facts.get(key, {}).get("value", "")
        return _clean(value, 350) if _supplied(value) else ""
    category = _clean(case.get("category_label") or case.get("category"), 80)
    event = get("key_event")
    other = get("counterparty")
    date = get("event_date")
    amount = get("amount")
    outcome = get("desired_resolution")
    evidence = case.get("evidence", [])
    evidence_names = [
        _clean(item.get("type"), 70) for item in evidence
        if item.get("type") and item.get("availability") not in ("not_available",)
    ][:8]
    questions = []
    for key, question in (
        ("counterparty", "Who is the other party, and what is their relationship to the dispute?"),
        ("event_date", "When did the disputed event occur?"),
        ("desired_resolution", "What resolution are you seeking?"),
    ):
        if not get(key):
            questions.append(question)
    if not evidence_names:
        questions.append("Which documents or communications, if any, could support each reported event?")
    for item in case.get("issues", []):
        if not item.get("resolved"):
            questions.append("Can you clarify: " + _clean(item.get("message"), 160))
    return {
        "schema_version": "4.0",
        "heading": "Factual argument preparation",
        "opening": (
            f"My account concerns a reported {category.lower()} matter."
            + (f" The other party identified in my account is {other}." if other else "")
        ),
        "key_points": [
            {"label": "Reported event", "text": event or "Describe the disputed event precisely.", "verified": False},
            {"label": "Reported date", "text": date or "Date still to be clarified.", "verified": False},
            {"label": "Reported amount", "text": amount or "Amount not specified or not applicable.", "verified": False},
            {"label": "Supporting materials", "text": ", ".join(evidence_names) if evidence_names else "No confirmed documents listed.", "verified": False},
        ],
        "possible_challenges": [
            "The other party may dispute the sequence of events or describe them differently.",
            "The other party may question whether the reported documents support your account.",
            "The agreement, terms, communications, and applicable procedure may change which options exist.",
        ],
        "response_guidance": (
            "Respond with the exact reported sequence, distinguish observed facts from assumptions, "
            "acknowledge unknown details, and cite only evidence you can actually produce."
        ),
        "closing": "I request a review of the facts and would like " + (outcome.rstrip(".") if outcome else "an appropriate resolution to be discussed") + ".",
        "questions_to_prepare": questions,
        "disclaimer": "For respectful factual practice only. Not a court argument, rights assessment, merits prediction or legal advice.",
    }
