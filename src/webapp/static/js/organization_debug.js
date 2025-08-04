/**
 * 用於診斷和除錯 AI 整理結果的工具函數
 */

// 診斷不同整理類型的問題
function diagnoseOrganizationIssue(type, result) {
    console.log(`診斷 ${type} 類型的整理結果:`, result);
    
    // 檢查基本問題
    if (!result) {
        console.error(`${type} 整理結果為 null 或 undefined`);
        return {
            status: 'error',
            message: `整理結果為空`,
            details: '收到的結果為 null 或 undefined，可能是 API 傳回空值'
        };
    }
    
    // 檢查類型
    if (typeof result === 'string') {
        try {
            // 嘗試解析 JSON
            const parsedResult = JSON.parse(result);
            console.log(`${type} 字符串成功解析為 JSON:`, parsedResult);
            return {
                status: 'warning',
                message: `整理結果是字符串形式的 JSON，已自動解析`,
                details: '整理結果需要額外解析步驟',
                parsed: parsedResult
            };
        } catch (e) {
            console.error(`${type} 字符串無法解析為 JSON:`, e);
            return {
                status: 'error',
                message: `整理結果是無效的 JSON 字符串`,
                details: `JSON 解析錯誤: ${e.message}`,
                raw: result.substring(0, 200) + "..."
            };
        }
    }
    
    // 檢查特定類型的結構
    const typeChecks = {
        'feynman': () => {
            const requiredFields = ['simple_explanation', 'analogies', 'step_by_step'];
            const missingFields = requiredFields.filter(field => !result[field]);
            
            if (missingFields.length > 0) {
                return {
                    status: 'warning',
                    message: `費曼技巧結果缺少必要欄位: ${missingFields.join(', ')}`,
                    details: '部分內容可能無法正確顯示',
                    available: Object.keys(result)
                };
            }
            
            return { status: 'ok', message: '費曼技巧結果結構完整' };
        },
        
        'qa_learning': () => {
            const requiredFields = ['basic_questions'];
            const recommendedFields = ['intermediate_questions', 'advanced_questions', 'answers'];
            
            const missingRequired = requiredFields.filter(field => !result[field]);
            const missingRecommended = recommendedFields.filter(field => !result[field]);
            
            if (missingRequired.length > 0) {
                return {
                    status: 'warning',
                    message: `問答式學習結果缺少必要欄位: ${missingRequired.join(', ')}`,
                    details: '基本問題無法顯示',
                    available: Object.keys(result)
                };
            }
            
            if (missingRecommended.length > 0) {
                return {
                    status: 'info',
                    message: `問答式學習結果缺少推薦欄位: ${missingRecommended.join(', ')}`,
                    details: '部分高級功能可能無法使用',
                    available: Object.keys(result)
                };
            }
            
            // 檢查答案與問題的對應
            if (result.answers && result.basic_questions) {
                const answeredQuestions = Object.keys(result.answers);
                const unansweredQuestions = result.basic_questions.filter(q => !answeredQuestions.includes(q));
                
                if (unansweredQuestions.length > 0) {
                    return {
                        status: 'info',
                        message: `${unansweredQuestions.length} 個問題沒有對應答案`,
                        details: '部分問題可能無法顯示答案'
                    };
                }
            }
            
            return { status: 'ok', message: '問答式學習結果結構完整' };
        },
        
        'hierarchical': () => {
            if (!result.main_points) {
                return {
                    status: 'warning',
                    message: '層次化重點整理缺少 main_points 欄位',
                    details: '無法顯示主要重點',
                    available: Object.keys(result)
                };
            }
            
            return { status: 'ok', message: '層次化重點整理結構完整' };
        },
        
        'mindmap': () => {
            if (!result.mindmap_data && !result.mindmap_structure) {
                return {
                    status: 'warning',
                    message: '心智圖缺少 mindmap_data 或 mindmap_structure 欄位',
                    details: '無法生成心智圖視覺化',
                    available: Object.keys(result)
                };
            }
            
            return { status: 'ok', message: '心智圖結構完整' };
        }
    };
    
    // 執行特定類型的檢查
    if (typeChecks[type]) {
        return typeChecks[type]();
    }
    
    // 通用檢查
    if (!result.organized_content) {
        return {
            status: 'warning',
            message: `${type} 整理結果缺少 organized_content 欄位`,
            details: '可能無法顯示完整內容',
            available: Object.keys(result)
        };
    }
    
    return { status: 'ok', message: `${type} 整理結果結構正常` };
}

// 顯示除錯資訊的函數
function showOrganizationDebugInfo(type, result) {
    const diagnosis = diagnoseOrganizationIssue(type, result);
    console.log(`${type} 診斷結果:`, diagnosis);
    
    // 創建一個可折疊的除錯信息
    let statusColorClass = '';
    switch (diagnosis.status) {
        case 'error': statusColorClass = 'danger'; break;
        case 'warning': statusColorClass = 'warning'; break;
        case 'info': statusColorClass = 'info'; break;
        case 'ok': statusColorClass = 'success'; break;
    }
    
    const debugId = `debug-${type}-${Date.now()}`;
    
    let html = `
        <div class="alert alert-${statusColorClass} mt-3 mb-3">
            <div class="d-flex justify-content-between align-items-center">
                <h6 class="mb-0">
                    <i class="fas fa-bug me-2"></i>
                    診斷: ${diagnosis.message}
                </h6>
                <button class="btn btn-sm btn-outline-secondary" 
                        data-bs-toggle="collapse"
                        data-bs-target="#${debugId}">
                    <i class="fas fa-info-circle"></i>
                    詳細信息
                </button>
            </div>
            <div id="${debugId}" class="collapse mt-2">
                <div class="bg-light p-2 rounded small">
                    <p class="mb-1">${diagnosis.details || '無詳細信息'}</p>
    `;
    
    // 添加可用欄位信息
    if (diagnosis.available) {
        html += `<p class="mb-1">可用欄位: ${diagnosis.available.join(', ')}</p>`;
    }
    
    // 添加原始數據預覽
    if (diagnosis.raw) {
        html += `
            <div class="mt-2">
                <strong>原始數據預覽:</strong>
                <pre class="mt-1 mb-0 bg-dark text-light p-2 rounded">${diagnosis.raw}</pre>
            </div>
        `;
    }
    
    html += `
                </div>
                <div class="text-end mt-2">
                    <button class="btn btn-sm btn-outline-primary retry-btn" data-type="${type}">
                        <i class="fas fa-sync-alt me-1"></i>
                        重試整理
                    </button>
                </div>
            </div>
        </div>
    `;
    
    return html;
}

// 暴露給全局使用
window.diagnoseOrganizationIssue = diagnoseOrganizationIssue;
window.showOrganizationDebugInfo = showOrganizationDebugInfo;

// 在頁面載入後添加全局事件監聽
document.addEventListener('DOMContentLoaded', function() {
    // 監聽除錯面板中的重試按鈕
    document.body.addEventListener('click', function(event) {
        if (event.target.closest('.retry-btn')) {
            const btn = event.target.closest('.retry-btn');
            const type = btn.dataset.type;
            
            if (type && window.regenerateOrganization) {
                console.log(`重新生成 ${type} 類型的整理結果`);
                window.regenerateOrganization(type, type);
            }
        }
    });
    
    console.log('AI 整理除錯工具已初始化');
});
