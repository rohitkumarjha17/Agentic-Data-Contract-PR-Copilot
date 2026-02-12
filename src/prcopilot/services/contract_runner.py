from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List

import yaml

from prcopilot.domain.contract import ContractSpec, ContractReport, CheckResult


def _load_contract(path: Path) -> ContractSpec:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ContractSpec.model_validate(data)


def _load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows: List[Dict[str, str]] = []
        for row in reader:
            if not row:
                continue
            if not any((v or "").strip() for v in row.values()):
                continue
            rows.append({(k or "").lstrip("\ufeff"): (v or "") for k, v in row.items()})
        return rows


def _col_values(rows: List[Dict[str, str]], col: str) -> List[str]:
    return [r.get(col, "") for r in rows]


def run_contract(contract_path: Path, data_path: Path) -> ContractReport:
    contract = _load_contract(contract_path)
    rows = _load_csv(data_path)

    results: List[CheckResult] = []

    for rule in contract.rules:
        values = _col_values(rows, rule.column)

        for chk in rule.checks:
            t = chk.type.lower().strip()

            if t == "not_null":
                bad = [i for i, v in enumerate(values) if v is None or str(v).strip() == ""]
                passed = len(bad) == 0
                results.append(CheckResult(
                    column=rule.column,
                    check_type="not_null",
                    passed=passed,
                    details={"null_rows": bad[:20], "null_count": len(bad)},
                ))

            elif t == "unique":
                counts = Counter([str(v).strip() for v in values if str(v).strip() != ""])
                dups = [k for k, c in counts.items() if c > 1]
                passed = len(dups) == 0
                results.append(CheckResult(
                    column=rule.column,
                    check_type="unique",
                    passed=passed,
                    details={"duplicate_values": dups[:20], "duplicate_count": len(dups)},
                ))

            elif t == "min":
                min_val = chk.value
                bad_count = 0
                bad_samples = []
                for v in values:
                    s = str(v).strip()
                    if s == "":
                        continue
                    try:
                        num = float(s)
                        if min_val is not None and num < float(min_val):
                            bad_count += 1
                            if len(bad_samples) < 20:
                                bad_samples.append(s)
                    except Exception:
                        bad_count += 1
                        if len(bad_samples) < 20:
                            bad_samples.append(s)
                passed = bad_count == 0
                results.append(CheckResult(
                    column=rule.column,
                    check_type="min",
                    passed=passed,
                    details={"min": min_val, "bad_count": bad_count, "bad_samples": bad_samples},
                ))

            elif t == "regex":
                pat = chk.pattern or ""
                rx = re.compile(pat)
                bad_count = 0
                bad_samples = []
                for v in values:
                    s = str(v).strip()
                    if s == "":
                        continue
                    if not rx.match(s):
                        bad_count += 1
                        if len(bad_samples) < 20:
                            bad_samples.append(s)
                passed = bad_count == 0
                results.append(CheckResult(
                    column=rule.column,
                    check_type="regex",
                    passed=passed,
                    details={"pattern": pat, "bad_count": bad_count, "bad_samples": bad_samples},
                ))

            elif t == "allowed":
                allowed = set((chk.allowed or []))
                bad = [str(v).strip() for v in values if str(v).strip() != "" and str(v).strip() not in allowed]
                passed = len(bad) == 0
                results.append(CheckResult(
                    column=rule.column,
                    check_type="allowed",
                    passed=passed,
                    details={"allowed": sorted(list(allowed)), "bad_samples": bad[:20], "bad_count": len(bad)},
                ))

            else:
                results.append(CheckResult(
                    column=rule.column,
                    check_type=t,
                    passed=False,
                    details={"error": f"Unknown check type: {t}"},
                ))

    failed = sum(1 for r in results if not r.passed)
    return ContractReport(
        table=contract.table,
        total_checks=len(results),
        failed_checks=failed,
        results=results,
    )
