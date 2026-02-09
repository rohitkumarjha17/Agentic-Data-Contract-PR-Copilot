from __future__ import annotations

import argparse
import json
from pathlib import Path
import yaml

from prcopilot.domain.schema import SchemaSnapshot
from prcopilot.domain.diff import diff_schemas


def _load_schema(path: Path) -> SchemaSnapshot:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SchemaSnapshot.model_validate(data)


def cmd_diff(args: argparse.Namespace) -> int:
    base = _load_schema(Path(args.base))
    head = _load_schema(Path(args.head))
    changeset = diff_schemas(base, head)

    out = changeset.model_dump()
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    else:
        print(json.dumps(out, indent=2))

    return 2 if changeset.breaking() else 0


def main() -> None:
    p = argparse.ArgumentParser(prog="prcopilot")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("diff", help="Diff two schema snapshots")
    d.add_argument("--base", required=True)
    d.add_argument("--head", required=True)
    d.add_argument("--out", required=False)
    d.set_defaults(func=cmd_diff)

    args = p.parse_args()
    raise SystemExit(args.func(args))
