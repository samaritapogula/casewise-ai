"""Fact-sensitive adaptive workflow, shared by all supported civil-case types.

No example-specific names, money, addresses, dates, or outcomes are embedded
here. Category/subtype focus and optional questions come from case_policy.json.
Potential legal channels and source URLs remain in the separate official
source registry; this module never invents statutes, forums or deadlines.
"""
from __future__ import annotations
from typing import Any

from .case_policy import get_case_policy

DOCUMENT_LABELS = {
    "request": "Resolution request",
    "notice": "Legal notice outline",
    "complaint": "Complaint draft",
    "reply": "Reply draft",
    "application": "Application for assistance",
}


def _fact(case: dict, key: str) -> str:
    return str(case.get("facts", {}).get(key, {}).get("value") or "").strip()


def _filled(case: dict, key: str) -> bool:
    checks = case.get("completeness", {}).get("checks", [])
    return any(x.get("key") == key and x.get("complete") is True for x in checks)


def _answered(case: dict, key: str) -> bool:
    # Unknown is a permissible *answer* to a question; it never becomes an
    # asserted factual date or amount. It is still displayed as a gap.
    return _filled(case, key) or key in case.get("unknown_fields", [])


def _task(id: str, title: str, instructions: str,
          source_ids: list[str], checked: dict[str, bool],
          stage: str) -> dict:
    return {
        "id": id, "title": title, "instructions": instructions,
        "source_ids": source_ids,
        "stage": stage,
        "completed": checked.get(id) is True,
    }


def _stage(case: dict) -> dict:
    missing_essentials = [
        key for key in ("subtype", "key_event", "counterparty", "desired_resolution")
        if not _answered(case, key)
    ]
    missing_followups = [
        key for key in ("location", "event_date", "amount", "evidence")
        if not _answered(case, key)
    ]
    if case.get("risk_flag") == "urgent_or_criminal":
        return {
            "code": "urgent", "title": "Urgent professional review",
            "description": "Possible urgency or criminal content; routine legal-action suggestions are withheld.",
            "missing_essentials": missing_essentials, "missing_followups": missing_followups,
        }
    if case.get("category") == "other":
        return {
            "code": "triage", "title": "Clarify the dispute type",
            "description": "This issue is not reliably classified into a supported civil category.",
            "missing_essentials": missing_essentials, "missing_followups": missing_followups,
        }
    if missing_essentials:
        code, title, description = (
            "intake", "Collect the essential facts",
            "Only a preliminary fact checklist and safe record-preservation steps are available.",
        )
    elif missing_followups:
        code, title, description = (
            "preliminary", "Develop the factual record",
            "The core dispute is identified, but key details still require clarification.",
        )
    else:
        code, title, description = (
            "personalized", "Case-specific action plan",
            "Key questions have been addressed, including any explicitly unknown answers. Review all facts and local legal requirements before use.",
        )
    return {
        "code": code, "title": title, "description": description,
        "missing_essentials": missing_essentials, "missing_followups": missing_followups,
    }


def _recommendations(case: dict, policy: dict, stage: str) -> list[dict]:
    has_counterparty = _filled(case, "counterparty")
    has_goal = _filled(case, "desired_resolution")
    has_notice = any(item.get("type", "").lower() == "notice" for item in case.get("evidence", []))
    prior_contact = any(
        ("contact" in item.get("id", "") or "response" in item.get("id", ""))
        and item.get("status") not in ("missing", "not_known")
        for item in case.get("context", {}).get("questions", [])
    )
    statuses = {
        "request": (
            "recommended" if stage == "personalized" and has_counterparty and has_goal
            else "requires_more_facts",
            "A factual request may be useful after the other party and desired outcome are confirmed.",
        ),
        "notice": (
            "consider_with_lawyer" if stage == "personalized" and prior_contact
            else "requires_more_facts",
            "Formal-notice wording and service require professional review; prior communications should be checked.",
        ),
        "complaint": (
            "possible_after_eligibility_check" if stage == "personalized" and prior_contact
            else "requires_more_facts",
            "Only consider a grievance route after the correct receiving organization, coverage and prior steps are checked.",
        ),
        "reply": (
            "consider_with_lawyer" if has_notice
            else "requires_incoming_communication",
            "A reply should be based on the actual communication or allegation received; none is assumed.",
        ),
        "application": (
            "possible_after_eligibility_check" if stage in ("preliminary", "personalized")
            else "information_only",
            "A request for legal aid or assistance depends on the office's scope and eligibility; it is not a filing recommendation.",
        ),
    }
    order = policy.get("document_priority", list(DOCUMENT_LABELS))
    result = []
    for doc_id in [*order, *DOCUMENT_LABELS]:
        if doc_id in DOCUMENT_LABELS and doc_id not in {x["type"] for x in result}:
            state, reason = statuses[doc_id]
            result.append({
                "type": doc_id, "label": DOCUMENT_LABELS[doc_id],
                "status": state, "reason": reason,
            })
    return result


def build_adaptive_plan(
    case: dict, completed_actions: dict[str, bool] | None = None,
    official_source_ids: list[str] | None = None,
) -> dict:
    """Return the fact-dependent portion of a source-verified legal plan."""
    checked = completed_actions if isinstance(completed_actions, dict) else {}
    policy = get_case_policy(case.get("category", "other"), case.get("subtype", {}).get("code", ""))
    stage = _stage(case)
    code = stage["code"]
    sources = official_source_ids or []
    actions = []
    # The preserve action stays stable when facts are supplied incrementally;
    # its checked state may carry across drafts in this browser session.
    actions.append(_task(
        "preserve", "Preserve relevant records", policy["records"],
        [], checked, code,
    ))
    gaps = case.get("missing", [])
    if stage["missing_essentials"] or stage["missing_followups"]:
        labels = [
            item["label"] for item in gaps
            if item.get("key") in (stage["missing_essentials"] + stage["missing_followups"])
        ]
        question = case.get("next_question", {}).get("text", "")
        text = "Provide or explicitly mark as unknown: " + ", ".join(labels[:8]) + "."
        if question and not question.startswith("I've noted"):
            text += " Next question: " + question
        actions.append(_task(
            "clarify", "Answer missing factual questions", text,
            [], checked, code,
        ))
    unresolved = [x for x in case.get("issues", []) if not x.get("resolved")]
    if unresolved:
        actions.append(_task(
            "resolve_issues", "Review potentially inconsistent details",
            "Review these reported differences, without assuming either statement is false: "
            + "; ".join(x.get("message", "") for x in unresolved[:3]),
            [], checked, code,
        ))
    if code == "urgent":
        actions.append(_task(
            "urgent_advice", "Seek prompt qualified advice",
            "A time-sensitive or potentially criminal issue was flagged. Contact a qualified local lawyer promptly; use emergency assistance if immediate safety is at risk.",
            ["nalsa"], checked, code,
        ))
    elif code == "triage":
        actions.append(_task(
            "triage_help", "Identify the correct subject area",
            "Ask a qualified adviser or legal-aid office to identify the applicable subject and procedure before preparing a filing.",
            ["nalsa"], checked, code,
        ))
    else:
        material = [
            item for item in case.get("evidence", [])
            if item.get("availability") in ("mentioned", "user_says_available")
        ]
        if material:
            descriptions = "; ".join(
                str(item.get("description") or item.get("type") or "record") for item in material[:6]
            )
            actions.append(_task(
                "review_evidence", "Review reported supporting material",
                "Check whether each of these can actually be produced, and what it proves: "
                + descriptions + ". A mention is not independent verification.",
                [], checked, code,
            ))
        elif _answered(case, "evidence"):
            actions.append(_task(
                "evidence_gap", "Record the evidence limitation",
                "You reported having no documents or an unknown evidence status. Record what is unavailable; do not create or alter evidence.",
                [], checked, code,
            ))
        if code == "preliminary":
            actions.append(_task(
                "review_record", "Review the developing case record",
                policy["focus"] + " Do not assume any legal result while essential details remain unconfirmed.",
                [], checked, code,
            ))
        if code == "personalized":
            other_party = _fact(case, "counterparty")
            goal = _fact(case, "desired_resolution")
            amount = _fact(case, "amount")
            event_date = _fact(case, "event_date")
            conditions = []
            if _filled(case, "amount") and amount.strip().lower() not in ("not applicable", "n/a"):
                conditions.append("Reported disputed amount: " + amount + ".")
            if _filled(case, "event_date"):
                conditions.append("Reported relevant date: " + event_date + ".")
            actions.append(_task(
                "review_terms", "Review terms and factual basis",
                policy["focus"] + " " + " ".join(conditions),
                [], checked, code,
            ))
            actions.append(_task(
                "contact", "Prepare a tailored factual request",
                "Use the confirmed wording to prepare a factual request to "
                + other_party + ". Desired outcome as reported: " + goal + ". "
                + " ".join(conditions) + " " + policy["contact"]
                + " Retain a copy and proof of any communication; this is not an automatic notice.",
                [], checked, code,
            ))
            if case.get("category") != "other":
                channel_ids = [source for source in sources
                               if source in ("nch", "ejagriti", "labour", "up_tenancy")]
                actions.append(_task(
                    "channels", "Check possible official information channels",
                    "Use linked official resources only as starting points. Ask an appropriate professional to confirm scope, eligibility, venue, applicable law and any deadline before filing.",
                    channel_ids, checked, code,
                ))
        optional = [
            row for row in case.get("context", {}).get("questions", [])
            if row.get("status") == "missing"
        ]
        if optional and code in ("preliminary", "personalized"):
            actions.append(_task(
                "context_details", "Clarify further dispute-specific details",
                "For a more useful factual assessment, consider these questions: "
                + " ".join(row.get("question", "") for row in optional[:3]),
                [], checked, code,
            ))
        elif case.get("context", {}).get("answered", 0):
            answers = [
                row for row in case.get("context", {}).get("questions", [])
                if row.get("answer") and row.get("status") in ("reported", "user_edited")
            ]
            if answers:
                actions.append(_task(
                    "check_extra_details", "Verify your additional reported information",
                    "Review the reported answers: "
                    + "; ".join(
                        row["label"] + ": " + str(row["answer"])[:170] for row in answers[:3]
                    ) + ". Check all dates and statements before relying on them.",
                    [], checked, code,
                ))
        if code in ("preliminary", "personalized"):
            actions.append(_task(
                "legal_review", "Confirm local rules and deadlines with a qualified professional",
                "This plan does not determine legal rights or deadlines. Ask a qualified local adviser to check any formal notice, limitation period, forum or proposed filing.",
                ["nalsa"], checked, code,
            ))
    questions = case.get("context", {}).get("questions", [])
    return {
        "stage": stage,
        "actions": actions,
        "context_questions": questions,
        "pending_context_questions": [row for row in questions if row.get("status") == "missing"],
        "document_recommendations": _recommendations(case, policy, code),
        "case_focus": case.get("structured_summary", {}),
        "policy_focus": policy["focus"],
    }
