/**
 * 用於從失敗的 feynman 整理結果中恢復數據
 */

// 從原始 JSON 字符串中嘗試提取有效的 JSON 部分
function extractValidJson(text) {
    console.log("嘗試從文本中提取有效的 JSON");
    
    try {
        // 首先嘗試直接解析
        return JSON.parse(text);
    } catch (e) {
        console.log("直接解析失敗，嘗試提取 JSON 部分");
        
        // 尋找最外層的花括號
        const startIdx = text.indexOf('{');
        const endIdx = text.lastIndexOf('}');
        
        if (startIdx >= 0 && endIdx > startIdx) {
            const jsonText = text.substring(startIdx, endIdx + 1);
            try {
                return JSON.parse(jsonText);
            } catch (e2) {
                console.log("提取後仍解析失敗，嘗試清理控制字符");
                
                // 清理無效的控制字符
                const cleanedText = jsonText.replace(/[\u0000-\u001F\u007F-\u009F]/g, '');
                try {
                    return JSON.parse(cleanedText);
                } catch (e3) {
                    throw new Error("無法解析 JSON，即使在清理後");
                }
            }
        } else {
            throw new Error("找不到有效的 JSON 部分");
        }
    }
}

// 從原始錯誤回應中恢復 feynman 數據
function recoverFeynmanData(rawText) {
    console.log("嘗試恢復 feynman 數據");
    
    try {
        // 嘗試提取 JSON
        const jsonData = extractValidJson(rawText);
        console.log("成功提取 JSON:", jsonData);
        return jsonData;
    } catch (e) {
        console.error("JSON 提取失敗:", e);
        
        // 嘗試手動從文本中提取各個部分
        console.log("嘗試手動提取數據部分");
        const simpleExplanationMatch = rawText.match(/"simple_explanation"\s*:\s*"([^"]+)"/);
        const analogiesMatch = rawText.match(/"analogies"\s*:\s*\[(.*?)\]/s);
        const stepByStepMatch = rawText.match(/"step_by_step"\s*:\s*\[(.*?)\]/s);
        
        const result = {
            organized_content: "AI 整理結果 (格式已修復)"
        };
        
        if (simpleExplanationMatch) {
            result.simple_explanation = simpleExplanationMatch[1].replace(/\\"/g, '"').replace(/\\n/g, '\n');
        } else {
            result.simple_explanation = "無法提取簡單解釋部分";
        }
        
        // 嘗試提取類比部分
        if (analogiesMatch) {
            try {
                // 嘗試將類比部分包裝成有效的 JSON 數組並解析
                const analogiesJson = `[${analogiesMatch[1]}]`;
                result.analogies = JSON.parse(analogiesJson.replace(/\\"/g, '"').replace(/\\n/g, '\n'));
            } catch (e) {
                result.analogies = ["無法解析類比部分"];
            }
        } else {
            result.analogies = ["無類比數據"];
        }
        
        // 嘗試提取步驟部分
        if (stepByStepMatch) {
            try {
                const stepsJson = `[${stepByStepMatch[1]}]`;
                result.step_by_step = JSON.parse(stepsJson.replace(/\\"/g, '"').replace(/\\n/g, '\n'));
            } catch (e) {
                result.step_by_step = ["無法解析步驟部分"];
            }
        } else {
            result.step_by_step = ["無步驟數據"];
        }
        
        console.log("手動提取的結果:", result);
        return result;
    }
}

// 暴露給全局使用
window.recoverFeynmanData = recoverFeynmanData;
