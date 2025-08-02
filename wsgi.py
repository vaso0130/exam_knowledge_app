#!/usr/bin/env python3
"""
WSGI Production Server Entry Point
使用 Waitress 作為生產級 WSGI 伺服器
"""
import os
from src.webapp import create_app
from waitress import serve

# 載入環境變數
from dotenv import load_dotenv
load_dotenv()

app = create_app()

if __name__ == '__main__':
    print("🚀 啟動 Waitress WSGI 伺服器...")
    print(f"🌐 應用程式運行於: http://0.0.0.0:8001")
    print("🔧 使用 Ctrl+C 停止伺服器")
    
    serve(app, host='0.0.0.0', port=8001, threads=6)
