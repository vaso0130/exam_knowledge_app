#!/usr/bin/env python3
"""
Flask Development Server Entry Point
開發環境啟動檔案
"""
import os
# 載入環境變數
from dotenv import load_dotenv
load_dotenv()

from src.webapp import create_app
from src.ai_gateway import start_gateway_background

app = create_app()

if __name__ == '__main__':
    print("🚀 啟動 Flask 開發伺服器...")
    print(f"🌐 應用程式運行於: http://localhost:5000")
    print("🔧 使用 Ctrl+C 停止伺服器")
    # 啟動 AI Gateway + LSP（避免 Flask reloader 雙啟）
    gateway_port = int(os.getenv('AI_GATEWAY_PORT', '8002'))
    # 在 debug 時只於 reloader 子行程啟動；非 debug（如生產）則正常啟動
    if (os.environ.get('WERKZEUG_RUN_MAIN') == 'true') or (not app.debug):
        start_gateway_background(port=gateway_port)
    app.run(debug=True, host='0.0.0.0', port=5000)
