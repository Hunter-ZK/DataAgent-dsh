from __future__ import annotations

import argparse
import json
from agent3.contracts.authz import AuthzContext
from agent3.services.factory import build_demo_core


def main() -> None:
    parser = argparse.ArgumentParser(prog="agent3")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("sql")
    validate.add_argument("--metric")
    search = sub.add_parser("search-tables")
    search.add_argument("query")
    args = parser.parse_args()

    core = build_demo_core()
    authz = AuthzContext.system(purpose="cli")
    result = core.validate_sql(authz, args.sql, metric_id=args.metric) if args.command == "validate" else core.search_tables(authz, args.query)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
