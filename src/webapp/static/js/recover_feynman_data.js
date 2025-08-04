/**
 * 用於從失敗的 AI 整理結果中恢復數據
 * 支援費曼技巧和問答式學習等多種整理類型
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

// 從原始錯誤回應中恢復問答式學習數據
function recoverQALearningData(rawText) {
    console.log("嘗試恢復問答式學習數據");
    
    // 首先嘗試直接從原始文本中找出完整的 JSON 部分
    try {
        // 如果是已經格式化好的 JSON，可能有縮排和換行
        if (rawText.trim().startsWith("{") && rawText.trim().endsWith("}")) {
            console.log("問答式學習數據似乎已經是 JSON 格式");
            return JSON.parse(rawText);
        }
        
        // 嘗試從原始文本中找出 JSON 對象
        const jsonMatch = rawText.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
            const jsonText = jsonMatch[0];
            // 清理可能的控制字符
            const cleanedJson = jsonText.replace(/[\u0000-\u001F\u007F-\u009F]/g, '')
                                       .replace(/\\"/g, '"')
                                       .replace(/\\n/g, '\n');
            
            try {
                const parsed = JSON.parse(cleanedJson);
                console.log("成功從原始文本中提取問答式學習 JSON:", parsed);
                return parsed;
            } catch (innerErr) {
                console.error("嘗試解析提取的 JSON 失敗:", innerErr);
            }
        }
        
        // 嘗試提取 JSON
        const jsonData = extractValidJson(rawText);
        console.log("成功提取問答式學習 JSON:", jsonData);
        return jsonData;
    } catch (e) {
        console.error("問答式學習 JSON 提取失敗:", e);
        
        // 嘗試手動從文本中提取各個部分
        console.log("嘗試手動提取問答式學習數據部分");
        
        // 創建基本結果對象
        const result = {
            organized_content: "問答式學習 (格式已修復)",
            basic_questions: [],
            intermediate_questions: [],
            advanced_questions: [],
            answers: {}
        };
        
        // 提取基礎問題
        try {
            // 首先嘗試尋找完整的 basic_questions 數組
            const basicQuestionsMatch = rawText.match(/"basic_questions"\s*:\s*\[([\s\S]*?)\]/);
            if (basicQuestionsMatch) {
                // 提取數組內容並清理
                const content = basicQuestionsMatch[1];
                // 分割數組項
                const items = content.split(',').map(item => {
                    // 提取每個項中的文本內容
                    const cleaned = item.trim();
                    if (cleaned.startsWith('"') && cleaned.endsWith('"')) {
                        return cleaned.substring(1, cleaned.length - 1).replace(/\\"/g, '"');
                    }
                    return cleaned;
                }).filter(item => item.length > 0);
                
                result.basic_questions = items;
                console.log("手動提取的基礎問題:", items);
            } else {
                // 嘗試通過正則提取
                const matches = rawText.match(/"([^"]+\?[^"]*?)"/g);
                if (matches) {
                    result.basic_questions = matches.map(m => m.substring(1, m.length - 1));
                    console.log("通過問號提取的基礎問題:", result.basic_questions);
                } else {
                    // 如果無法通過 JSON 格式提取，嘗試通過文本模式匹配
                    const basicLines = rawText.split(/\n/).filter(line => 
                        line.includes("基礎問題") || 
                        (line.includes("?") && !line.includes(":")) ||
                        line.match(/^\s*[-*]\s*".*?"/)
                    );
                    
                    if (basicLines.length > 0) {
                        result.basic_questions = basicLines.map(line => {
                            // 提取引號中的內容或整行文本
                            const quoted = line.match(/"([^"]+)"/);
                            return quoted ? quoted[1] : line.trim().replace(/^[-*]\s*/, '');
                        });
                    } else {
                        result.basic_questions = ["無法提取基礎問題"];
                    }
                }
            }
        } catch (bqErr) {
            console.error("提取基礎問題失敗:", bqErr);
            result.basic_questions = ["提取基礎問題時發生錯誤"];
        }
        
        // 提取中級問題
        try {
            const intermediateQuestionsMatch = rawText.match(/"intermediate_questions"\s*:\s*\[(.*?)\]/s);
            if (intermediateQuestionsMatch) {
                const questionsJson = `[${intermediateQuestionsMatch[1]}]`;
                const cleanedJson = questionsJson.replace(/\\"/g, '"').replace(/\\n/g, '\n');
                result.intermediate_questions = JSON.parse(cleanedJson);
            }
        } catch (iqErr) {
            console.error("提取中級問題失敗:", iqErr);
        }
        
        // 提取高級問題
        try {
            const advancedQuestionsMatch = rawText.match(/"advanced_questions"\s*:\s*\[(.*?)\]/s);
            if (advancedQuestionsMatch) {
                const questionsJson = `[${advancedQuestionsMatch[1]}]`;
                const cleanedJson = questionsJson.replace(/\\"/g, '"').replace(/\\n/g, '\n');
                result.advanced_questions = JSON.parse(cleanedJson);
            }
        } catch (aqErr) {
            console.error("提取高級問題失敗:", aqErr);
        }
        
        // 提取答案 (這部分比較複雜，可能需要更複雜的正則表達式)
        try {
            const answersMatch = rawText.match(/"answers"\s*:\s*\{(.*?)\}/s);
            if (answersMatch) {
                const answersJson = `{${answersMatch[1]}}`;
                const cleanedJson = answersJson.replace(/\\"/g, '"').replace(/\\n/g, '\n');
                try {
                    result.answers = JSON.parse(cleanedJson);
                } catch (parseErr) {
                    // 如果無法解析完整的 answers 對象，嘗試提取個別問答對
                    const answerPairs = answersMatch[1].match(/"([^"]+)"\s*:\s*"([^"]+)"/g);
                    if (answerPairs) {
                        answerPairs.forEach(pair => {
                            const matches = pair.match(/"([^"]+)"\s*:\s*"([^"]+)"/);
                            if (matches) {
                                result.answers[matches[1]] = matches[2];
                            }
                        });
                    }
                }
            }
        } catch (ansErr) {
            console.error("提取答案失敗:", ansErr);
        }
        
        console.log("手動提取的問答式學習結果:", result);
        return result;
    }
}

// 通用資料恢復函數，根據類型選擇適當的恢復方法
function recoverOrganizationData(rawText, type) {
    console.log(`嘗試恢復 ${type} 類型的數據`);
    
    switch(type) {
        case 'feynman':
            return recoverFeynmanData(rawText);
        case 'qa_learning':
            return recoverQALearningData(rawText);
        default:
            // 對於其他類型，嘗試通用的 JSON 提取
            try {
                return extractValidJson(rawText);
            } catch (e) {
                console.error(`無法提取 ${type} 類型的數據:`, e);
                return { organized_content: `無法解析 ${type} 類型的數據` };
            }
    }
}

// 暴露給全局使用
window.recoverFeynmanData = recoverFeynmanData;
window.recoverQALearningData = recoverQALearningData;
window.recoverOrganizationData = recoverOrganizationData;
