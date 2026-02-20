import json
import sys
from pathlib import Path

BREAKING_TYPES = {
    "drop_table",
    "remove_table",
    "remove_column",
    "drop_column",
    "change_type",
    "rename_column",
    "tighten_constraint",
}

def load_json(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def contract_failed(report: dict) -> bool:
    failed = report.get("failed_checks")
    if isinstance(failed, int):
        return failed > 0

    results = report.get("results")
    if isinstance(results, list):
        return any(r.get("passed") is False for r in results)

    return False

def is_breaking(change: dict) -> bool:
    if change.get("breaking") is True:
        return True
    sev = str(change.get("severity", "")).lower()
    if sev in {"breaking", "high", "critical"}:
        return True
    ctype = str(change.get("type", "")).lower()
    if ctype in BREAKING_TYPES:
        return True
    return False

def diff_breaking(diff: dict) -> bool:
    changes = diff.get("changes")
    if isinstance(changes, list):
        return any(is_breaking(c) for c in changes if isinstance(c, dict))
    return False

def main():
    diff = load_json(Path("artifacts/diff.json"))
    contract = load_json(Path("artifacts/contract_report.json"))

    bad_contract = contract_failed(contract)
    bad_schema = diff_breaking(diff)

    print(f"Schema breaking: {bad_schema}")
    print(f"Contract failed: {bad_contract}")

    if bad_schema or bad_contract:
        print("CI gate failed")
        sys.exit(1)

    print("CI gate passed")
    sys.exit(0)

if __name__ == "__main__":
    main()
