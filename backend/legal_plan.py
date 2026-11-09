"""Phase 3: deterministic, source-linked orientation and user-controlled action plans.

All references are curated official starting points and checked manually
2026-11-09, not live legal research. This service NEVER determines rights,
jurisdiction, limitation periods, eligibility, or likelihood of winning.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .adaptive_planning import build_adaptive_plan

SOURCE_REVIEWED = "2026-11-09"
SOURCES = {
    "nalsa": {
        "id": "nalsa", "kind": "legal_aid",
        "title": "NALSA — Free legal aid and eligibility",
        "url": "https://nalsa.gov.in/legal-aid/",
        "relevance": "Official information on legal aid, applications and finding legal-services offices.",
    },
    "consumer_law": {
        "id": "consumer_law", "kind": "statute",
        "title": "Consumer Protection Act, 2019 — Department of Consumer Affairs",
        "url": "https://consumeraffairs.gov.in/pages/consumer-protection-acts",
        "relevance": "Official publication and rules; whether a transaction qualifies needs fact-specific checking.",
    },
    "nch": {
        "id": "nch", "kind": "complaint_channel",
        "title": "National Consumer Helpline — official portal",
        "url": "https://consumerhelpline.gov.in/public/contact",
        "relevance": "Consumer grievance support at the pre-litigation stage; it is not a court judgment.",
    },
    "ejagriti": {
        "id": "ejagriti", "kind": "filing_channel",
        "title": "e-Jagriti — Consumer Commission platform",
        "url": "https://e-jagriti.gov.in/",
        "relevance": "Official consumer complaint filing/tracking; verify commission jurisdiction and procedure.",
    },
    "contract_law": {
        "id": "contract_law", "kind": "statute",
        "title": "Indian Contract Act, 1872 — India Code",
        "url": "https://www.indiacode.nic.in/handle/123456789/2187?col=123456789%2F1362",
        "relevance": "Official statute reference; contractual remedies turn on agreement and facts.",
    },
    "up_tenancy": {
        "id": "up_tenancy", "kind": "state_statute",
        "title": "Uttar Pradesh Regulation of Urban Premises Tenancy Act, 2021 — India Code",
        "url": "https://www.indiacode.nic.in/handle/123456789/21157",
        "relevance": "Possible state tenancy reference only for qualifying urban premises in UP; coverage must be checked.",
    },
    "labour": {
        "id": "labour", "kind": "information_channel",
        "title": "Chief Labour Commissioner — Online Services",
        "url": "https://clc.gov.in/clc/online-services",
        "relevance": "Official guidance on labour online services, including SAMADHAN; claims and worker status require checking.",
    },
}

CATEGORY_GUIDANCE = {
    "consumer": {
        "title": "Consumer purchase or service dispute",
        "position": "A consumer complaint may be a possible route if your transaction and grievance meet the applicable requirements. The present account does not establish an entitlement to a refund, repair or compensation.",
        "considerations": [
            "Check what was purchased, when it was supplied and what was promised.",
            "Review the terms, the business's response and any warranty or return conditions.",
            "A consumer-commission route depends on eligibility, jurisdiction, procedure and the current law.",
        ],
        "source_ids": ["consumer_law", "nch", "ejagriti", "nalsa"],
        "routes": [
            ("seller", "Seller or service-provider grievance process",
             "Consider requesting a written response and retaining proof of communication.", []),
            ("nch", "National Consumer Helpline",
             "Possible pre-litigation grievance assistance; check whether the issue fits its process.", ["nch"]),
            ("commission", "Consumer Commission / e-Jagriti",
             "Explore only after checking consumer status, venue, filing requirements and any time limits.", ["ejagriti", "consumer_law"]),
        ],
        "contact": "Send a factual written request to the seller or service provider, asking for a response without asserting a guaranteed legal outcome.",
    },
    "property": {
        "title": "Property and rental dispute",
        "position": "The rental or property agreement and the law applying to the particular premises and state may affect the available options. A reported unpaid deposit does not by itself establish which remedy or forum applies.",
        "considerations": [
            "Check the written agreement, move-out condition, handover and deposit terms.",
            "Confirm whether the premises and relationship fall under a state tenancy regime.",
            "Avoid selecting a rent authority, court or deadline without a local jurisdiction and law check.",
        ],
        "source_ids": ["contract_law", "nalsa"],
        "routes": [
            ("counterparty", "Landlord, owner or other counterparty",
             "Consider a factual request for the deposit breakdown, return, or reasons for withholding it.", []),
            ("local_review", "Local tenancy authority or civil-law advice",
             "Have a local lawyer identify the correct state tenancy regime, forum and time limits.", ["nalsa"]),
        ],
        "contact": "Ask the landlord or relevant party in writing for an explanation, applicable agreement clause and proposed resolution.",
    },
    "employment": {
        "title": "Unpaid salary or employment dispute",
        "position": "Potential wage or employment remedies depend on your employment status, applicable law, location and contractual terms. This summary cannot determine coverage or the correct authority.",
        "considerations": [
            "Check the employment arrangement, pay periods, contract and written deductions or responses.",
            "The route for workers and other employees can differ, including which authority can hear the claim.",
            "Confirm applicable filing time limits and labour-law coverage with an appropriate authority or adviser.",
        ],
        "source_ids": ["labour", "nalsa"],
        "routes": [
            ("hr", "Employer or HR grievance process",
             "Consider requesting the payment breakdown and outstanding amount in writing.", []),
            ("labour_review", "Labour authority / SAMADHAN applicability check",
             "Explore whether your worker status and claim are covered before choosing a labour forum.", ["labour"]),
        ],
        "contact": "Ask HR or the employer in writing for a pay statement and response about any unpaid amounts.",
    },
    "contract": {
        "title": "Contract or outstanding-payment dispute",
        "position": "Potential options can depend on the agreement's terms, proof of performance, correspondence and applicable contract law. No enforceability or damages conclusion has been made.",
        "considerations": [
            "Review what each party agreed, payment conditions and any dispute-resolution clause.",
            "Check evidence of delivery or performance and any objections raised by the other party.",
            "A qualified adviser should check limitation rules, venue and contractual remedies before any filing.",
        ],
        "source_ids": ["contract_law", "nalsa"],
        "routes": [
            ("contract_contact", "Contract counterparty",
             "Consider a factual request for payment or clarification of the contested obligation.", []),
            ("contract_review", "Contractual dispute-resolution clause or civil-law review",
             "Examine contractual negotiation, mediation, arbitration or civil options only if applicable.", ["contract_law", "nalsa"]),
        ],
        "contact": "Ask the other contracting party for a written response about the outstanding performance or payment.",
    },
    "other": {
        "title": "Dispute type needs clarification",
        "position": "This account has not been reliably classified within the supported civil categories, so choosing a specific legal remedy would be premature.",
        "considerations": [
            "Clarify which kind of civil dispute this is and who is involved.",
            "Review dates, location, evidence and any notices or court papers.",
            "Ask a qualified adviser or legal-aid office for the correct route before proceeding.",
        ],
        "source_ids": ["nalsa"],
        "routes": [
            ("legal_triage", "Legal aid or lawyer for triage",
             "Seek help to identify the appropriate subject area and legal channel.", ["nalsa"]),
        ],
        "contact": "Clarify the dispute and the party involved before sending a formal request.",
    },
}

def _usable(value: Any) -> bool:
    val = str(value or "").strip().lower()
    return val not in ("", "unknown", "not known", "n/a", "not applicable", "someone", "somebody", "person", "none", "pending")

def _fact(case: dict, key: str) -> str:
    return str(case.get("facts", {}).get(key, {}).get("value", "")).strip()

def _action(id: str, title: str, instructions: str, refs: list[str], checked: dict[str, bool]) -> dict:
    return {"id": id, "title": title, "instructions": instructions,
            "source_ids": refs, "completed": checked.get(id) is True}

def build_legal_plan(case: dict, *, completed_actions: dict[str, bool] | None = None) -> dict:
    """Build a new plan from a Phase 2 case file. No API key or persistence needed."""
    category = case.get("category", "other")
    guide = CATEGORY_GUIDANCE.get(category, CATEGORY_GUIDANCE["other"])
    risk = case.get("risk_flag") == "urgent_or_criminal"
    checked = completed_actions if isinstance(completed_actions, dict) else {}

    # Official registry: no source URLs or legal citations come from the LLM.
    source_ids = list(guide["source_ids"])
    location = _fact(case, "location").lower()
    if category == "property" and any(p in location for p in ("uttar pradesh", "kanpur", "lucknow", "noida", "ghaziabad", "varanasi")):
        source_ids.append("up_tenancy")
    sources = [{**SOURCES[key], "reviewed_on": SOURCE_REVIEWED,
                "verification": "Official page checked manually; current applicability not established."}
               for key in source_ids]
    statutes = [{"source_id": key, "title": SOURCES[key]["title"],
                 "applicability": "Potential reference only; check the latest text, scope and facts with a qualified professional."}
                for key in source_ids if SOURCES[key]["kind"] in ("statute", "state_statute")]

    reported = []
    evidence = case.get("evidence", [])
    for item in evidence:
        if item.get("availability") == "user_says_available":
            reported.append("You report having " + item.get("type", "supporting material").lower() + "; authenticity and relevance are not verified.")
        elif item.get("availability") == "mentioned":
            reported.append(item.get("type", "Supporting material") + " was mentioned; availability is not confirmed.")
    if _usable(_fact(case, "amount")):
        reported.append("A disputed amount was reported: " + _fact(case, "amount") + " (not independently verified).")
    if _usable(_fact(case, "event_date")):
        reported.append("A relevant date was reported: " + _fact(case, "event_date") + " (its significance is unverified).")
    if not reported:
        reported.append("No independently verified support is available; collect a detailed factual record.")

    gaps = []
    for item in case.get("missing", []):
        gaps.append("Missing case information: " + str(item.get("label", "a key detail")) + ".")
    for issue in case.get("issues", []):
        if not issue.get("resolved"):
            gaps.append("Clarification needed: " + str(issue.get("message", "A possible inconsistency was found.")))
    if not any(x.get("availability") == "user_says_available" for x in evidence):
        gaps.append("No supporting document has been confirmed as available by the user.")
    if not case.get("narrative", {}).get("reviewed"):
        gaps.append("The factual narrative has not been explicitly reviewed and confirmed.")
    for question in case.get("context", {}).get("questions", []):
        if question.get("status") == "missing":
            gaps.append("Additional context to clarify: " + question.get("label", "a detail") + ".")
    gaps = gaps[:12]

    uncertainties = [
        "The other side's account, defenses and documents have not been independently assessed.",
        "Eligibility, jurisdiction, limitation periods and current legal applicability are not determined.",
    ]
    if category == "property":
        uncertainties.append("State-specific property rules and the nature of the premises require checking.")
    elif category == "employment":
        uncertainties.append("Employee/workman status and the authority with jurisdiction require checking.")
    else:
        uncertainties.append("Contract or transaction terms may change which options are available.")

    adaptive = build_adaptive_plan(case, completed_actions=checked, official_source_ids=source_ids)
    actions = adaptive["actions"]

    routes = ([] if risk else [{
        "id": route_id, "title": title, "when_to_consider": reason,
        "source_ids": [ref for ref in route_sources if ref in SOURCES],
        "eligibility_status": "Not assessed; possible channel only.",
    } for route_id, title, reason, route_sources in guide["routes"]])
    if risk:
        routes = [{
            "id": "urgent", "title": "Qualified local legal assistance",
            "when_to_consider": "Promptly seek individual advice for the flagged urgent/criminal issue.",
            "source_ids": ["nalsa"], "eligibility_status": "Legal aid eligibility is not automatically established.",
        }]
    state = "urgent_review" if risk else "category_review" if category == "other" else "general_guidance"
    escalation_reasons = []
    if risk:
        escalation_reasons.append("Possible urgent or criminal issue flagged during case intake.")
    if category == "other":
        escalation_reasons.append("The issue is outside the four reliably supported civil categories.")
    if case.get("review", {}).get("unresolved_issues", 0):
        escalation_reasons.append("Unresolved inconsistencies appear in the case file.")
    escalation_reasons.append("Consult a professional for any deadline, official notice, court document, legal eligibility or dispute-specific decision.")
    return {
        "schema_version": "3.1", "case_id": case.get("case_id", ""),
        "category": category,
        "position": {
            "heading": guide["title"],
            "explanation": guide["position"],
            "considerations": guide["considerations"],
            "status": "Cautious orientation only — not verified legal advice, a rights decision, or an outcome prediction.",
        },
        "stage": adaptive["stage"],
        "case_focus": adaptive["case_focus"],
        "context_questions": adaptive["context_questions"],
        "document_recommendations": adaptive["document_recommendations"],
        "source_reviewed_on": SOURCE_REVIEWED,
        "source_status": "Official source URLs manually reviewed 9 November 2026; not checked live per request. Law and coverage may change.",
        "sources": sources,
        "statute_references": statutes,
        "supporting_reports": reported[:8],
        "uncertainties": uncertainties,
        "evidence_gaps": gaps,
        "routes": routes,
        "actions": actions,
        "checklist": {"completed": sum(a["completed"] for a in actions), "total": len(actions),
                      "message": "User-marked task progress; not evidence of legal compliance or case readiness."},
        "escalation": {
            "level": state,
            "reasons": escalation_reasons,
            "message": ("Seek prompt help from a qualified lawyer or appropriate service. Do not rely on a self-generated notice or routine filing steps."
                        if risk else "For deadlines, threatened proceedings, official notices, and filing, obtain individualized qualified advice."),
        },
        "disclaimer": "This plan only organizes possible next steps. Sources are authentic links, not proof that a law applies or a claim will succeed. Do not submit it as a court filing.",
    }
