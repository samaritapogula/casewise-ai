"""Evidence extraction with provenance and conservative semantic deduplication.

A bank-transfer receipt must not count as both a receipt and an independent bank
record merely because two aliases matched the *same words*. Separate documents
are preserved. Nothing is independently verified or uploaded.
"""
from __future__ import annotations
import re

# Taxonomy, not scenario-specific case facts: expandable aliases for civil cases.
PATTERNS = (
    ("Invoice", r"\binvoices?\b"),
    ("Receipt", r"\breceipts?\b"),
    ("Agreement", r"\b(?:agreements?|contracts?|leases?)\b"),
    ("Payment Record", r"\b(?:bank transfers?|bank statements?|payment (?:proof|records?)|transaction records?)\b"),
    ("Messages", r"\b(?:whatsapp(?:\s+(?:messages?|chats?))?|messages?|texts?|chats?)\b"),
    ("Email", r"\bemails?\b"),
    ("Photograph", r"\b(?:photos?|pictures?|photographs?|screenshots?)\b"),
    ("Notice", r"\bnotices?\b"),
    ("Payslip", r"\bpayslips?\b"),
)
_CLAIM_HAVE = re.compile(r"\b(?:i have|i've got|i possess|i kept|i saved|i can provide)\b", re.I)
_CLAIM_LACK = re.compile(r"\b(?:i (?:do not|don't) have|i lost|i haven't got|no|without)\b", re.I)


def _same_document(content: str, receipt: re.Match, transfer: re.Match) -> bool:
    # "bank transfer receipt" is one document; "bank transfer and receipt"
    # may be two. Do not merge records across conjunctions.
    between = content[transfer.end():receipt.start()] if transfer.end() <= receipt.start() else ""
    return 0 <= receipt.start() - transfer.end() <= 3 and not between.strip()


def _describe(kind: str, content: str, match: re.Match, source_start: int | None = None) -> str:
    start = source_start if source_start is not None else match.start()
    snippet = content[max(0, start - 45):match.end() + 12].lower()
    phrase = content[start:match.end()]
    if kind == "Receipt" and "bank transfer" in snippet[-65:]:
        return "Bank transfer receipt"
    if kind == "Receipt" and "payment" in snippet[-35:]:
        return "Payment receipt"
    if kind == "Agreement":
        return "Signed agreement" if re.search(r"\bsigned\b", snippet) else "Agreement or contract"
    if kind == "Messages" and "whatsapp" in snippet:
        return "WhatsApp messages"
    if kind == "Payment Record":
        return "Bank transfer record" if "bank transfer" in phrase.lower() else phrase.strip().capitalize()
    return phrase.strip().capitalize()


def _availability(content: str, start: int) -> str:
    before = content[max(0, start-140):start]
    # The latest explicit possession phrase preceding the item determines
    # availability. Avoid assuming a document exists just because it is named.
    positive = list(_CLAIM_HAVE.finditer(before))
    negative = list(_CLAIM_LACK.finditer(before))
    pos = positive[-1].start() if positive else -1
    neg = negative[-1].start() if negative else -1
    if neg >= 0 and neg > pos and start-(max(0,start-140)+neg) <= 65:
        return "user_says_unavailable"
    if pos >= 0:
        return "user_says_available"
    return "mentioned"


def extract_evidence(messages: list[dict], edits: list[dict] | None = None) -> list[dict]:
    if edits is not None:
        entries = []
        for i, row in enumerate(edits[:18]):
            if not isinstance(row, dict):
                continue
            description = str(row.get("description") or "").strip()[:300]
            if not description:
                continue
            availability = row.get("availability")
            entries.append({
                "id": str(row.get("id") or "evidence-edit-%d" % i)[:60],
                "type": str(row.get("type") or "Other")[:60],
                "description": description,
                "availability": availability if availability in (
                    "mentioned", "user_says_available", "user_says_unavailable", "unknown") else "unknown",
                "verified": False,
                "source_message": row.get("source_message") if isinstance(row.get("source_message"), int) else None,
                "source_excerpt": str(row.get("source_excerpt") or "")[:160],
            })
        # Explicit user edits are authoritative as *reports*. Do not merge
        # different files they deliberately listed themselves.
        return entries

    found = {}
    for index, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        content = str(message.get("content") or "")[:2000]
        hits = [(name, m) for name, pattern in PATTERNS
                for m in re.finditer(pattern, content, re.I)]
        receipts = [m for k, m in hits if k == "Receipt"]
        hits = [(kind, match) for kind, match in hits if not (
            kind == "Payment Record" and any(
                _same_document(content, receipt, match) for receipt in receipts
            )
        )]
        for kind, match in hits:
            if kind == "Messages" and re.fullmatch(r"(?:messages?|texts?|chats?)", match.group(), re.I):
                # "WhatsApp messages" already has a more informative alias.
                if re.search(r"\bwhatsapp\s*$", content[max(0, match.start()-16):match.start()], re.I):
                    continue
            description = _describe(kind, content, match)
            availability = _availability(content, match.start())
            new = {
                "id": "evidence-" + kind.lower().replace(" ", "-"),
                "type": kind, "description": description,
                "availability": availability, "verified": False,
                "source_message": index, "source_excerpt": content[:160],
            }
            previous = found.get(kind)
            # Prefer a user-confirmed item or the more descriptive mention.
            if previous is None or (
                previous["availability"] != "user_says_available"
                and availability == "user_says_available"
            ) or (len(description) > len(previous["description"])
                  and previous["availability"] == availability):
                found[kind] = new
    return list(found.values())[:18]
