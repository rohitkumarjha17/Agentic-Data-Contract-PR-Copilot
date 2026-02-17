import json
from pathlib import Path

def load_json(p: str):
    f = Path(p)
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None

diff = load_json("artifacts/diff.json") or {}
rep  = load_json("artifacts/contract_report.json") or {}

print("## PR Copilot Summary")
print("")
print("### Schema diff")
if diff:
    print(f"- Status:  generated")
else:
    print(f"- Status:  no diff.json found")
print("")
print("### Contract checks")
if rep:
    status = rep.get("status") or rep.get("result") or "unknown"
    print(f"- Status: {status}")
else:
    print(f"- Status:  no contract_report.json found")
