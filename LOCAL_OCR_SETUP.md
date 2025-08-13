# 本地OCR安裝指導

## 1. 安裝 Tesseract OCR

### Windows 系統:

#### 方法一: 使用 winget (推薦)
```powershell
winget install UB-Mannheim.TesseractOCR
```

#### 方法二: 手動下載安裝
1. 前往 https://github.com/UB-Mannheim/tesseract/wiki
2. 下載最新版本的安裝檔 (tesseract-ocr-w64-setup-xxx.exe)
3. 執行安裝，記住安裝路徑 (通常是 C:\Program Files\Tesseract-OCR)

### 2. 配置環境變數 (如果需要)

如果 pytesseract 找不到 tesseract.exe，需要設定路徑：

在 Python 程式中加入：
```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

或設定系統環境變數：
- 將 `C:\Program Files\Tesseract-OCR` 加入 PATH 環境變數

### 3. 下載繁體中文語言包

Tesseract 預設只支援英文，需要下載中文語言包：

1. 前往 https://github.com/tesseract-ocr/tessdata_best
2. 下載 `chi_tra.traineddata` (繁體中文)
3. 將檔案放入 Tesseract 安裝目錄下的 `tessdata` 資料夾
   (通常是 `C:\Program Files\Tesseract-OCR\tessdata\`)

### 4. 驗證安裝

開啟命令提示字元或 PowerShell，執行：
```bash
tesseract --version
tesseract --list-langs
```

應該看到版本資訊和支援的語言列表（包含 chi_tra 和 eng）

### 5. 功能特色

- ✅ 本地處理，無需網路連線
- ✅ 支援繁體中文識別
- ✅ 支援程式碼識別（英文、數字、符號）
- ✅ 圖片預處理提高準確度
- ✅ 自動回退到 Google Vision API
- ✅ 詳細的狀態回報

### 6. 使用狀態

安裝完成後，筆記系統會自動：
1. 優先使用本地 Tesseract OCR
2. 如果本地識別失敗或結果太少，自動使用 Google Vision API
3. 在回應中標明使用的方法（本地OCR/線上OCR）

### 故障排除

如果遇到問題：
1. 確認 Tesseract 已正確安裝並在 PATH 中
2. 確認已下載繁體中文語言包
3. 查看控制台錯誤訊息，會有詳細的狀態資訊
