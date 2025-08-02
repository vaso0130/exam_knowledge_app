#!/usr/bin/env python3
"""
Flask Development Server Entry Point
開發環境啟動檔案
"""
# 載入環境變數
from dotenv import load_dotenv
load_dotenv()

from src.webapp import create_app

app = create_app()

if __name__ == '__main__':
    print("🚀 啟動 Flask 開發伺服器...")
    print(f"🌐 應用程式運行於: http://localhost:5000")
    print("🔧 使用 Ctrl+C 停止伺服器")
    app.run(debug=True, host='0.0.0.0', port=5000)
