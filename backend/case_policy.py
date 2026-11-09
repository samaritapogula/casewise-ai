"""Declarative case-type policy loader; no sample party, amount or date in logic.

Adding a category or subtype requires policy data, not edits in the planning
engine. Policy records are guidance templates, never legal determinations.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_POLICY_PATH = Path(__file__).with_name("case_policy.json")
_MAX_QUESTIONS = 8


@lru_cache(maxsize=1)
def _registry() -> dict:
    with _POLICY_PATH.open("r", encoding="utf-8") as src:
        raw = json.load(src)
    if not isinstance(raw.get("categories"), dict) or not isinstance(raw.get("default"), dict):
        raise ValueError("Case policy file has an invalid structure.")
    return raw


def get_case_policy(category: str, subtype: str = "") -> dict:
    raw = _registry()
    fallback = raw["default"]
    selected = raw["categories"].get(category, {})
    subtype_config = selected.get("subtypes", {}).get(subtype, {})
    combined = {**fallback, **{k: v for k, v in selected.items() if k != "subtypes"},
                **subtype_config}
    prompts = [*selected.get("detail_questions", []),
               *subtype_config.get("detail_questions", [])] if selected else fallback["detail_questions"]
    seen = set()
    questions = []
    for item in prompts:
        if not all(isinstance(item.get(k), str) and item[k].strip() for k in ("id", "question", "label", "purpose")):
            continue
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        question = {key: item[key] for key in ("id", "question", "label", "purpose")}
        # Only curated config patterns are allowed to suggest a reported answer.
        patterns = item.get("source_patterns", [])
        if isinstance(patterns, list):
            question["source_patterns"] = [p for p in patterns[:4]
                                          if isinstance(p, str) and 0 < len(p) <= 220]
        questions.append(question)
        if len(questions) >= _MAX_QUESTIONS:
            break
    combined["detail_questions"] = questions
    combined.pop("subtypes", None)
    combined["category"] = category
    combined["subtype"] = subtype
    return combined



def get_regional_source_ids(category: str, reported_location: str) -> list[str]:
    """Only include source IDs supported by an explicitly named state.

    A city name alone is insufficient to infer state law. Registry additions
    can cover more jurisdictions without changing the planning algorithm.
    """
    place = " ".join(str(reported_location or "").casefold().split())
    found = []
    for entry in _registry().get("regional_sources", []):
        if entry.get("category") != category:
            continue
        state = str(entry.get("state") or "").casefold().strip()
        if state and re.search(r"(?<!\w)" + re.escape(state) + r"(?!\w)", place):
            for source_id in entry.get("source_ids", []):
                if isinstance(source_id, str) and source_id not in found:
                    found.append(source_id)
    return found
