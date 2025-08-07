# 筆記編輯器增強方案：混合 LSP + AI 模式

## 架構總覽

層級 | 任務 | 建議方案 | 關鍵理由
--- | --- | --- | ---
編輯器 | Markdown 編輯體驗 | Monaco（React + TS 好整合） | VS Code 同源，API 完整
LSP 伺服器 | 結構/語法診斷 | Marksman 或 remark-language-server | 鏈結補全、標題大綱、診斷完整
AI Gateway | 語意摘要、重寫、關鍵字推薦 | FastAPI 轉接 AI | 使用者 API Key 不落地前端
Proxy | 瀏覽器 ↔ LSP | FastAPI WebSocket → Subprocess (stdin/stdout) | 一支服務搞定；部署簡單
前端 AI provider | 把 LLM 回傳文字變成 completion | 自訂 registerCompletionItemProvider('markdown', …) | 可與 LSP 建議合併排序

## 實現方案

### 1. LSP 處理的功能（本地端）
- Markdown 語法檢查與格式化
- 標題層級診斷（避免跳級）
- 鏈結檢查與補全
- 文件結構大綱生成
- 基本的自動完成（如列表項、代碼塊等）

### 2. AI 處理的功能（伺服器端）
- 高級語意分析與內容建議
- 專業術語解釋與內容增強
- 上下文感知的智能補全
- 學習內容優化建議
- 跨文件知識關聯

### 3. 整合策略
- LSP 伺服器處理基礎診斷與建議（預設啟用，持續提供即時協助）
- 前端整合 LSP 與 AI 建議，依照優先級排序
- 使用 WebSocket 保持低延遲的 LSP 通信
- AI 請求透過 API Gateway 進行，僅處理複雜任務
- AI 智慧偵測為選擇性功能（使用者主動啟用後才提供語意分析與上下文補全）

## 技術細節

### LSP 實現（Marksman）
```typescript
// 在前端初始化 LSP 客戶端
const lspClient = new LanguageClient(
  'markdown-lsp',
  'Markdown Language Server',
  {
    // 連接到本地 WebSocket 代理
    webSocket: {
      url: 'ws://localhost:3000/lsp/markdown'
    }
  }
);

// 啟動 LSP 客戶端
lspClient.start();
```

### FastAPI Proxy 實現
```python
@app.websocket("/lsp/markdown")
async def lsp_markdown_proxy(websocket: WebSocket):
    await websocket.accept()
    
    # 啟動 LSP 伺服器子進程
    process = await asyncio.create_subprocess_exec(
        "marksman", "server",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE
    )
    
    # 雙向轉發消息
    async def forward_to_lsp():
        while True:
            data = await websocket.receive_text()
            if process.stdin:
                process.stdin.write((data + "\r\n").encode())
                await process.stdin.drain()
    
    async def forward_from_lsp():
        if process.stdout:
            while not process.stdout.at_eof():
                data = await process.stdout.readline()
                await websocket.send_text(data.decode())
    
    # 同時處理雙向通信
    await asyncio.gather(
        forward_to_lsp(),
        forward_from_lsp()
    )
```

### AI Gateway 實現
```python
@app.post("/ai/enhance")
async def ai_content_enhance(request: EnhanceRequest):
    # 從筆記內容和增強請求生成增強內容
    ai_client = NoteAIClient()
    result = ai_client.generate_content_enhancement(
        request.enhancement_request,
        request.current_content,
        request.title,
        request.context
    )
    
    return result

@app.post("/ai/detect")
async def ai_detect_suggestions(request: DetectRequest):
    # 分析筆記內容，提供智慧建議
    ai_client = NoteAIClient()
    
    # 檢查用戶是否啟用了 AI 智慧偵測
    if not request.ai_enabled:
        # 未啟用 AI 智慧偵測，僅返回空結果
        return {
            "suggestions": [],
            "has_suggestions": False,
            "source": "ai_disabled"
        }
    
    # 檢查是否為複雜建議請求，若是簡單語法問題則不調用AI
    if request.request_type == "syntax_only":
        # 不使用 AI，依賴 LSP 結果
        return {"use_lsp": True}
    
    # 對於複雜語意分析，調用 AI
    result = ai_client.detect_and_suggest_text(
        request.content,
        request.context
    )
    
    return result
```

### 整合在前端

```typescript
// 註冊自定義 CompletionItemProvider，整合 LSP 和 AI 建議
monaco.languages.registerCompletionItemProvider('markdown', {
  provideCompletionItems: async (model, position) => {
    // 獲取上下文
    const textBeforeCursor = model.getValueInRange({
      startLineNumber: 1,
      startColumn: 1,
      endLineNumber: position.lineNumber,
      endColumn: position.column
    });
    
    // 首先獲取 LSP 的建議 (快速回應，預設啟用)
    const lspSuggestions = await getLspSuggestions(model, position);
    
    // 檢查使用者是否啟用了 AI 智慧偵測功能
    if (userSettings.aiAssistEnabled && needsAIEnhancement(textBeforeCursor, position)) {
      // 異步請求 AI 建議 (可能較慢)
      getAiSuggestions(textBeforeCursor).then(aiSuggestions => {
        // 整合並更新建議列表
        mergeSuggestions(lspSuggestions, aiSuggestions);
      });
    }
    
    // 優先返回 LSP 建議 (保持編輯流暢度)
    return {
      suggestions: lspSuggestions
    };
  }
});
```

## 使用者體驗設計

1. **LSP 與 AI 功能差異**
   - LSP 功能預設啟用，編輯筆記時自動提供即時診斷與建議
   - AI 智慧偵測為選擇性功能，使用者需主動開啟
   - 使用者介面提供明確的開關，讓使用者可自由控制 AI 輔助程度

## 效能優化策略

1. **分層處理**
   - 語法/結構問題優先透過 LSP 處理（更快、更高效）
   - 只有複雜的語意分析才傳送到 AI 服務

2. **建議緩存**
   - 常見模式和建議進行本地緩存
   - 相似內容的 AI 分析結果可重複利用

3. **延遲加載**
   - 首先顯示 LSP 建議
   - AI 建議作為增強在後台加載並整合

4. **智能分流**
   - 簡單任務：LSP + 前端處理
   - 中等任務：輔助 AI 模型
   - 複雜任務：主要 AI 模型

此混合架構結合了本地 LSP 的速度與 AI 的智能，提供了最佳的使用者體驗與效能平衡。
