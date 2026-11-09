"""Conservative extraction of explicitly named parties and locations.

These are suggestions from user words, not identity or address verification.
There are no sample business names or user-specific values in this module.
Ambiguous or generic parties are left missing so the intake can ask.
"""
from __future__ import annotations

import re

# Require an actual name (capitalization) after a category-relevant relationship.
# Never turn generic phrases such as "the seller" into fictitious legal names.
_TOKEN = r"[A-Z][A-Za-z0-9&'’.-]{1,}"
_NAME = rf"{_TOKEN}(?:\s+{_TOKEN}){{0,5}}"
_COMMON = {
    "Seller", "Shop", "Store", "Landlord", "Employer", "Company", "Client",
    "Customer", "Retailer", "Vendor", "Provider", "Owner", "Manager",
    "The", "This", "That", "Someone", "Somebody", "Unknown", "None",
    "A", "An", "Online", "Receipt", "Agreement", "Invoice",
}
_MONTHS = {
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
}


def _party_patterns(category: str) -> list[str]:
    """Generic grammatical relationships, not a vendor-name lookup table."""
    intro = rf"(?P<name>{_NAME})"
    rules = {
        "consumer": [
            rf"(?i:\b(?:purchased|bought|ordered)\b)[^\n.!?]{{0,140}}?(?i:\bfrom\s+)(?:the\s+)?{intro}",
            rf"(?i:\b(?:seller|retailer|merchant|store|shop|vendor|provider)\s+(?:named|called|is)\s+){intro}",
            rf"(?i:\b(?:seller|retailer|shop|store)\s*[:\-]\s*){intro}",
        ],
        "property": [
            rf"(?i:\b(?:my|the)\s+(?:landlord|owner|property manager)\s*,?\s*(?:named|called|is\s+)?){intro}",
            rf"(?i:\b(?:rented|leased)\b)[^\n.!?]{{0,120}}?(?i:\bfrom\s+){intro}",
        ],
        "employment": [
            rf"(?i:\b(?:my|the)\s+(?:employer|company|organization|firm)\s*,?\s*(?:named|called|is\s+)?){intro}",
            rf"(?i:\b(?:work|worked|working|employed)\s+(?:for|at|by)\s+){intro}",
        ],
        "contract": [
            rf"(?i:\b(?:my|the)\s+(?:client|customer|contractor|vendor|counterparty)\s*,?\s*(?:named|called|is\s+)?){intro}",
            rf"(?i:\b(?:sent|issued)\s+(?:an?\s+)?invoice\s+to\s+){intro}",
            rf"(?i:\b(?:provided|delivered)\s+[^\n.!?]{{0,90}}?\s+to\s+){intro}",
        ],
    }
    return rules.get(category, [])


def extract_counterparty(user_messages: list[str], category: str) -> str:
    """Return only a clearly named counterparty, or an empty string."""
    for message in user_messages:
        for pattern in _party_patterns(category):
            for match in re.finditer(pattern, message):
                name = match.group("name").strip(" ,.;:-")
                words = name.split()
                # "The seller" / "my landlord" / ordinary title words are
                # not proper names, even when capitalized at sentence start.
                if words and words[0] not in _COMMON and words[0] not in _MONTHS:
                    return name[:160]
    return ""


_STATES = (
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal", "Delhi", "Chandigarh", "Jammu and Kashmir", "Ladakh",
    "Puducherry", "Lakshadweep", "Andaman and Nicobar Islands",
    "Dadra and Nagar Haveli and Daman and Diu",
)
_STATE_NAMES = "|".join(re.escape(name) for name in sorted(_STATES, key=len, reverse=True))
_CITY = r"[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+){0,3}"
_LOCATION_PAIR = re.compile(
    rf"(?i:\b(?:in|at|located\s+in|based\s+in|place\s*:))\s+"
    rf"(?P<city>{_CITY})\s*,\s*(?P<state>{_STATE_NAMES})\b",
    re.I,
)


def extract_location(user_messages: list[str]) -> str:
    """Prefer explicitly provided city AND state; never infer a state from a city."""
    for message in user_messages:
        match = _LOCATION_PAIR.search(message)
        if match:
            city = re.sub(r"\s+", " ", match.group("city")).strip()
            state = re.sub(r"\s+", " ", match.group("state")).strip()
            return f"{city}, {state}"[:160]
    return ""
