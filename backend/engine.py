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
        "draft_facts": draft_narrative(messages),
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



def draft_narrative(messages: list[dict[str, str]]) -> str:
    """Keep only user-reported statements, not questions addressed to the chatbot.

    This deliberately does not invent facts or paraphrase allegations as verified facts.
    The result is an editable draft for the user to confirm.
    """
    sentences: list[str] = []
    for msg in messages:
        if msg.get("role") != "user":
            continue
        raw = clean(msg.get("content"), 2000)
        # Protect common currency abbreviations from sentence splitting.
        raw = re.sub(r"\bRs\.\s*(?=\d)", "INR ", raw, flags=re.I)
        for part in re.split(r"(?<=[.!?])\s+|\n+", raw):
            clause = clean(re.sub(r"\s+", " ", part), 350)
            if not clause or clause.endswith("?"):
                continue
            if re.match(r"^(?:what|how|why|where|when|who|can|could|should|would|do|does|is|are|please|help|thanks|thank you)\b", clause, re.I):
                continue
            if re.search(r"\b(?:what should I do|please (?:draft|generate|write)|can you help|tell me what to do)\b", clause, re.I):
                continue
            if clause not in sentences:
                sentences.append(clause)
            if sum(len(x) for x in sentences) > 1000:
                break
        if sum(len(x) for x in sentences) > 1000:
            break
    return " ".join(sentences)[:1200].strip()



def make_draft(messages: list[dict[str, str]], profile: dict[str, Any] | None = None,
               category: str = "auto", *, confirmed: bool = False, document_type: str = "request") -> str:
    """Build a reviewable factual letter, never a formal legal notice.

    Both essential details and an explicit review confirmation are validated on
    the server, not just in the React UI.
    """
    analysis = analyze(messages, profile, category)
    if analysis["needs_lawyer"]:
        raise ValueError("Draft generation disabled for potentially urgent or criminal matters; seek a qualified lawyer.")
    if not confirmed:
        raise ValueError("Review the proposed facts and confirm they are accurate before generating a PDF.")

    if document_type not in {"request", "notice", "complaint", "reply", "application"}:
        raise ValueError("Unsupported document type.")

    facts = analysis["profile_used"]
    required = ("counterparty", "location", "event_date", "desired_resolution")
    missing = [PROFILE_LABELS[key] for key in required if not facts[key].strip()]
    if missing:
        raise ValueError("Please complete these details before generating a PDF: " + ", ".join(missing))

    story = clean((profile or {}).get("facts_narrative"), 1400) or draft_narrative(messages)
    story = draft_narrative([{"role": "user", "content": story}])
    if not story:
        raise ValueError("Please enter at least one factual statement about the dispute (not just a question).")

    sender = clean((profile or {}).get("sender_name"), 160) or "[Your full name]"
    contact = clean((profile or {}).get("sender_contact"), 180) or "[Your contact information]"
    counterparty = facts["counterparty"]
    location = facts["location"]
    amount = facts["amount"].replace("₹", "INR ")
    event_date = facts["event_date"]
    evidence = facts["evidence"].replace(" (mentioned by user; availability unconfirmed)", "")
    remedy = facts["desired_resolution"].rstrip(" .")
    category_label = analysis["summary"]["category_label"]

    document_config = {
        "request": ("DRAFT REQUEST FOR RESOLUTION", "Request for resolution", "I am writing to seek a resolution of the matter described below."),
        "notice": ("DRAFT NOTICE OUTLINE - LAWYER REVIEW REQUIRED", "Proposed notice requesting resolution", "This is a proposed notice of the matter for review by a qualified lawyer; it does not assert any legal conclusions."),
        "complaint": ("DRAFT COMPLAINT - CHECK RECIPIENT AND PROCEDURE", "Draft complaint", "I am writing to describe a grievance for the appropriate recipient to review. Please verify the authority and filing process."),
        "reply": ("DRAFT REPLY - LAWYER REVIEW ADVISED", "Proposed reply regarding dispute", "I am replying to the concerns raised about the matter below. This draft does not admit or deny allegations beyond the facts I have confirmed."),
        "application": ("DRAFT APPLICATION FOR ASSISTANCE", "Request for assistance", "I am requesting guidance or assistance with the matter described below. Please verify the appropriate office and its application process."),
    }
    heading, subject, opening = document_config[document_type]
    lines = [
        "CASEWISE AI | " + heading,
        "For review only - not a formal legal notice, official filing or legal advice.",
        "",
        f"From: {sender}",
        f"Contact: {contact}",
        f"To: {counterparty}",
        f"City / State: {location}",
        "Date prepared: [Add the date on which you send this letter]",
        "",
        f"Subject: {subject} - {category_label}",
        "",
        "Dear Sir/Madam,",
        "",
        opening + " The following is my account of the events:",
        story,
        "",
        f"Relevant event date: {event_date}",
    ]
    if amount:
        lines.append(f"Amount involved: {amount}")
    if evidence:
        lines.append(f"Documents or evidence identified: {evidence}")
    lines += [
        "",
        "Requested resolution:",
        remedy[0].upper() + remedy[1:] + "." if remedy else "[Specify your requested resolution].",
        "",
        "Please acknowledge this communication in writing. I would prefer an appropriate, peaceful resolution and a written record of correspondence.",
        "",
        "Sincerely,",
        sender,
        "",
        "REVIEW BEFORE SENDING: Confirm each statement, the recipient, dates, documents, amount and requested outcome. Seek qualified legal review if necessary. This letter is not a court filing or formal legal notice.",
    ]
    return "\n".join(lines)
