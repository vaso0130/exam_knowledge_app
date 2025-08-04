/**
 * 修復費曼技巧整理結果的 JSON 解析錯誤
 */

// 確保 renderMarkdown 函數存在
if (typeof window.renderMarkdown !== 'function') {
    window.renderMarkdown = function(text) {
        if (!text) return '';
        // 一個簡單的 markdown 渲染函數，主要處理換行和基本格式
        return text
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/^# (.*?)$/mg, '<h1>$1</h1>')
            .replace(/^## (.*?)$/mg, '<h2>$1</h2>')
            .replace(/^### (.*?)$/mg, '<h3>$1</h3>')
            .replace(/^#### (.*?)$/mg, '<h4>$1</h4>')
            .replace(/^- (.*?)$/mg, '• $1<br>');
    };
}

// 增強原有的 formatOrganizationResult 函數以處理 feynman 類型的 JSON 解析錯誤
function enhanceFormatOrganizationResult() {
    // 保存原始函數
    const originalFormatOrganizationResult = window.formatOrganizationResult;
    
    // 替換為增強版本
    window.formatOrganizationResult = function(result, type) {
        console.log(`增強版處理 ${type} 類型的結果`);
        
        // 對於 feynman 類型，嘗試修復可能的 JSON 解析錯誤
        if (type === 'feynman') {
            if (typeof result === 'string') {
                console.log('偵測到 feynman 結果為字符串，嘗試解析為 JSON');
                try {
                    // 嘗試解析 JSON 字符串
                    result = JSON.parse(result);
                    console.log('成功解析 feynman JSON 字符串');
                } catch (e) {
                    console.error('解析 feynman JSON 字符串失敗:', e);
                    
                    // 嘗試清理和修復 JSON 字符串
                    try {
                        // 移除 JSON 外的額外文字
                        let jsonText = result;
                        // 找到第一個 { 和最後一個 }
                        const startIdx = jsonText.indexOf('{');
                        const endIdx = jsonText.lastIndexOf('}');
                        
                        if (startIdx >= 0 && endIdx > startIdx) {
                            jsonText = jsonText.substring(startIdx, endIdx + 1);
                            
                            // 替換無效的控制字符
                            jsonText = jsonText.replace(/[\u0000-\u001F\u007F-\u009F]/g, '');
                            
                            // 嘗試再次解析
                            result = JSON.parse(jsonText);
                            console.log('成功修復並解析 feynman JSON 字符串');
                        }
                    } catch (repairErr) {
                        console.error('修復 feynman JSON 字符串失敗:', repairErr);
                        
                        // 創建一個基本的結果對象，包含原始字符串
                        result = {
                            organized_content: "JSON 解析失敗，顯示原始內容:",
                            simple_explanation: result
                        };
                    }
                }
            }
        }
        
        // 調用原始函數處理修復後的結果
        return originalFormatOrganizationResult(result, type);
    };
    
    console.log('已增強 formatOrganizationResult 函數來處理 feynman 類型的 JSON 解析錯誤');
}

// 在頁面載入後執行增強
document.addEventListener('DOMContentLoaded', function() {
    enhanceFormatOrganizationResult();
    console.log('費曼技巧 JSON 解析修復已啟用');
});

// 暴露修復函數以便手動調用
window.fixFeynmanParsing = enhanceFormatOrganizationResult;
