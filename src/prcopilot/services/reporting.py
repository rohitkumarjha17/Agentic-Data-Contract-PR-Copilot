from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class GateSummary:
    breaking_changes: int
    contract_failed_checks: int
    has_diff: bool
    has_contract: bool


def _safe_load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _fmt_change(c: Dict[str, Any]) -> str:
    sev = c.get("severity", "unknown")
    ctype = c.get("change_type", "unknown")
    table = c.get("table", "?")
    col = c.get("column")
    details = c.get("details") or {}

    if ctype == "column_renamed":
        base_col = details.get("base_column", "?")
        head_col = details.get("head_column", col or "?")
        return f"- {sev}: column_renamed `{table}` `{base_col}` -> `{head_col}`"

    if col:
        return f"- {sev}: {ctype} `{table}` `{col}`"

    return f"- {sev}: {ctype} `{table}`"


def _suggestions(diff: Optional[Dict[str, Any]], contract: Optional[Dict[str, Any]]) -> List[str]:
    tips: List[str] = []

    if diff:
        for c in diff.get("changes", []):
            ctype = c.get("change_type")
            sev = c.get("severity")
            details = c.get("details") or {}

            if ctype == "column_renamed":
                base_col = details.get("base_column", "old_name")
                head_col = details.get("head_column", "new_name")
                tips.append(
                    f"- rename: add a compatibility alias view or duplicate column `{head_col}` as `{base_col}` for 1 release, then deprecate"
                )

            if ctype == "column_added" and sev == "breaking":
                col = c.get("column", "new_col")
                tips.append(f"- new required column: backfill `{col}` or ship as nullable first, then tighten to NOT NULL later")

            if ctype == "column_removed":
                col = c.get("column", "old_col")
                tips.append(f"- removed column: keep `{col}` via view or derived column until downstream jobs migrate")

    if contract:
        failed = int(contract.get("failed_checks", 0))
        if failed > 0:
            tips.append("- data contract: fix failed checks first, then rerun pipeline and re-open PR")

    if not tips:
        tips.append("- no action needed: changes look safe based on current rules")

    # de-dup
    seen = set()
    out = []
    for t in tips:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out


def render_pr_comment(
    diff_path: Path,
    contract_path: Path,
    base_ref: str = "base",
    head_ref: str = "head",
) -> str:
    diff = _safe_load_json(diff_path)
    contract = _safe_load_json(contract_path)

    breaking = 0
    if diff:
        breaking = sum(1 for c in diff.get("changes", []) if c.get("severity") == "breaking")

    failed_checks = 0
    if contract:
        failed_checks = int(contract.get("failed_checks", 0))

    status = "PASS" if (breaking == 0 and failed_checks == 0) else "FAIL"

    lines: List[str] = []
    lines.append("<!-- prcopilot -->")
    lines.append(f"## PR Copilot Gate: {status}")
    lines.append("")
    lines.append(f"- schema breaking changes: **{breaking}**")
    lines.append(f"- contract failed checks: **{failed_checks}**")
    lines.append("")
    lines.append("### Schema diff")
    if not diff:
        lines.append("- diff.json not found or unreadable")
    else:
        changes = diff.get("changes", [])
        if not changes:
            lines.append("- no schema changes detected")
        else:
            for c in changes:
                lines.append(_fmt_change(c))

    lines.append("")
    lines.append("### Contract checks")
    if not contract:
        lines.append("- contract_report.json not found or unreadable")
    else:
        total = contract.get("total_checks", 0)
        failed = contract.get("failed_checks", 0)
        lines.append(f"- total checks: **{total}**, failed: **{failed}**")
        if int(failed) > 0:
            lines.append("")
            lines.append("Failed checks:")
            for r in contract.get("results", []):
                if not r.get("passed", True):
                    col = r.get("column", "?")
                    chk = r.get("check_type", "?")
                    lines.append(f"- `{col}` `{chk}` failed")

    lines.append("")
    lines.append("### Suggested fixes")
    lines.extend(_suggestions(diff, contract))

    lines.append("")
    lines.append("### Reproduce locally")
    lines.append("```bash")
    lines.append("prcopilot diff --base schemas/_base.yaml --head schemas/_head.yaml --out artifacts/diff.json")
    lines.append("prcopilot contract --contract contracts/orders_contract.yaml --data examples/data/orders.csv --out artifacts/contract_report.json")
    lines.append("```")

    return "\n".join(lines)


def write_pr_comment(diff_path: Path, contract_path: Path, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    md = render_pr_comment(diff_path=diff_path, contract_path=contract_path)
    out_path.write_text(md, encoding="utf-8")
