"""Deterministic analysis and cautious drafting; no automatic legal conclusions.

This is the transparent offline fallback for the LLM-enabled assistant. The
LLM may improve *conversation wording*, not add unverified legal authorities.
"""
from __future__ import annotations

import re
from typing import Any
from .knowledge import CATEGORIES, SOURCES, VERIFIED_ON, ALLOWED_CATEGORIES

CRIMINAL_PATTERNS = (
    r"\b(murder|rape|kidnapp(?:ed|ing)?|sexual assault|arrested|police custody|bail application|fir registered)\b",
)
URGENT_PATTERN = re.compile(r"\b(hearing tomorrow|court tomorrow|eviction tomorrow|evict(?:ing|ed)? today|deadline today|served a summons|court summons|immediate threat|physically threaten(?:ed|ing)?|violence|suicid(?:e|al))\b", re.I)
AMOUNT_PATTERN = re.compile(r"(?:(?:₹|rs\.?|inr)\s*)([\d,]+(?:\.\d{1,2})?)", re.I)
STATE_HINT = re.compile(r"\b(?:in|at|from)\s+(Kanpur|Delhi|Mumbai|Maharashtra|Karnataka|Bengaluru|Bangalore|Chennai|Tamil Nadu|Hyderabad|Telangana|Pune|Lucknow|Uttar Pradesh|Kolkata|West Bengal|Gujarat|Rajasthan|Kerala|Punjab|Bihar|Odisha|Haryana|Goa)\b", re.I)
EVIDENCE_MARKERS = ("receipt", "invoice", "screenshot", "email", "messages", "whatsapp", "agreement", "contract", "payslip", "bank transfer", "bank statement", "photo", "notice")
PROFILE_FIELDS = ("location", "counterparty", "amount", "event_date", "evidence", "desired_resolution")
PROFILE_LABELS = {
    "location": "State or city", "counterparty": "Other party", "amount": "Amount in dispute",
    "event_date": "Relevant date", "evidence": "Evidence available", "desired_resolution": "Resolution requested",
}


def clean(value: Any, cap: int = 600) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()[:cap]


def select_category(text: str, category: str = "auto") -> str:
    if category in ALLOWED_CATEGORIES:
        return category
    lower = text.lower()
    scores = {key: sum(3 if " " in term else 1 for term in config["terms"] if re.search(r"\b" + re.escape(term) + r"\b", lower)) for key, config in CATEGORIES.items() if key != "other"}
    if not any(scores.values()):
        return "other"
    return max(scores, key=scores.get)


def profile_from_messages(messages: list[dict[str, str]], profile: dict[str, Any] | None) -> dict[str, str]:
    result = {k: clean((profile or {}).get(k), 250) for k in PROFILE_FIELDS}
    user_text = "\n".join(clean(m.get("content"), 2000) for m in messages if m.get("role") == "user")
    if not result["amount"]:
        match = AMOUNT_PATTERN.search(user_text)
        if match:
            result["amount"] = "₹" + match.group(1)
    if not result["location"]:
        match = STATE_HINT.search(user_text)
        if match:
            result["location"] = match.group(1)
    if not result["evidence"]:
        matches = [term for term in EVIDENCE_MARKERS if re.search(r"\b" + re.escape(term) + r"s?\b", user_text, re.I)]
        if matches:
            result["evidence"] = ", ".join(matches[:4]) + " (mentioned by user; availability unconfirmed)"
    return result


def analyze(messages: list[dict[str, str]], profile: dict[str, Any] | None = None, category: str = "auto") -> dict:
    user_messages = [clean(m.get("content"), 2000) for m in messages if m.get("role") == "user" and clean(m.get("content"))]
    if not user_messages:
        raise ValueError("Please describe a problem first.")
    first = user_messages[0]
    complete_story = "\n".join(user_messages)
    chosen = select_category(complete_story, category)
    info = CATEGORIES[chosen]
    fields = profile_from_messages(messages, profile)
    criminal = bool(any(re.search(p, complete_story, re.I) for p in CRIMINAL_PATTERNS))
    urgent = bool(URGENT_PATTERN.search(complete_story))
    missing = [PROFILE_LABELS[k] for k in PROFILE_FIELDS if not fields[k]]
    source_list = [dict(SOURCES[k], verified_on=VERIFIED_ON) for k in info["source_ids"]]
    warnings = ["General information only, not a lawyer, legal opinion, or outcome prediction.", "Sources are official starting points, not confirmation of eligibility, jurisdiction or a deadline."]
    if chosen == "property":
        warnings.append("Property and tenancy rules can differ by state and the type of property; local advice is important.")
    if chosen == "employment":
        warnings.append("Employment remedies differ by worker status, applicable law and location; SAMADHAN may not cover every employee.")
    if criminal:
        warnings.insert(0, "Possible criminal-law issue detected. This civil-only prototype cannot advise on arrests, offences or criminal proceedings; consult a qualified lawyer.")
    if urgent:
        warnings.insert(0, "Time-sensitive or safety-related issue detected. Seek prompt help from a qualified local lawyer or the appropriate emergency service; do not rely on this prototype.")
    if chosen == "other":
        warnings.append("This issue has not been classified within the four tested civil categories.")

    steps = ([] if criminal else list(info["steps"]))
    if criminal:
        steps = ["Obtain advice from a qualified lawyer and preserve any relevant notices, documents and dates."]
    question_number = max(0, len(user_messages) - 1)
    question = info["questions"][question_number % len(info["questions"])]
    if criminal:
        assistant = "This may involve criminal law, which CaseWise AI does not cover. Please speak with a qualified lawyer promptly. Is there a current legal notice or urgent hearing?"
    elif urgent:
        assistant = "This sounds time-sensitive. Please contact a qualified local lawyer promptly rather than relying on a generated answer. " + question
    else:
        assistant = "I can help organize this as a possible " + info["title"].lower() + " issue. " + question

    summary = {
        "issue": first,
        "category": chosen,
        "category_label": info["title"],
        "facts_reported": {PROFILE_LABELS[k]: v for k, v in fields.items() if v},
        "missing_details": missing,
        "evidence_to_preserve": [
            "A dated timeline of what happened",
            "Agreements, invoices, notices and messages relevant to the dispute",
            "Payment or transaction records, if any",
        ],
        "assessment": "Preliminary organization of user-provided facts; no determination of legal rights or case merits.",
    }
    return {
        "assistant_message": assistant,
        "summary": summary,
        "next_steps": steps,
        "sources": source_list,
        "safety_flags": warnings,
        "needs_lawyer": criminal or urgent,
        "mode": "guided-demo",
        "source_status": "Curated official links reviewed " + VERIFIED_ON + "; not checked live during this request.",
        "profile_used": fields,
    }


def make_draft(messages: list[dict[str, str]], profile: dict[str, Any] | None = None, category: str = "auto") -> str:
    analysis = analyze(messages, profile, category)
    if analysis["needs_lawyer"]:
        raise ValueError("Draft generation disabled for potentially urgent or criminal matters; seek a qualified lawyer.")
    first = clean(next(m["content"] for m in messages if m.get("role") == "user" and clean(m.get("content"))), 1500)
    facts = analysis["profile_used"]
    name = facts["counterparty"] or "[Name of the other party]"
    location = facts["location"] or "[City and State]"
    amount = facts["amount"] or "[Amount, if applicable]"
    date = facts["event_date"] or "[Relevant date]"
    evidence = facts["evidence"] or "[List documents you have verified]"
    request = facts["desired_resolution"] or "[Describe the resolution you want]"
    category_label = analysis["summary"]["category_label"]
    return "\n".join([
        "DRAFT — FACTUAL REQUEST FOR RESOLUTION (NOT A FORMAL LEGAL NOTICE)",
        "For review and editing; not legal advice. Do not send without checking facts and recipient.",
        "",
        "From: [Your name and contact details]",
        f"To: {name}",
        f"Place: {location}",
        "Date of letter: [Insert today's date when sending]",
        "",
        f"Subject: Request for resolution — {category_label}",
        "",
        "Dear Sir/Madam,",
        "",
        "I am writing to request a resolution concerning the following issue, as I understand it:",
        first,
        "",
        f"Relevant date (please verify): {date}",
        f"Amount involved (please verify): {amount}",
        f"Documents currently available (please verify): {evidence}",
        "",
        f"I request: {request}.",
        "Please acknowledge this letter and respond in writing within a mutually reasonable time.",
        "I would prefer to resolve this matter amicably and keep a written record of communications.",
        "",
        "Sincerely,",
        "[Your full name]",
        "",
        "CHECK BEFORE SENDING: Confirm names, dates, amounts, evidence and accuracy. Seek legal review",
        "before making legal allegations, imposing a deadline, or filing any court/authority document.",
    ])
