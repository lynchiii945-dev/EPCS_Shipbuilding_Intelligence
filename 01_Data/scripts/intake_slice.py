# -*- coding: utf-8 -*-
"""统一资料入口命令。

只扫描 --root 下面的 01_Data/intake/inbox，不扫描盘符，不移动来源文件。
"""
import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "01_Data"))
sys.path.insert(0, str(_ROOT / "03_Application"))

from epcs_intake.service import IntakeService


def main(argv=None):
    parser = argparse.ArgumentParser(description="统一资料入口薄切片")
    parser.add_argument("--root", required=True, help="仓库或临时根目录")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("submit", help="登记入口里的文件和子文件夹")

    reviewer = sub.add_parser("reviewer", help="登记审核人")
    reviewer.add_argument("--name", required=True)
    reviewer.add_argument("--org-name", required=True)
    reviewer.add_argument("--org-code", required=True)

    approve = sub.add_parser("approve", help="审核通过并分流")
    approve.add_argument("--document", required=True)
    approve.add_argument("--reviewer", required=True)
    approve.add_argument("--reason", required=True)
    approve.add_argument("--zone", choices=("company", "personal"))

    reject = sub.add_parser("reject", help="驳回，不归档也不确认事实")
    reject.add_argument("--document", required=True)
    reject.add_argument("--reviewer", required=True)
    reject.add_argument("--reason", required=True)

    args = parser.parse_args(argv)
    service = IntakeService(args.root)
    if args.cmd == "submit":
        payload = service.submit_inbox()
    elif args.cmd == "reviewer":
        payload = {
            "person_id": service.register_reviewer(args.name, args.org_name, args.org_code)
        }
    elif args.cmd == "approve":
        payload = service.approve(args.document, args.reviewer, args.reason, zone=args.zone)
    else:
        service.reject(args.document, args.reviewer, args.reason)
        payload = {"document_id": args.document, "decision": "REJECT"}
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
