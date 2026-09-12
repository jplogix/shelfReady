"""Compare supplier record against lookup evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.enrichment.base import LookupRecord
from app.db.models import MatchOutcome


def _norm(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _tokens(s: str | None) -> set[str]:
    return {t for t in re.split(r"[\s/\-_,]+", _norm(s)) if t}


def _color_overlap(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return True  # missing = no conflict
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return True
    return bool(ta & tb) or _norm(a) in _norm(b) or _norm(b) in _norm(a)


def _brand_match(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return True
    na, nb = _norm(a), _norm(b)
    return na in nb or nb in na or na.split()[0] == nb.split()[0]


@dataclass
class FieldComparison:
    field_name: str
    supplier_value: Any
    evidence_value: Any
    outcome: MatchOutcome
    explanation: str


def compare_record(supplier: dict[str, Any], record: LookupRecord) -> list[FieldComparison]:
    comparisons: list[FieldComparison] = []

    def add(field: str, supplier_val: Any, evidence_val: Any, *, agree_fn) -> None:
        if evidence_val is None or str(evidence_val).strip() == "":
            return
        if supplier_val is None or str(supplier_val).strip() == "":
            comparisons.append(
                FieldComparison(
                    field_name=field,
                    supplier_value=supplier_val,
                    evidence_value=evidence_val,
                    outcome=MatchOutcome.matching_evidence,
                    explanation=f"Supplier missing {field}; external record provides '{evidence_val}'.",
                )
            )
            return
        if agree_fn(supplier_val, evidence_val):
            comparisons.append(
                FieldComparison(
                    field_name=field,
                    supplier_value=supplier_val,
                    evidence_value=evidence_val,
                    outcome=MatchOutcome.matching_evidence,
                    explanation=f"{field.title()} agrees: supplier '{supplier_val}' matches record '{evidence_val}'.",
                )
            )
        else:
            comparisons.append(
                FieldComparison(
                    field_name=field,
                    supplier_value=supplier_val,
                    evidence_value=evidence_val,
                    outcome=MatchOutcome.conflicting_evidence,
                    explanation=f"Supplier says '{supplier_val}'. The barcode record says '{evidence_val}'.",
                )
            )

    add("brand", supplier.get("brand"), record.brand, agree_fn=_brand_match)
    add("model", supplier.get("model"), record.model or record.mpn, agree_fn=lambda a, b: _norm(a) == _norm(b) or _norm(a) in _norm(b))
    add("size", supplier.get("size"), record.size, agree_fn=lambda a, b: _norm(a) == _norm(b))
    add("color", supplier.get("color"), record.color, agree_fn=_color_overlap)
    add(
        "pack_quantity",
        supplier.get("pack_quantity"),
        record.pack_quantity,
        agree_fn=lambda a, b: _norm(str(a)) == _norm(str(b)),
    )

    if record.title and supplier.get("title"):
        st, rt = _norm(supplier["title"]), _norm(record.title)
        if st not in rt and rt not in st and len(_tokens(st) & _tokens(rt)) < 2:
            comparisons.append(
                FieldComparison(
                    field_name="title",
                    supplier_value=supplier.get("title"),
                    evidence_value=record.title,
                    outcome=MatchOutcome.possible_match,
                    explanation=f"Title differs but may refer to the same product: '{supplier.get('title')}' vs '{record.title}'.",
                )
            )

    return comparisons


def overall_outcome(comparisons: list[FieldComparison]) -> MatchOutcome:
    if not comparisons:
        return MatchOutcome.no_match
    if any(c.outcome == MatchOutcome.conflicting_evidence for c in comparisons):
        return MatchOutcome.conflicting_evidence
    if any(c.outcome == MatchOutcome.possible_match for c in comparisons):
        return MatchOutcome.possible_match
    return MatchOutcome.matching_evidence
