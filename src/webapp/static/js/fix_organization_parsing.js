/**
 * 修復 AI 整理結果的 JSON 解析錯誤
 * 支援多種整理類型：費曼技巧、問答式學習等
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

// 增強原有的 formatOrganizationResult 函數以處理各種整理類型的 JSON 解析錯誤
function enhanceFormatOrganizationResult() {
    // 保存原始函數
    const originalFormatOrganizationResult = window.formatOrganizationResult;
    
    // 如果原始函數不存在，則不進行替換
    if (typeof originalFormatOrganizationResult !== 'function') {
        console.log('formatOrganizationResult 函數尚未定義，跳過增強');
        return;
    }
    
    // 替換為增強版本
    window.formatOrganizationResult = function(type, result) {
        console.log(`增強版處理 ${type} 類型的結果`, result);
        
        // 檢查結果是否已經是物件，如果是則直接使用
        if (typeof result === 'object' && result !== null) {
            console.log(`${type} 結果已經是物件，直接使用`);
            return originalFormatOrganizationResult(type, result);
        }
        
        // 檢查結果是否為字符串，如果是則嘗試解析
        if (typeof result === 'string') {
            console.log(`偵測到 ${type} 結果為字符串，嘗試解析為 JSON`);
            try {
                // 嘗試解析 JSON 字符串
                const parsedResult = JSON.parse(result);
                console.log(`成功解析 ${type} JSON 字符串`);
                return originalFormatOrganizationResult(type, parsedResult);
            } catch (e) {
                console.error(`解析 ${type} JSON 字符串失敗:`, e);
                
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
                        const repairedResult = JSON.parse(jsonText);
                        console.log(`成功修復並解析 ${type} JSON 字符串`);
                        return originalFormatOrganizationResult(type, repairedResult);
                    }
                } catch (repairErr) {
                    console.error(`修復 ${type} JSON 字符串失敗:`, repairErr);
                    
                    // 使用專門的恢復函數（如果存在）
                    if (window.recoverOrganizationData) {
                        try {
                            const recoveredResult = window.recoverOrganizationData(result, type);
                            console.log(`使用專門的恢復函數處理 ${type} 數據`);
                            return originalFormatOrganizationResult(type, recoveredResult);
                        } catch (recoverErr) {
                            console.error(`使用專門函數恢復 ${type} 數據失敗:`, recoverErr);
                        }
                    }
                    
                    // 創建一個基本的結果對象，包含原始字符串
                    const fallbackResult = {
                        organized_content: `JSON 解析失敗，顯示原始內容:`,
                        error_details: `無法解析 ${type} 類型的整理結果`,
                        raw_content: result.substring(0, 500) + "..."
                    };
                    return originalFormatOrganizationResult(type, fallbackResult);
                }
            }
        }
        
        // 調用原始函數處理其他情況
        return originalFormatOrganizationResult(type, result);
    };
    
    console.log('已增強 formatOrganizationResult 函數來處理各種整理類型的 JSON 解析錯誤');
}

// 在頁面載入後延遲執行增強，確保 note_detail.js 已經載入
document.addEventListener('DOMContentLoaded', function() {
    // 延遲執行以確保其他腳本已載入
    setTimeout(function() {
        enhanceFormatOrganizationResult();
        console.log('AI 整理結果 JSON 解析修復已啟用');
    }, 100);
});

// 暴露修復函數以便手動調用
window.fixOrganizationParsing = enhanceFormatOrganizationResult;
