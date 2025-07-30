#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
考題/知識整理桌面應用程式
主程式入口
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加 src 目錄到 Python 路徑
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

try:
    from src.core.database import DatabaseManager
    from src.core.gemini_client import GeminiClient
    from src.flows.info_flow import ContentProcessor
    from src.gui.main_window import ModernGUI
except ImportError as e:
    print(f"匯入模組失敗: {e}")
    print("請確認所有依賴套件已正確安裝")
    sys.exit(1)

class ExamKnowledgeApp:
    """考題知識整理應用程式主類別"""
    
    def __init__(self):
        self.db_manager = None
        self.gemini_client = None
        self.content_processor = None
        self.gui = None
        
    def initialize_components(self):
        """初始化所有組件"""
        try:
            print("正在初始化資料庫...")
            self.db_manager = DatabaseManager()
            
            print("正在初始化 Gemini 客戶端...")
            self.gemini_client = GeminiClient()
            
            print("正在初始化內容處理器...")
            self.content_processor = ContentProcessor(
                self.gemini_client, 
                self.db_manager
            )
            
            print("正在初始化使用者介面...")
            self.gui = ModernGUI(
                self.content_processor,
                self.db_manager
            )
            
            print("所有組件初始化完成！")
            return True
            
        except Exception as e:
            print(f"初始化失敗: {e}")
            return False
    
    def run(self):
        """啟動應用程式"""
        print("=" * 50)
        print("考題/知識整理桌面應用程式")
        print("=" * 50)
        
        # 檢查 Python 版本
        if sys.version_info < (3, 7):
            print("錯誤: 此應用程式需要 Python 3.7 或更高版本")
            sys.exit(1)
        
        # 建立必要目錄
        self.create_directories()
        
        # 初始化組件
        if not self.initialize_components():
            print("應用程式初始化失敗，程式結束")
            sys.exit(1)
        
        # 啟動 GUI
        try:
            print("啟動使用者介面...")
            self.gui.run()
        except Exception as e:
            print(f"GUI 啟動失敗: {e}")
            import traceback
            traceback.print_exc()
        
        print("應用程式已結束")
    
    def create_directories(self):
        """建立必要的目錄結構"""
        directories = [
            "./data",
            "./data/資料結構",
            "./data/資訊管理", 
            "./data/資通網路與資訊安全",
            "./data/資料庫應用"
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
        
        print("目錄結構建立完成")

def check_dependencies():
    """檢查依賴套件"""
    required_packages = [
        'google.generativeai',
        'customtkinter',
        'PIL',
        'docx',
        'PyPDF2',
        'bs4',
        'requests',
        'dotenv',
        'asyncio_throttle'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("缺少以下必要套件:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\n請執行以下命令安裝:")
        print("pip install -r requirements.txt")
        return False
    
    return True

def main():
    """主函式"""
    # 檢查依賴套件
    if not check_dependencies():
        sys.exit(1)
    
    # 建立並啟動應用程式
    app = ExamKnowledgeApp()
    app.run()

if __name__ == "__main__":
    main()
