"""
对话库清理脚本：删除超过保留期（conversation_retention_days）的旧对话。

背景：conversations/messages 表会无限增长，多用户长期使用后积累大量
无价值的旧记录。保留期默认为 0（禁用，保持既有行为）；部署方可通过
环境变量 CONVERSATION_RETENTION_DAYS 或命令行参数 --days 显式开启，
并配合 cron 定时执行本脚本实现归档策略。

用法：
  python scripts/cleanup_db.py                 # 使用 CONVERSATION_RETENTION_DAYS（0=跳过）
  python scripts/cleanup_db.py --days 90       # 强制按 90 天清理
  python scripts/cleanup_db.py --dry-run       # 只统计将删除的数量，不真正删除
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
from src.database.db import DatabaseManager


def main():
    ap = argparse.ArgumentParser(description="对话库清理")
    ap.add_argument("--days", type=int, default=None,
                    help="保留天数（覆盖 CONVERSATION_RETENTION_DAYS；<=0 视为禁用）")
    ap.add_argument("--dry-run", action="store_true", help="只统计不删除")
    args = ap.parse_args()

    settings = get_settings()
    days = args.days if args.days is not None else settings.conversation_retention_days

    if days <= 0:
        print("保留天数未开启（CONVERSATION_RETENTION_DAYS=0），未做任何清理。")
        return

    db = DatabaseManager()
    if args.dry_run:
        # 统计：先按相同条件查出将删除的对话数，避免 dry-run 改动数据
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        n = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE updated_at < datetime('now', ?)",
            (f"-{days} days",),
        ).fetchone()[0]
        conn.close()
        print(f"[dry-run] 将删除 {days} 天未更新的旧对话: {n} 条（未执行删除）")
        return

    deleted = db.purge_old_conversations(days)
    print(f"已删除 {days} 天未更新的旧对话: {deleted} 条")


if __name__ == "__main__":
    main()
