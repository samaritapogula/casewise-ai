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




def _readable_evidence(raw: str) -> str:
    """Normalize duplicated short tags, without inventing supporting records."""
    labels = [term.strip() for term in raw.split(",") if term.strip()]
    found = {label.casefold() for label in labels}
    if "whatsapp" in found and "messages" in found:
        labels = [label for label in labels if label.casefold() != "messages"]
    readable = []
    seen = set()
    for label in labels:
        normalized = "WhatsApp messages" if label.casefold() == "whatsapp" else label
        key = normalized.casefold()
        if key not in seen:
            readable.append(normalized)
            seen.add(key)
    return ", ".join(readable)


def _normalize_money_grammar(text: str) -> str:
    """Convert common INR expressions without modifying numerical claims."""
    return re.sub(r"\ba (?=INR\s+\d)", "an ", text.replace("₹", "INR "), flags=re.I)


def make_draft(messages: list[dict[str, str]], profile: dict[str, Any] | None = None,
               category: str = "auto", *, confirmed: bool = False, document_type: str = "request") -> str:
    """Generate a category-appropriate, *type-specific* editable draft.

    This is not an official legal instrument. Only user-provided or reviewed
    details appear as assertions. Unsupported facts are explicit placeholders.
    No statutory provision, limitation period, legal entitlement, forum or
    mandatory response deadline is inferred.
    """
    analysis = analyze(messages, profile, category)
    if analysis["needs_lawyer"]:
        raise ValueError("Draft generation disabled for potentially urgent or criminal matters; seek a qualified lawyer.")
    if not confirmed:
        raise ValueError("Review the proposed facts and confirm they are accurate before generating a PDF.")
    if document_type not in {"request", "notice", "complaint", "reply", "application"}:
        raise ValueError("Unsupported document type.")

    provided = profile or {}
    facts = analysis["profile_used"]
    required = ("counterparty", "location", "event_date", "desired_resolution")
    missing = [PROFILE_LABELS[key] for key in required if not facts[key].strip()]
    if missing:
        raise ValueError("Please complete these details before generating a PDF: " + ", ".join(missing))

    narrative = clean(provided.get("facts_narrative"), 1400) or draft_narrative(messages)
    narrative = draft_narrative([{"role": "user", "content": narrative}])
    if not narrative:
        raise ValueError("Please enter at least one factual statement about the dispute (not just a question).")

    sender = clean(provided.get("sender_name"), 160) or "[Your full name]"
    contact = clean(provided.get("sender_contact"), 180) or "[Your contact information]"
    counterparty = facts["counterparty"]
    office_document = document_type in {"complaint", "application"}
    recipient = clean(provided.get("recipient_name"), 180) or (
        "[Relevant office or authority - verify before use]"
        if office_document else counterparty
    )
    location = facts["location"]
    amount = _normalize_money_grammar(facts["amount"])
    date = facts["event_date"]
    evidence = _readable_evidence(
        facts["evidence"].replace(" (mentioned by user; availability unconfirmed)", "")
    )
    remedy = facts["desired_resolution"].rstrip(" .")
    prior_contact = clean(provided.get("prior_contact"), 600)
    received_communication = clean(provided.get("received_communication"), 700)
    reply_points = clean(provided.get("reply_points"), 700)
    assistance = clean(provided.get("assistance_requested"), 600)
    office_action = clean(provided.get("office_action"), 600)
    category_label = analysis["summary"]["category_label"]
    story = _normalize_money_grammar(narrative)

    headings = {
        "request": ("DRAFT REQUEST FOR RESOLUTION", "Request to resolve a reported civil dispute"),
        "notice": ("DRAFT NOTICE OUTLINE - LAWYER REVIEW REQUIRED", "Proposed notice - facts and remedy for legal review"),
        "complaint": ("DRAFT COMPLAINT - CHECK RECIPIENT AND PROCEDURE", "Complaint for appropriate authority to consider"),
        "reply": ("DRAFT REPLY - LAWYER REVIEW ADVISED", "Proposed response to a communication or claim"),
        "application": ("DRAFT APPLICATION FOR ASSISTANCE", "Application requesting guidance or assistance"),
    }
    heading, subject = headings[document_type]
    lines = [
        "CASEWISE AI | " + heading,
        "For review only - not a formal legal notice, official filing or legal advice.",
        "",
        f"From: {sender}",
        f"Contact: {contact}",
        f"To: {recipient}",
    ]
    if office_document:
        lines.append(f"Party concerned: {counterparty}")
    lines.extend([
        f"City / State: {location}",
        "Date prepared: [Add the date on which you send this draft]",
        "",
        f"Subject: {subject} - {category_label}",
        "",
        "Dear Sir/Madam,",
        "",
    ])
    details = [
        f"Reported relevant date: {date}",
        *([f"Reported amount involved: {amount}"] if amount else []),
        *([f"Supporting materials mentioned by the user: {evidence} (not independently verified)"] if evidence else []),
    ]
    if document_type == "request":
        lines.extend([
            "Purpose of this request:",
            "I am requesting an explanation and a possible resolution of the matter described below.",
            "",
            "My account of what happened:",
            story,
            "",
            "Key details:",
            *details,
            "",
            "Previous attempts to resolve the matter:",
            prior_contact or "[Add any earlier conversations, payment requests or responses, if applicable.]",
            "",
            "Resolution I am asking for:",
            remedy + ".",
            "",
            "Please review these details and provide a written response. I would like to resolve the matter constructively and keep a record of our correspondence.",
        ])
    elif document_type == "notice":
        lines.extend([
            "PURPOSE - PROPOSED NOTICE FOR A QUALIFIED LAWYER TO REVIEW",
            "This outline records the reported dispute and a proposed remedy. A lawyer must check the facts, applicable law, recipient, appropriate service and any deadline before it is used as a legal notice.",
            "",
            "1. Parties and relationship:",
            f"The reported other party is {counterparty}. The matter relates to {category_label.lower()} in {location}.",
            "",
            "2. Facts alleged by the sender (unverified):",
            story,
            "",
            "3. Relevant transaction and reported supporting materials:",
            *details,
            "",
            "4. Earlier communications or attempts to settle:",
            prior_contact or "[Describe any earlier requests, replies or steps taken; do not invent correspondence.]",
            "",
            "5. Proposed resolution for legal review:",
            remedy + ".",
            "",
            "6. Questions for the reviewing lawyer:",
            "Confirm the legal basis, the recipient, the accuracy of allegations, any applicable response period, service requirements, limitation periods and appropriate forum. No statutory provision or deadline is asserted by this outline.",
        ])
    elif document_type == "complaint":
        lines.extend([
            "Nature of grievance:",
            f"This is a reported {category_label.lower()} dispute involving {counterparty}.",
            "",
            "Statement of reported facts:",
            story,
            "",
            "Key details and supporting materials:",
            *details,
            "",
            "Steps taken before this complaint:",
            prior_contact or "[Describe any communication with the other party, or state that none was attempted.]",
            "",
            "Action requested from the receiving organization:",
            office_action or remedy + ".",
            "",
            "Procedural and jurisdictional verification:",
            "Please confirm that the recipient is the appropriate organization and advise on applicable forms, supporting material and the process, if this matter falls within its scope. No filing eligibility or jurisdiction has been determined.",
        ])
    elif document_type == "reply":
        lines.extend([
            "REFERENCE TO COMMUNICATION RECEIVED:",
            received_communication or "[Provide details of the notice, complaint, demand or allegation received, including its date and sender. No incoming notice has been verified.]",
            "",
            "The points I am responding to:",
            reply_points or "[Quote or accurately summarize the specific points raised by the other party. Do not assume what they alleged.]",
            "",
            "My factual account for review:",
            story,
            "",
            "Details and materials I can refer to:",
            *details,
            "",
            "Clarifications or resolution requested:",
            remedy + ".",
            "",
            "Reservation for professional review:",
            "This is only a proposed factual response. It is not an admission, a formal denial, a court pleading or a response to a verified notice. A lawyer should check the original communication, relevant dates and consequences before use.",
        ])
    elif document_type == "application":
        lines.extend([
            "Type of assistance sought:",
            assistance or "[Specify the assistance needed, such as guidance, legal aid, mediation information or help identifying a suitable procedure.]",
            "",
            "Why I am requesting assistance:",
            f"I am seeking information or support in relation to a reported {category_label.lower()} dispute involving {counterparty}.",
            "",
            "Background and reported facts:",
            story,
            "",
            "Relevant details and supporting materials:",
            *details,
            "",
            "Prior steps, if any:",
            prior_contact or "[Describe any prior contact with the other party or a public office, if applicable.]",
            "",
            "Assistance or response requested from this office:",
            assistance or "[Explain exactly what guidance, service or assistance you want this office to consider.]",
            "",
            "Eligibility and procedure:",
            "Please advise whether this office can assist and what process, eligibility rules or forms apply. This draft does not claim entitlement to a particular service.",
        ])
    lines.extend([
        "",
        "Sincerely,",
        sender,
        "",
        "REVIEW BEFORE SENDING: Confirm every statement, the intended recipient, the record being answered (if any), dates, evidence, requested action and local procedure. Seek qualified legal review where necessary. This draft is not a court filing or formal legal notice.",
    ])
    return "\n".join(_normalize_money_grammar(line) for line in lines)
