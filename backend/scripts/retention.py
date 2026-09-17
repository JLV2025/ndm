"""数据保留与归档工具

分层规则见 storage/file_manager.py 的模块文档。**归档是不可逆删除**，
改规则或第一次跑之前先 `--dry-run` 看清单。

用法：
    python scripts/retention.py --dry-run     # 只列清单，不改任何文件与数据（先跑这个）
    python scripts/retention.py               # 执行归档 + DB 收缩（不可逆）
    python scripts/retention.py --db-only     # 只收缩 DB，不碰文件
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage import get_connection, init_db, run_retention

DEFAULT_DATA_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="数据保留与归档（分层规则）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只列清单，不修改任何文件与数据")
    parser.add_argument("--db-only", action="store_true",
                        help="只做 DB 收缩（配置全文与日志），不碰文件")
    parser.add_argument("--data-root", default=DEFAULT_DATA_ROOT, help="数据根目录")
    args = parser.parse_args()

    init_db(args.data_root)
    conn = None if args.db_only else get_connection()
    result = run_retention(args.data_root, conn=conn, dry_run=args.dry_run)

    print(f"数据根目录：{args.data_root}")

    if args.dry_run:
        plan = result.get("plan", [])
        print(f"文件待处理 {len(plan)} 项：")
        for line in plan:
            print(f"  {line}")
        print(f"DB 待处理：配置全文置空 {result['config_cleared']} 条，"
              f"日志删除 {result['logs_deleted']} 条，"
              f"STP 快照删除 {result['stp_deleted']} 条")
        print("（--dry-run：未做任何修改）")
    else:
        print(f"归档 {result['archived']} 个周目录，删除 {result['deleted']} 个")
        print(f"配置全文置空 {result['config_cleared']} 条，日志删除 {result['logs_deleted']} 条，"
              f"STP 快照删除 {result['stp_deleted']} 条")

    for err in result["errors"]:
        print(f"  [错误] {err}")

    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
