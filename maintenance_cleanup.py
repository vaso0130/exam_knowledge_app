#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資料庫定期清理腳本
清理孤立的知識點、過期會話、舊的非同步工作記錄等

使用方法：
python maintenance_cleanup.py [--dry-run] [--orphaned-only] [--schedule]

參數說明：
--dry-run: 只顯示統計，不實際刪除
--orphaned-only: 只清理孤立知識點
--schedule: 適合排程執行（靜默模式，只記錄日誌）
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from dotenv import load_dotenv

# 設定路徑以便導入模組
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.database import DatabaseManager

def setup_logging(schedule_mode=False):
    """設定日誌記錄"""
    log_level = logging.INFO if not schedule_mode else logging.WARNING
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    
    # 創建 logs 目錄（如果不存在）
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 設定日誌檔案
    log_file = os.path.join(log_dir, 'maintenance_cleanup.log')
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout) if not schedule_mode else logging.NullHandler()
        ]
    )

def display_cleanup_stats(stats, dry_run=False):
    """顯示清理統計資訊"""
    action = "將要清理" if dry_run else "已清理"
    
    print(f"\n🧹 資料庫清理統計 ({action}):")
    print("=" * 40)
    print(f"🔗 孤立知識點: {stats['orphaned_knowledge_points']} 個")
    print(f"⏰ 過期會話: {stats['expired_sessions']} 個")
    print(f"📋 舊非同步工作: {stats['old_async_jobs']} 個") 
    print(f"🔐 舊登入記錄: {stats['old_login_attempts']} 個")
    print("=" * 40)
    
    total = sum(stats.values())
    if total > 0:
        if dry_run:
            print(f"💡 總計發現 {total} 個項目可以清理")
            print("🚀 執行時使用不加 --dry-run 參數來實際清理")
        else:
            print(f"✅ 總計清理了 {total} 個項目")
    else:
        print("✨ 資料庫很乾淨，沒有需要清理的項目")

def cleanup_orphaned_only(db, dry_run=False):
    """只清理孤立知識點"""
    if dry_run:
        count = db.get_orphaned_knowledge_points_count()
        details = db.get_orphaned_knowledge_points_details()
        
        print(f"\n🔍 發現 {count} 個孤立知識點:")
        if details:
            print("詳細列表:")
            for kp in details[:10]:  # 只顯示前10個
                print(f"  - [{kp['subject']}] {kp['name']}")
            if len(details) > 10:
                print(f"  ... 還有 {len(details) - 10} 個")
        return count
    else:
        count = db.clean_orphaned_knowledge_points()
        print(f"✅ 清理了 {count} 個孤立知識點")
        return count

def main():
    """主函數"""
    # 載入環境變數
    load_dotenv()
    
    # 解析命令列參數
    parser = argparse.ArgumentParser(description='資料庫維護清理腳本')
    parser.add_argument('--dry-run', action='store_true', help='只顯示統計，不實際刪除')
    parser.add_argument('--orphaned-only', action='store_true', help='只清理孤立知識點')
    parser.add_argument('--schedule', action='store_true', help='排程模式（靜默運行）')
    args = parser.parse_args()
    
    # 設定日誌
    setup_logging(args.schedule)
    
    try:
        # 初始化資料庫連線
        db = DatabaseManager()
        
        # 記錄開始時間
        start_time = datetime.now()
        
        if not args.schedule:
            print("🧹 資料庫維護清理工具")
            print(f"📅 執行時間: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            if args.dry_run:
                print("🔍 預覽模式 (--dry-run): 只顯示統計，不會實際刪除資料")
        
        if args.orphaned_only:
            # 只清理孤立知識點
            count = cleanup_orphaned_only(db, args.dry_run)
            logging.info(f"孤立知識點處理: {'預覽' if args.dry_run else '清理'} {count} 個")
        else:
            # 全面清理
            stats = db.comprehensive_cleanup(dry_run=args.dry_run)
            
            if not args.schedule:
                display_cleanup_stats(stats, args.dry_run)
            
            # 記錄到日誌
            action = "預覽" if args.dry_run else "清理"
            total = sum(stats.values())
            logging.info(f"資料庫{action}完成: 處理 {total} 個項目 - "
                        f"孤立知識點:{stats['orphaned_knowledge_points']}, "
                        f"過期會話:{stats['expired_sessions']}, "
                        f"舊工作:{stats['old_async_jobs']}, "
                        f"舊記錄:{stats['old_login_attempts']}")
        
        # 計算執行時間
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        if not args.schedule:
            print(f"\n⏱️  執行時間: {duration:.2f} 秒")
        
        logging.info(f"清理腳本執行完成，耗時 {duration:.2f} 秒")
        
    except Exception as e:
        error_msg = f"清理過程中發生錯誤: {e}"
        logging.error(error_msg)
        if not args.schedule:
            print(f"❌ {error_msg}")
        sys.exit(1)

if __name__ == "__main__":
    main()
