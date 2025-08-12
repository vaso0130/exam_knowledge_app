#!/usr/bin/env python3
"""
WSGI Production Server Entry Point
使用 Waitress 作為生產級 WSGI 伺服器
"""
import os
# 先載入 .env，確保稍後匯入的模組能讀到環境變數
from dotenv import load_dotenv
load_dotenv()

from src.webapp import create_app
from src.ai_gateway import start_gateway_background
from waitress import serve

app = create_app()

if __name__ == '__main__':
    print("🚀 啟動 Waitress WSGI 伺服器...")
    print(f"🌐 應用程式運行於: http://0.0.0.0:8001")
    print("🔧 使用 Ctrl+C 停止伺服器")
    # 背景啟動 AI Gateway + LSP（偏好 AI_GATEWAY_PORT，若占用則自動改用其他可用埠）
    gateway_port = int(os.getenv('AI_GATEWAY_PORT', '8002'))
    start_gateway_background(port=gateway_port)
    
    serve(app, host='0.0.0.0', port=8001, threads=6)
