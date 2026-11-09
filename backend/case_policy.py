"""Declarative case-type policy loader; no sample party, amount or date in logic.

Adding a category or subtype requires policy data, not edits in the planning
engine. Policy records are guidance templates, never legal determinations.
"""
from __future__ import annotations

import json
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
        questions.append({key: item[key] for key in ("id", "question", "label", "purpose")})
        if len(questions) >= _MAX_QUESTIONS:
            break
    combined["detail_questions"] = questions
    combined.pop("subtypes", None)
    combined["category"] = category
    combined["subtype"] = subtype
    return combined
