"""Reviewable date parsing for civil-dispute intake, independent of case type.

A date reported for one event must never silently become the date of
another event. Partial dates are preserved without inferring a year.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any

_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
FULL_DATE = re.compile(
    rf"\b(?:\d{{1,2}}\s+{_MONTH},?\s+20\d{{2}}|"
    rf"{_MONTH}\s+\d{{1,2}},?\s+20\d{{2}}|"
    r"20\d{2}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]20\d{2})\b", re.I,
)
PARTIAL_DATE = re.compile(
    rf"\b(?:\d{{1,2}}\s+{_MONTH}|{_MONTH}\s+\d{{1,2}})\b", re.I,
)
RELATIVE_DATE = re.compile(
    r"\b(?:yesterday|today|last month|last week|two weeks ago|three days ago|recently)\b", re.I,
)
# Action stems describe grammatical events, not names, disputes or example data.
ACTION_WORD = re.compile(
    r"\b(?:refus\w*|deni\w*|denied|reject\w*|complain\w*|complaint|"
    r"purchas\w*|bought|buy|order\w*|request\w*|demand\w*|"
    r"return\w*|pay|paid|payment|withheld|withhold\w*|"
    r"deliver\w*|receiv\w*|received|send|sent|"
    r"cancel\w*|terminat\w*|resign\w*|dismiss\w*|"
    r"repair\w*|break|broke|broken|stop\w*|fail\w*|"
    r"sign\w*|mov\w*|vacat\w*|fire\w*|fired|"
    r"complete\w*|suppl\w*|issue\w*)\b", re.I,
)
_STEMS = (
    ("refus", "refusal"), ("deni", "denial"), ("denied", "denial"),
    ("reject", "rejection"), ("compl", "complaint"), ("purch", "purchase"),
    ("bought", "purchase"), ("buy", "purchase"), ("order", "order"),
    ("request", "request"), ("demand", "request"), ("return", "return"),
    ("pay", "payment"), ("paid", "payment"), ("withh", "withheld"),
    ("deliv", "delivery"), ("receiv", "receipt"), ("sent", "sending"),
    ("send", "sending"), ("cancel", "cancellation"), ("termin", "termination"),
    ("resign", "resignation"), ("dismis", "dismissal"), ("repair", "repair"),
    ("break", "breakage"), ("broke", "breakage"), ("broken", "breakage"),
    ("stop", "failure"), ("fail", "failure"), ("sign", "signing"),
    ("mov", "moving"), ("vacat", "vacating"), ("fired", "dismissal"),
    ("fire", "dismissal"), ("complet", "completion"), ("suppl", "supply"),
    ("issue", "issuance"),
)


def _actions(text: str) -> set[str]:
    words = ACTION_WORD.findall(text)
    result = set()
    for word in words:
        lower = word.casefold()
        result.add(next((label for prefix, label in _STEMS if lower.startswith(prefix)), lower))
    return result


def _normalize_full(value: str) -> str:
    value = re.sub(r",\s*", " ", value.strip())
    for fmt in ("%d %B %Y", "%B %d %Y", "%d %b %Y", "%b %d %Y",
                "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            parsed = datetime.strptime(value.title(), fmt)
            return f"{parsed.day} {parsed.strftime('%B %Y')}"
        except ValueError:
            continue
    return ""


def _normalize_partial(value: str) -> str:
    value = value.strip()
    for fmt in ("%d %B", "%B %d", "%d %b", "%b %d"):
        try:
            parsed = datetime.strptime(value.title(), fmt)
            return f"{parsed.day} {parsed.strftime('%B')}"
        except ValueError:
            continue
    # A partial date with Feb 29 may be valid in a leap year: retain rather
    # than declaring it invalid before the year is reported.
    if re.search(r"\b29\s+Feb(?:ruary)?\b|\bFeb(?:ruary)?\s+29\b", value, re.I):
        return "29 February"
    return ""


def reported_date_mentions(text: str) -> list[dict[str, str | int]]:
    """List explicit, relative and yearless dates in source order."""
    matches: list[dict[str, str | int]] = []
    occupied: list[tuple[int, int]] = []
    for kind, pattern in (("full", FULL_DATE), ("relative", RELATIVE_DATE), ("partial", PARTIAL_DATE)):
        for m in pattern.finditer(text):
            if any(a < m.end() and m.start() < b for a, b in occupied):
                continue
            normalized = (_normalize_full(m.group()) if kind == "full"
                          else _normalize_partial(m.group()) if kind == "partial"
                          else m.group())
            if not normalized:
                continue
            matches.append({"kind": kind, "text": normalized, "raw": m.group(),
                            "start": m.start(), "end": m.end()})
            occupied.append(m.span())
    return sorted(matches, key=lambda row: int(row["start"]))


def _clause(text: str, position: int) -> str:
    """Look at the clause containing the date, not a separate later action."""
    # An 'and' between two acts is a boundary. A date before that boundary
    # does not date the subsequent act by default.
    spans = list(re.finditer(r"\b(?:and|but|however|then)\b|[;.!?]", text, re.I))
    left = max((m.end() for m in spans if m.end() <= position), default=0)
    right = min((m.start() for m in spans if m.start() >= position), default=len(text))
    return text[left:right].strip()


def assess_event_date_reply(
    response: str, disputed_event: str, previous: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Assess whether a reply actually dates the disputed event.

    A standalone date is interpreted as answering the question. A date in
    a clause about a *different* action is not. An incomplete month/day never
    gets an inferred year, even when other messages mention a year.
    """
    value = str(response or "").strip()[:400]
    prev = previous or {}
    if re.fullmatch(r"20\d{2}", value) and prev.get("status") == "partial_year":
        partial = prev.get("candidate", "")
        full = _normalize_full(partial + " " + value)
        if full:
            return {"status": "accepted", "value": full, "candidate": full}

    if re.fullmatch(r"(?i)(?:yes|yes[,.]?\s+(?:on )?(?:the )?same day|same day)", value):
        if prev.get("status") == "different_event" and prev.get("kind") == "full":
            return {"status": "accepted", "value": prev.get("candidate", ""),
                    "candidate": prev.get("candidate", "")}
        if prev.get("status") in ("different_event", "partial_year") and prev.get("candidate"):
            return {"status": "partial_year", "value": "", "candidate": prev["candidate"]}
    mentions = reported_date_mentions(value)
    if not mentions:
        return {"status": "no_date", "value": "", "candidate": ""}
    expected_actions = _actions(disputed_event)
    judged = []
    for date in mentions:
        clause = _clause(value, int(date["start"]))
        actual_actions = _actions(clause)
        # Prefer the date explicitly linked to the disputed event. If the
        # reply contains only a date, it directly answers the asked question.
        direct = not actual_actions or bool(expected_actions & actual_actions)
        state = ("accepted" if date["kind"] != "partial" else "partial_year") if direct else "different_event"
        judged.append({"status": state, "value": str(date["text"]) if state == "accepted" else "",
                       "candidate": str(date["text"]), "kind": str(date["kind"])})
    selected = next((row for row in judged if row["status"] == "accepted"), None)
    if not selected:
        selected = next((row for row in judged if row["status"] == "partial_year"), None)
    if not selected:
        selected = judged[0]
    return selected


def date_clarification_question(disputed_event: str, outcome: dict[str, str]) -> str:
    """Produce a targeted followup with no invented date or event."""
    event = re.sub(r"\s+", " ", disputed_event).strip(" .,:;")[:130]
    candidate = outcome.get("candidate", "")
    status = outcome.get("status", "no_date")
    if status == "different_event":
        note = (f"You mentioned {candidate}, but that may describe a different event. "
                f"Was '{event}' on that date, or on another date? Please include the year if known. ")
    elif status == "partial_year":
        note = (f"You mentioned {candidate}, but the year is not confirmed. "
                f"What year did '{event}' happen? ")
    else:
        note = f"I could not identify a date for '{event}' in your last reply. Please give the date if known. "
    return "To clarify the date of this reported event: " + note + "If you do not know, say 'not known'."
