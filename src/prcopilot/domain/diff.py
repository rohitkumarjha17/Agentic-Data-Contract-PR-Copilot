from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher

from pydantic import BaseModel, Field

from .schema import SchemaSnapshot, Table


class Severity(str, Enum):
    non_breaking = "non_breaking"
    breaking = "breaking"


class ChangeType(str, Enum):
    table_added = "table_added"
    table_removed = "table_removed"
    column_added = "column_added"
    column_removed = "column_removed"
    column_renamed = "column_renamed"
    column_type_changed = "column_type_changed"
    column_nullability_changed = "column_nullability_changed"
    primary_key_changed = "primary_key_changed"


class Change(BaseModel):
    severity: Severity
    change_type: ChangeType
    table: str
    column: Optional[str] = None
    details: Dict[str, str] = Field(default_factory=dict)


class ChangeSet(BaseModel):
    base_version: int
    head_version: int
    changes: List[Change] = Field(default_factory=list)

    def breaking(self) -> List[Change]:
        return [c for c in self.changes if c.severity == Severity.breaking]


def _is_type_change_breaking(old: str, new: str) -> bool:
    old = old.lower().strip()
    new = new.lower().strip()
    if old == new:
        return False

    numeric = {"int", "float", "double", "decimal"}
    if old in numeric and new in numeric:
        return False

    if {old, new} <= {"date", "timestamp"}:
        return False

    return True


def _pk_tuple(table: Table) -> Tuple[str, ...]:
    return tuple(sorted(table.primary_keys()))


def _tokens(name: str) -> set[str]:
    return set(name.lower().replace("-", "_").split("_"))


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _match_renames(bcols: Dict[str, object], hcols: Dict[str, object]) -> List[Tuple[str, str, float]]:
    """
    Heuristic rename detection:
    - only consider (removed, added) pairs with same type + nullable + primary_key
    - score by token overlap + name similarity
    - match greedily by best score (1-to-1)
    """
    removed = set(bcols) - set(hcols)
    added = set(hcols) - set(bcols)

    candidates: List[Tuple[float, str, str]] = []
    for r in removed:
        bc = bcols[r]
        for a in added:
            hc = hcols[a]
            if bc.type.lower().strip() != hc.type.lower().strip():
                continue
            if bc.nullable != hc.nullable:
                continue
            if bc.primary_key != hc.primary_key:
                continue

            token_bonus = 2.0 if (_tokens(r) & _tokens(a)) else 0.0
            score = token_bonus + _name_similarity(r, a)
            candidates.append((score, r, a))

    # If it's a single removed + single added and compatible, treat as rename even if score is low
    if len(removed) == 1 and len(added) == 1 and candidates:
        score, r, a = sorted(candidates, key=lambda x: x[0], reverse=True)[0]
        return [(r, a, score)]

    # Otherwise require some signal (token overlap or decent similarity)
    MIN_SCORE = 1.0

    candidates.sort(reverse=True, key=lambda x: x[0])
    used_r: set[str] = set()
    used_a: set[str] = set()
    matches: List[Tuple[str, str, float]] = []

    for score, r, a in candidates:
        if score < MIN_SCORE:
            break
        if r in used_r or a in used_a:
            continue
        used_r.add(r)
        used_a.add(a)
        matches.append((r, a, score))

    return matches


def diff_schemas(base: SchemaSnapshot, head: SchemaSnapshot) -> ChangeSet:
    cs = ChangeSet(base_version=base.version, head_version=head.version)

    base_tables = base.table_map()
    head_tables = head.table_map()

    # table added/removed
    for t in sorted(set(head_tables) - set(base_tables)):
        cs.changes.append(Change(severity=Severity.non_breaking, change_type=ChangeType.table_added, table=t))

    for t in sorted(set(base_tables) - set(head_tables)):
        cs.changes.append(Change(severity=Severity.breaking, change_type=ChangeType.table_removed, table=t))

    # tables in common
    for tname in sorted(set(base_tables) & set(head_tables)):
        bt = base_tables[tname]
        ht = head_tables[tname]

        # primary key change
        if _pk_tuple(bt) != _pk_tuple(ht):
            cs.changes.append(Change(
                severity=Severity.breaking,
                change_type=ChangeType.primary_key_changed,
                table=tname,
                details={"base_pk": ",".join(_pk_tuple(bt)), "head_pk": ",".join(_pk_tuple(ht))},
            ))

        bcols = bt.column_map()
        hcols = ht.column_map()

        # --- rename detection (must run before added/removed) ---
        renames = _match_renames(bcols, hcols)
        renamed_removed = {r for r, _, _ in renames}
        renamed_added = {a for _, a, _ in renames}

        for r, a, score in renames:
            bc = bcols[r]
            cs.changes.append(Change(
                severity=Severity.breaking,
                change_type=ChangeType.column_renamed,
                table=tname,
                column=a,  # show new name as primary column field
                details={
                    "base_column": r,
                    "head_column": a,
                    "type": bc.type,
                    "nullable": str(bc.nullable),
                    "score": f"{score:.2f}",
                },
            ))

        removed_cols = sorted((set(bcols) - set(hcols)) - renamed_removed)
        added_cols = sorted((set(hcols) - set(bcols)) - renamed_added)

        # column added/removed
        for c in added_cols:
            col = hcols[c]
            sev = Severity.breaking if col.nullable is False else Severity.non_breaking
            cs.changes.append(Change(
                severity=sev,
                change_type=ChangeType.column_added,
                table=tname,
                column=c,
                details={"type": col.type, "nullable": str(col.nullable)},
            ))

        for c in removed_cols:
            cs.changes.append(Change(
                severity=Severity.breaking,
                change_type=ChangeType.column_removed,
                table=tname,
                column=c,
            ))

        # modified columns (same name exists in both)
        for c in sorted(set(bcols) & set(hcols)):
            bc = bcols[c]
            hc = hcols[c]

            if _is_type_change_breaking(bc.type, hc.type):
                cs.changes.append(Change(
                    severity=Severity.breaking,
                    change_type=ChangeType.column_type_changed,
                    table=tname,
                    column=c,
                    details={"base_type": bc.type, "head_type": hc.type},
                ))

            if bc.nullable != hc.nullable:
                sev = Severity.breaking if (bc.nullable is True and hc.nullable is False) else Severity.non_breaking
                cs.changes.append(Change(
                    severity=sev,
                    change_type=ChangeType.column_nullability_changed,
                    table=tname,
                    column=c,
                    details={"base_nullable": str(bc.nullable), "head_nullable": str(hc.nullable)},
                ))

    return cs
