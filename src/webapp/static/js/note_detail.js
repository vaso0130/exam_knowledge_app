// note_detail.js - 筆記詳情頁面的 JavaScript 功能

// 全域變數
let currentNoteId = null; // 將從 HTML 中獲取
let loadingModal;
let organizationAnalysisIds = {}; // 儲存 type 與 analysis_id 的對應關係

// 頁面載入時檢查預先生成的結果
document.addEventListener('DOMContentLoaded', function () {
        // 初始化 loading modal
        loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));

        // 全域錯誤處理
        window.addEventListener('error', function (event) {
            console.error('全域錯誤捕獲:', event.error);

            // 檢查是否為 JSON 解析錯誤
            if (event.error instanceof SyntaxError && event.error.message.includes('JSON')) {
                console.warn('偵測到 JSON 解析錯誤，可能是 AI 回傳的資料格式有問題');
                showAlert('偵測到資料格式錯誤，系統將嘗試自動修復', 'warning');

                // 如果修復函數存在，嘗試運行
                if (typeof window.fixFeynmanParsing === 'function') {
                    window.fixFeynmanParsing();
                }
            }
        });

        loadPreGeneratedResults();
        initializeContentTabs();
    });

    // 初始化內容標籤頁
function initializeContentTabs() {
    // 使用事件委派，監聽整個標籤容器
    const contentTabs = document.getElementById('content-tabs');
    
    // 停止任何可能已經存在的事件監聽器（避免重複綁定）
    if (contentTabs.dataset.eventsBound) return;
    contentTabs.dataset.eventsBound = 'true';
    
    // 使用事件委派處理點擊
    contentTabs.addEventListener('click', function(event) {
        // 找到可能被點擊的標籤按鈕
        const triggerEl = event.target.closest('button[data-bs-toggle="tab"]');
        
        if (triggerEl && triggerEl.id !== 'add-organization-tab') {
            event.preventDefault();
            
            // 防止刪除按鈕的點擊事件觸發標籤切換
            if (event.target.closest('button[onclick*="removeOrganizationTab"]')) {
                return;
            }
            
            // 啟動標籤
            const tabTrigger = new bootstrap.Tab(triggerEl);
            tabTrigger.show();
        }
    });
    
    // 使用事件委派監聽所有標籤頁的顯示事件
    document.body.addEventListener('shown.bs.tab', function(event) {
        if (!event.target.matches('button[data-bs-toggle="tab"]')) return;
        
        // 獲取目標面板ID
        const targetPaneId = event.target.getAttribute('data-bs-target');
        if (!targetPaneId) return;
        
        // 找到對應的標籤面板
        const targetPane = document.querySelector(targetPaneId);
        if (!targetPane) return;
        
        console.log(`Tab switched to ${targetPaneId}`);
        
        // 找到該標籤頁中的所有圖表容器
        const chartContainers = targetPane.querySelectorAll('.mindmap-container, .chart-container');
        
        // 重設所有找到的圖表
        chartContainers.forEach(container => {
            // 等待標籤頁完全顯示（動畫完成）後再調整圖表大小
            setTimeout(() => {
                const chartInstance = echarts.getInstanceByDom(container);
                if (chartInstance) {
                    chartInstance.resize();
                    console.log(`Chart in ${targetPaneId} has been resized`);
                }
            }, 300);
        });
    });
}

    // 顯示組織方式選擇器
    function showOrganizationSelector() {
        const organizationTypes = [
            { type: 'mindmap', name: '心智圖結構化', icon: 'sitemap' },
            { type: 'hierarchical', name: '層次化重點整理', icon: 'list' },
            { type: 'feynman', name: '費曼技巧解析', icon: 'lightbulb' },
            { type: 'qa_learning', name: '問答式學習', icon: 'question' },
            { type: 'comparison', name: '對比分析整理', icon: 'balance-scale' },
            { type: 'memory_palace', name: '記憶宮殿法', icon: 'home' },
            { type: 'format_enhance', name: '格式化與補強 (將直接替換原始內容)', icon: 'magic' }
        ]; let modalHtml = `
        <div class="modal fade" id="organizationModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title"><i class="fas fa-magic me-2"></i>選擇整理方式</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
    `;

        organizationTypes.forEach(type => {
            // 檢查是否已經有這個標籤
            const existingTab = document.getElementById(`${type.type}-tab`);
            if (!existingTab) {
                modalHtml += `
                <div class="col-md-6 mb-3">
                    <button class="btn btn-outline-primary w-100 text-start organization-btn"
                            data-type="${type.type}" 
                            data-name="${type.name}" 
                            data-icon="${type.icon}">
                        <i class="fas fa-${type.icon} me-2"></i>
                        <strong>${type.name}</strong>
                    </button>
                </div>
            `;
            }
        });

        modalHtml += `
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

        // 移除舊的 modal（如果存在）
        const oldModal = document.getElementById('organizationModal');
        if (oldModal) {
            oldModal.remove();
        }

        // 添加新的 modal
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // 顯示 modal
        const modal = new bootstrap.Modal(document.getElementById('organizationModal'));

        // 使用事件委派方式處理按鈕點擊
        const modalElement = document.getElementById('organizationModal');
        modalElement.addEventListener('click', function (event) {
            // 檢查點擊的是否是組織按鈕
            if (event.target.closest('.organization-btn')) {
                const btn = event.target.closest('.organization-btn');
                const type = btn.getAttribute('data-type');
                const name = btn.getAttribute('data-name');
                const icon = btn.getAttribute('data-icon');
                selectOrganizationType(type, name, icon);
            }
        });

        modal.show();
    }

    // 選擇組織方式並生成
    function selectOrganizationType(type, name, icon) {
        console.log(`選擇整理類型: ${type}, 名稱: ${name}`);

        // 關閉 modal - 使用更健壯的方式
        try {
            const modalElement = document.getElementById('organizationModal');
            if (modalElement) {
                const modal = bootstrap.Modal.getInstance(modalElement);
                if (modal) {
                    modal.hide();
                } else {
                    // 如果無法獲取實例，直接移除modal的show類和backdrop
                    modalElement.classList.remove('show');
                    const backdrop = document.querySelector('.modal-backdrop');
                    if (backdrop) backdrop.remove();
                }
            }
        } catch (e) {
            console.error("關閉模態框時出錯:", e);
        }

        // 對於格式化與補強，顯示特別警告
        if (type === 'format_enhance') {
            if (!confirm('警告：格式化與補強功能將直接替換您的原始筆記內容！是否確定要繼續？')) {
                return; // 用戶取消，中止操作
            }
        }

        // 開始生成
        loadingModal.show();

        fetch(`/notes/${currentNoteId}/organize`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                organization_type: type
            })
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`伺服器回應錯誤，狀態碼: ${response.status}`);
                }

                // 嘗試解析為JSON，如果失敗則返回原始文本以進行調試
                return response.json().catch(err => {
                    console.error("JSON解析失敗:", err);
                    return response.text().then(text => {
                        return {
                            success: false,
                            error: "JSON解析失敗",
                            raw_text: text,
                            parse_error: err.toString()
                        };
                    });
                });
            })
            .then(data => {
                loadingModal.hide();

                // 特殊處理JSON解析失敗的情況
                if (data.raw_text) {
                    console.error("API回傳的資料無法解析為JSON:", data.parse_error);
                    console.log("原始回應:", data.raw_text.substring(0, 500) + "...");

                    if (type === 'feynman' && window.fixFeynmanParsing) {
                        // 對於費曼類型，嘗試自動修復並重試
                        showAlert('正在嘗試修復費曼技巧的 JSON 格式...', 'warning');
                        window.fixFeynmanParsing();

                        // 嘗試使用專門的恢復機制
                        if (window.recoverOrganizationData) {
                            try {
                                // 這裡特別處理 qa_learning 類型
                                let recoveredData;
                                if (type === 'qa_learning') {
                                    // 對於問答式學習，嘗試直接從原始文本中提取JSON
                                    try {
                                        console.log("嘗試為問答式學習解析JSON...");
                                        // 找到 JSON 的開始和結束
                                        const jsonStart = data.raw_text.indexOf('{');
                                        const jsonEnd = data.raw_text.lastIndexOf('}') + 1;
                                        if (jsonStart >= 0 && jsonEnd > jsonStart) {
                                            const jsonText = data.raw_text.substring(jsonStart, jsonEnd);
                                            // 清理控制字符
                                            const cleanedJson = jsonText.replace(/[\u0000-\u001F\u007F-\u009F]/g, '');
                                            recoveredData = JSON.parse(cleanedJson);
                                            console.log("成功直接解析問答式學習數據:", recoveredData);
                                        }
                                    } catch (jsonErr) {
                                        console.error("直接解析JSON失敗，將使用恢復機制:", jsonErr);
                                        recoveredData = window.recoverOrganizationData(data.raw_text, type);
                                    }
                                } else {
                                    // 其他類型使用標準恢復機制
                                    recoveredData = window.recoverOrganizationData(data.raw_text, type);
                                }

                                if (recoveredData) {
                                    console.log(`成功恢復 ${type} 資料:`, recoveredData);

                                    // 創建臨時 ID 並添加標籤頁
                                    organizationAnalysisIds[type] = Date.now();
                                    addOrganizationTab(type, name, icon, recoveredData);
                                    showAlert(`${name} 整理資料已成功修復！`, 'success');
                                    return;
                                }
                            } catch (recoverErr) {
                                console.error(`恢復 ${type} 資料失敗:`, recoverErr);
                            }
                        }
                        // 向下相容支援舊版恢復函數
                        else if (window.recoverFeynmanData && type === 'feynman') {
                            try {
                                let recoveredData = window.recoverFeynmanData(data.raw_text);
                                if (recoveredData) {
                                    console.log("成功恢復 feynman 資料:", recoveredData);

                                    // 創建臨時 ID 並添加標籤頁
                                    organizationAnalysisIds[type] = Date.now();
                                    addOrganizationTab(type, name, icon, recoveredData);
                                    showAlert(`${name} 整理資料已成功修復！`, 'success');
                                    return;
                                }
                            } catch (recoverErr) {
                                console.error("恢復 feynman 資料失敗:", recoverErr);
                            }
                        }

                        try {
                            // 通用的 JSON 修復嘗試
                            let rawText = data.raw_text;
                            // 尋找 JSON 部分
                            let jsonStart = rawText.indexOf('{');
                            let jsonEnd = rawText.lastIndexOf('}');
                            if (jsonStart >= 0 && jsonEnd > jsonStart) {
                                let jsonText = rawText.substring(jsonStart, jsonEnd + 1);
                                // 替換控制字符
                                jsonText = jsonText.replace(/[\u0000-\u001F\u007F-\u009F]/g, '');
                                let result = JSON.parse(jsonText);

                                // 成功解析，創建模擬的API成功回應
                                organizationAnalysisIds[type] = Date.now(); // 臨時ID
                                addOrganizationTab(type, name, icon, result);
                                showAlert(`${name} 整理成功修復！`, 'success');
                                return;
                            }
                        } catch (e) {
                            console.error("自動修復失敗:", e);
                        }
                    }

                    showAlert(`解析 ${name} 回應資料失敗，請查看控制台獲取詳細信息`, 'danger');
                    return;
                }

                // 正常處理成功的API回應
                if (data.success) {
                    // 儲存新生成的 analysis_id
                    if (data.analysis_id) {
                        organizationAnalysisIds[type] = data.analysis_id;
                    }

                    try {
                        addOrganizationTab(type, name, icon, data.result);
                        showAlert(`${name} 整理完成！`, 'success');
                    } catch (tabError) {
                        console.error("創建標籤頁時出錯:", tabError);
                        showAlert(`創建 ${name} 標籤頁失敗: ${tabError.message}`, 'danger');
                    }
                } else {
                    showAlert('AI 整理失敗：' + (data.error || '未知錯誤'), 'danger');
                }
            })
            .catch(error => {
                loadingModal.hide();
                console.error("整理過程中出錯:", error);
                showAlert('發生錯誤：' + error.message, 'danger');
            });
    }

    // 添加新的組織標籤頁
    function addOrganizationTab(type, name, icon, result) {
        console.log(`嘗試添加 ${type} 標籤頁...`, { name, icon });
        console.log(`結果數據類型: ${typeof result}, 是否為空: ${!result}`);

        // 檢查是否已經存在相同類型的標籤頁
        const existingTab = document.getElementById(`${type}-tab`);
        if (existingTab) {
            console.log(`標籤頁 ${type} 已存在，更新內容而非重新創建`);
            // 更新現有標籤頁的內容
            const existingContent = document.getElementById(`${type}-content`);
            if (existingContent) {
                const formattedContent = formatOrganizationResult(result, type);
                existingContent.querySelector('.note-content').innerHTML = formattedContent;
                console.log(`${type} 標籤頁內容已更新`);
                
                // 更新完內容後，重新調整圖表大小
                setTimeout(() => {
                    const chartContainer = existingContent.querySelector('.mindmap-container');
                    if (chartContainer) {
                        const chartInstance = echarts.getInstanceByDom(chartContainer);
                        if (chartInstance) {
                            chartInstance.resize();
                            console.log(`Updated chart in ${type}-content has been resized`);
                        }
                    }
                }, 300);
            }
            return;
        }

        // 驗證必要的DOM元素
        const addTabButton = document.getElementById('add-organization-tab');
        const tabContent = document.getElementById('content-tab-content');

        if (!addTabButton || !tabContent) {
            console.error('找不到必要的DOM元素來創建標籤頁');
            return;
        }

        try {
            // 添加標籤按鈕，使用更明確的HTML結構防止事件衝突
            const newTabHtml = `
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="${type}-tab" data-bs-toggle="tab" data-bs-target="#${type}-content" type="button" role="tab">
                    <span class="tab-content-wrapper">
                        <i class="fas fa-${icon} me-1"></i>${name}
                    </span>
                    <button class="btn btn-sm ms-2 remove-tab-btn" onclick="event.stopPropagation(); removeOrganizationTab('${type}');" title="移除" style="background:none;border:none;color:inherit;">
                        <i class="fas fa-times" style="font-size: 0.8em;"></i>
                    </button>
                </button>
            </li>
        `;
            addTabButton.parentElement.insertAdjacentHTML('beforebegin', newTabHtml);

            // 格式化內容
            const formattedContent = formatOrganizationResult(result, type);
            console.log(`${type} 格式化後的內容長度: ${formattedContent.length}`);

            // 添加標籤內容
            const newContentHtml = `
            <div class="tab-pane fade" id="${type}-content" role="tabpanel">
                <div class="note-content markdown-content mt-3">
                    ${formattedContent}
                </div>
            </div>
        `;
            tabContent.insertAdjacentHTML('beforeend', newContentHtml);

            // 啟動新標籤（僅在第一個標籤頁時自動切換）
            const existingTabs = document.querySelectorAll('#content-tabs .nav-link:not(#add-organization-tab)');
            if (existingTabs.length === 2) { // 原始標籤 + 這個新標籤
                const newTab = new bootstrap.Tab(document.getElementById(`${type}-tab`));
                newTab.show();
            }

            console.log(`${type} 標籤頁創建完成！`);

        } catch (error) {
            console.error(`創建 ${type} 標籤頁時發生錯誤:`, error);
            showAlert(`創建 ${name} 標籤頁失敗`, 'danger');
        }
    }

    // 移除組織標籤頁
    function removeOrganizationTab(type) {
        // 阻止事件冒泡，確保點擊刪除按鈕不會同時觸發標籤切換
        event.stopPropagation();
        
        if (confirm('確定要移除這個整理版本嗎？這將永久刪除該整理結果。')) {
            // 獲取對應的 analysis_id
            const analysisId = organizationAnalysisIds[type];
            if (!analysisId) {
                showAlert('無法找到對應的整理記錄', 'warning');
                return;
            }

            // 從資料庫中刪除
            fetch(`/notes/${currentNoteId}/organizations/${analysisId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // 成功刪除後才從頁面移除
                        const tabButton = document.getElementById(`${type}-tab`);
                        if (tabButton) {
                            tabButton.parentElement.remove();
                        }

                        const tabContent = document.getElementById(`${type}-content`);
                        if (tabContent) {
                            tabContent.remove();
                        }

                        // 從對應關係中移除
                        delete organizationAnalysisIds[type];

                        // 切換到原始標籤
                        const originalTab = new bootstrap.Tab(document.getElementById('original-tab'));
                        originalTab.show();

                        showAlert('整理版本已刪除', 'success');
                    } else {
                        showAlert('刪除失敗：' + data.error, 'danger');
                    }
                })
                .catch(error => {
                    showAlert('發生錯誤：' + error.message, 'danger');
                });
        }
    }

    // 載入預先生成的 AI 整理結果
    function loadPreGeneratedResults() {
        console.log('開始載入預先生成的 AI 整理結果...');

        fetch(`/notes/${currentNoteId}/pre-generated-results`)
            .then(response => {
                console.log('API 回應狀態:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('API 回應完整數據:', data);

                if (data.success) {
                    const resultsCount = Object.keys(data.results || {}).length;
                    console.log(`找到 ${resultsCount} 個預先生成的結果`);

                    if (resultsCount > 0) {
                        console.log('結果詳情:', data.results);

                        // 為每個預先生成的結果創建標籤頁
                        const typeNames = {
                            'mindmap': { name: '心智圖結構化', icon: 'sitemap' },
                            'hierarchical': { name: '層次化重點整理', icon: 'list' },
                            'feynman': { name: '費曼技巧解析', icon: 'lightbulb' },
                            'qa_learning': { name: '問答式學習', icon: 'question' },
                            'comparison': { name: '對比分析整理', icon: 'balance-scale' },
                            'memory_palace': { name: '記憶宮殿法', icon: 'home' },
                            'format_enhance': { name: '格式化與補強', icon: 'magic' }
                        };

                        let successCount = 0;
                        let errorCount = 0;

                        for (const [type, resultWrapper] of Object.entries(data.results)) {
                            const typeInfo = typeNames[type];
                            if (typeInfo) {
                                try {
                                    console.log(`創建 ${type} 標籤頁...`);
                                    console.log(`- Analysis ID: ${resultWrapper.analysis_id}`);
                                    console.log(`- Result 格式:`, typeof resultWrapper.result);
                                    console.log(`- Result 內容預覽:`, Object.keys(resultWrapper.result || {}));

                                    // 驗證結果數據
                                    if (!resultWrapper.result) {
                                        console.warn(`${type} 的結果數據為空`);
                                        errorCount++;
                                        continue;
                                    }

                                    // 儲存 analysis_id 以供刪除時使用
                                    organizationAnalysisIds[type] = resultWrapper.analysis_id;

                                    // 創建標籤頁
                                    addOrganizationTab(type, typeInfo.name, typeInfo.icon, resultWrapper.result);
                                    successCount++;

                                } catch (error) {
                                    console.error(`創建 ${type} 標籤頁失敗:`, error);
                                    errorCount++;
                                }
                            } else {
                                console.warn(`未知的整理類型: ${type}`);
                                errorCount++;
                            }
                        }

                        console.log(`標籤頁創建完成！成功: ${successCount}, 失敗: ${errorCount}`);

                        // 如果有成功創建的標籤頁，隱藏舊的顯示區域
                        if (successCount > 0) {
                            const container = document.getElementById('pre-generated-results');
                            if (container) {
                                container.style.display = 'none';
                            }
                        }

                        // 如果有錯誤，顯示提示
                        if (errorCount > 0) {
                            showAlert(`已載入 ${successCount} 個AI整理結果，${errorCount} 個載入失敗`, 'warning');
                        }

                    } else {
                        console.log('沒有找到預先生成的結果');
                    }
                } else {
                    console.error('API 回應失敗:', data.error);
                    showAlert('載入AI整理結果失敗：' + (data.error || '未知錯誤'), 'danger');
                }
            })
            .catch(error => {
                console.error('載入預先生成結果時發生錯誤:', error);
                showAlert('載入AI整理結果時發生網路錯誤', 'danger');
            });
    }

    // 顯示預先生成的結果
    function displayPreGeneratedResults(results) {
        const container = document.getElementById('pre-generated-results');
        let html = '<div class="alert alert-success"><i class="fas fa-check-circle me-1"></i><strong>建立時預先生成的 AI 整理結果</strong></div>';

        const typeNames = {
            'mindmap': '心智圖結構化',
            'hierarchical': '層次化重點整理',
            'feynman': '費曼技巧解析',
            'qa_learning': '問答式學習',
            'comparison': '對比分析整理',
            'memory_palace': '記憶宮殿法'
        };

        for (const [type, result] of Object.entries(results)) {
            html += `
            <div class="card shadow-sm mb-3">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h6 class="mb-0"><i class="fas fa-magic me-2"></i>${typeNames[type] || type}</h6>
                    <button class="btn btn-outline-primary btn-sm" onclick="regenerateOrganization('${type}', '${typeNames[type]}')">
                        <i class="fas fa-sync-alt me-1"></i>重新生成
                    </button>
                </div>
                <div class="card-body">
                    ${formatOrganizationResult(result, type)}
                </div>
            </div>
        `;
        }

        container.innerHTML = html;
    }

    // 格式化整理結果顯示
    function formatOrganizationResult(result, type) {
        console.log(`格式化 ${type} 類型的結果:`, result);

        let html = '';

        // 檢查 result 是否存在且為對象
        if (!result || typeof result !== 'object') {
            console.warn(`結果格式不正確:`, result);
            return '<p class="text-muted">內容格式有誤，請重新生成...</p>';
        }

        // 只有在沒有特殊格式的情況下，才顯示通用的organized_content
        // 費曼法、問答式學習、記憶宮殿法、層次化筆記、對比分析整理和格式化增強都有特殊排版，所以不顯示通用內容
        const hasSpecialFormat = ['feynman', 'qa_learning', 'memory_palace', 'format_enhance', 'hierarchical', 'comparison'].includes(type);

        if (result.organized_content && !hasSpecialFormat) {
            // 使用 Markdown 渲染，就像題庫參考答案一樣
            html += `<div class="ai-organized-content markdown-content mb-3">${renderMarkdown(result.organized_content)}</div>`;
        }

        // 根據不同的整理類型顯示特定內容
    if (type === 'mindmap') {
        if (result.mindmap_data) {
            const chartId = `echart-mindmap-${Date.now()}`;
            html += `<h6><i class="fas fa-project-diagram me-2 text-primary"></i>心智圖視覺化 <small class="text-muted">(可拖曳、縮放及滑動)</small></h6>`;
            // 容器結構保持不變
            html += `<div class="mindmap-scroll-container" style="width: 100%; height: 800px; overflow: hidden; border: 1px solid #eee; position: relative; user-select: none;">
                <div id="${chartId}" style="width: 150%; height: 100%; min-width: 1200px;" class="mindmap-container"></div>
            </div>`;

            setTimeout(() => {
                try {
                    const scrollContainer = document.querySelector(`#${chartId}`).parentElement;
                    const chartDom = document.getElementById(chartId);
                    if (!chartDom || !scrollContainer) return;
                    
                    const myChart = echarts.init(chartDom);
                    
                    const option = {
                        series: [{
                            type: 'tree',
                            data: [result.mindmap_data],
                            top: '5%', left: '7%', bottom: '5%', right: '18%',
                            symbolSize: 16,
                            layout: 'orthogonal', orient: 'LR', edgeShape: 'polyline',
                            // ... 其他美化選項 ...
                            
                            // *** 【關鍵修改 1】: 徹底禁用 ECharts 的漫遊功能 ***
                            roam: false, 
                            
                            initialTreeDepth: -1,
                            expandAndCollapse: true
                        }]
                    };
                    
                    myChart.setOption(option);
                    window.addEventListener('resize', () => myChart.resize());

                    // --- 全新的手動互動控制邏輯 ---

                    // 1. 保留優化的【滾輪縮放】邏輯
                    let isWheeling = false;
                    chartDom.addEventListener('wheel', function(event) {
                        event.preventDefault();
                        if (isWheeling) return;
                        isWheeling = true;
                        setTimeout(() => { isWheeling = false; }, 80); // 稍微縮短緩衝時間

                        const currentOption = myChart.getOption();
                        let currentZoom = currentOption.series[0].zoom || 1;
                        const zoomStep = 0.1;
                        currentZoom += (event.deltaY < 0 ? zoomStep : -zoomStep);
                        currentZoom = Math.max(0.3, Math.min(5.0, currentZoom));
                        
                        myChart.setOption({ series: [{ zoom: currentZoom }] });
                    });

                    // 2. 【全新的手動拖曳平移】邏輯
                    let isDragging = false;
                    let startX, startY;
                    let scrollLeftStart, scrollTopStart;

                    scrollContainer.addEventListener('mousedown', (e) => {
                        isDragging = true;
                        // 改變滑鼠樣式為「抓取中」
                        scrollContainer.style.cursor = 'grabbing';
                        // 記錄初始位置
                        startX = e.pageX - scrollContainer.offsetLeft;
                        startY = e.pageY - scrollContainer.offsetTop;
                        scrollLeftStart = scrollContainer.scrollLeft;
                        scrollTopStart = scrollContainer.scrollTop;
                    });

                    scrollContainer.addEventListener('mouseleave', () => {
                        isDragging = false;
                        scrollContainer.style.cursor = 'grab';
                    });

                    scrollContainer.addEventListener('mouseup', () => {
                        isDragging = false;
                        scrollContainer.style.cursor = 'grab';
                    });

                    scrollContainer.addEventListener('mousemove', (e) => {
                        if (!isDragging) return;
                        e.preventDefault();

                        // 計算滑鼠移動的距離
                        const x = e.pageX - scrollContainer.offsetLeft;
                        const y = e.pageY - scrollContainer.offsetTop;
                        const walkX = (x - startX);
                        const walkY = (y - startY);

                        // 根據移動距離更新滾動條位置
                        scrollContainer.scrollLeft = scrollLeftStart - walkX;
                        scrollContainer.scrollTop = scrollTopStart - walkY;
                    });


                } catch (e) {
                    console.error("ECharts 初始化或自訂互動失敗:", e);
                }
            }, 150);
        }
            // 向下相容：顯示舊版的 mindmap_structure
            else if (result.mindmap_structure) {
                html += '<h6>心智圖結構：</h6>';
                html += '<div class="small"><pre class="bg-light p-2">' + JSON.stringify(result.mindmap_structure, null, 2) + '</pre></div>';
            }
        } else if (type === 'hierarchical') {
            // 層次化筆記的特殊顯示
            html += '<div class="hierarchical-container p-3 border rounded">';

            // 添加除錯信息
            console.log('層次化整理結果數據:', JSON.stringify(result, null, 2));

            // 標題
            if (result.title) {
                html += `<h4 class="text-center mb-4">${result.title}</h4>`;
            }

            // 主要重點部分
            if (result.main_points) {
                html += '<h5 class="border-bottom pb-2 mb-3"><i class="fas fa-list me-2 text-primary"></i>主要重點</h5>';

                try {
                    if (Array.isArray(result.main_points)) {
                        html += '<div class="list-group mb-4">';
                        result.main_points.forEach(point => {
                            html += `<div class="list-group-item list-group-item-action">${renderMarkdown(point)}</div>`;
                        });
                        html += '</div>';
                    } else if (typeof result.main_points === 'string') {
                        html += `<div class="alert alert-light border-start border-4 border-primary mb-4">${renderMarkdown(result.main_points)}</div>`;
                    } else {
                        html += '<div class="alert alert-warning">主要重點數據格式不正確</div>';
                        console.warn('主要重點數據格式不正確:', result.main_points);
                    }
                } catch (e) {
                    html += `<div class="alert alert-danger">處理主要重點時出錯: ${e.message}</div>`;
                    console.error('處理主要重點時出錯:', e);
                }
            }

            // 次要重點部分（如果有）
            if (result.sub_points) {
                html += '<h5 class="border-bottom pb-2 mb-3"><i class="fas fa-stream me-2 text-success"></i>次要重點</h5>';

                try {
                    if (Array.isArray(result.sub_points)) {
                        const accordionId = `hierarchical-subpoints-${Date.now()}`;
                        html += `<div class="accordion mb-4" id="${accordionId}">`;

                        result.sub_points.forEach((section, index) => {
                            const sectionId = `subpoint-section-${Date.now()}-${index}`;
                            const contentId = `subpoint-content-${Date.now()}-${index}`;

                            let title, content;

                            // 檢查 section 的類型和結構
                            if (typeof section === 'object' && section !== null) {
                                title = section.title || `章節 ${index + 1}`;
                                content = section.content || section.points || '';
                            } else if (typeof section === 'string') {
                                // 如果直接是字符串，使用索引作為標題
                                title = `章節 ${index + 1}`;
                                content = section;
                            } else {
                                title = `章節 ${index + 1}`;
                                content = '內容格式錯誤';
                                console.warn(`章節 ${index + 1} 的數據格式不正確:`, section);
                            }

                            html += `
                        <div class="accordion-item">
                            <h2 class="accordion-header" id="${sectionId}-header">
                                <button class="accordion-button ${index === 0 ? '' : 'collapsed'}" type="button" 
                                        data-bs-toggle="collapse" data-bs-target="#${contentId}" 
                                        aria-expanded="${index === 0 ? 'true' : 'false'}" aria-controls="${contentId}">
                                    ${title}
                                </button>
                            </h2>
                            <div id="${contentId}" class="accordion-collapse collapse ${index === 0 ? 'show' : ''}" 
                                 aria-labelledby="${sectionId}-header" data-bs-parent="#${accordionId}">
                                <div class="accordion-body">
                                    ${renderMarkdown(content)}
                                </div>
                            </div>
                        </div>`;
                        });

                        html += '</div>'; // 關閉 accordion
                    } else {
                        html += '<div class="alert alert-warning">次要重點數據格式不正確</div>';
                        console.warn('次要重點數據格式不正確:', result.sub_points);
                    }
                } catch (e) {
                    html += `<div class="alert alert-danger">處理次要重點時出錯: ${e.message}</div>`;
                    console.error('處理次要重點時出錯:', e);
                }
            }

            // 向下相容：處理舊的supporting_details格式
            if (!result.sub_points && result.supporting_details) {
                html += '<h5 class="border-bottom pb-2 mb-3"><i class="fas fa-stream me-2 text-success"></i>支撐細節</h5>';
                html += '<div class="accordion mb-3" id="hierarchical-details-accordion">';

                try {
                    Object.entries(result.supporting_details).forEach(([mainPoint, details], index) => {
                        const sectionId = `detail-section-${index}`;
                        const contentId = `detail-content-${index}`;

                        html += `
                <div class="accordion-item">
                    <h2 class="accordion-header" id="${sectionId}-header">
                        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#${contentId}" aria-expanded="false" aria-controls="${contentId}">
                            ${mainPoint}
                        </button>
                    </h2>
                    <div id="${contentId}" class="accordion-collapse collapse" aria-labelledby="${sectionId}-header">
                        <div class="accordion-body">
                            <ul>
                                ${Array.isArray(details) ? details.map(detail => `<li>${detail}</li>`).join('') : `<li>${details}</li>`}
                            </ul>
                        </div>
                    </div>
                </div>`;
                    });
                    html += '</div>'; // 關閉 accordion
                } catch (e) {
                    html += `<div class="alert alert-danger">處理支撐細節時出錯: ${e.message}</div>`;
                    console.error('處理支撐細節時出錯:', e);
                }
            }

            // 關鍵概念部分（如果有）
            if (result.key_concepts) {
                html += '<h5 class="border-bottom pb-2 mb-3"><i class="fas fa-key me-2 text-warning"></i>關鍵概念</h5>';

                try {
                    if (Array.isArray(result.key_concepts)) {
                        html += '<div class="row row-cols-1 row-cols-md-2 g-4 mb-4">';
                        result.key_concepts.forEach(concept => {
                            let term, definition;

                            if (typeof concept === 'object' && concept !== null) {
                                term = concept.term || '概念';
                                definition = concept.definition || '未提供定義';
                            } else if (typeof concept === 'string') {
                                term = concept;
                                definition = '未提供定義';
                            } else {
                                term = '概念';
                                definition = '數據格式錯誤';
                            }

                            html += `<div class="col">
                            <div class="card h-100 border-warning">
                                <div class="card-header bg-warning bg-opacity-10">
                                    <h5 class="card-title mb-0">${term}</h5>
                                </div>
                                <div class="card-body">
                                    <p class="card-text">${renderMarkdown(definition)}</p>
                                </div>
                            </div>
                        </div>`;
                        });
                        html += '</div>';
                    } else {
                        html += '<div class="alert alert-warning">關鍵概念數據格式不正確</div>';
                        console.warn('關鍵概念數據格式不正確:', result.key_concepts);
                    }
                } catch (e) {
                    html += `<div class="alert alert-danger">處理關鍵概念時出錯: ${e.message}</div>`;
                    console.error('處理關鍵概念時出錯:', e);
                }
            }

            // 學習建議（如果有）
            if (result.learning_tips) {
                html += '<h5 class="border-bottom pb-2 mb-3"><i class="fas fa-lightbulb me-2 text-info"></i>學習建議</h5>';

                try {
                    html += `<div class="alert alert-light border-start border-4 border-info mb-4">
                    ${renderMarkdown(result.learning_tips)}
                </div>`;
                } catch (e) {
                    html += `<div class="alert alert-danger">處理學習建議時出錯: ${e.message}</div>`;
                    console.error('處理學習建議時出錯:', e);
                }
            }

            // 調試信息（默認隱藏）
            html += `
        <div class="d-none">
            <hr>
            <h6>調試信息:</h6>
            <pre class="small bg-light p-2">${JSON.stringify(result, null, 2)}</pre>
        </div>
        `;

            html += '</div>'; // 關閉容器
        } else if (type === 'qa_learning') {
            // 問答式學習的增強顯示
            html += '<div class="qa-learning-container p-3 border rounded">';

            // 基礎問題部分
            if (result.basic_questions && result.basic_questions.length > 0) {
                html += '<h6><i class="fas fa-question-circle me-2 text-primary"></i>基礎問題</h6>';
                html += '<div class="accordion mb-3" id="qa-basic-accordion">';

                if (Array.isArray(result.basic_questions)) {
                    result.basic_questions.forEach((question, index) => {
                        const qId = `basic-q-${index}`;
                        const answerId = `basic-a-${index}`;
                        const answer = result.answers && result.answers[question] ?
                            result.answers[question] : '查看答案功能準備中...';

                        html += `
                    <div class="accordion-item">
                        <h2 class="accordion-header" id="${qId}-header">
                            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#${answerId}" aria-expanded="false" aria-controls="${answerId}">
                                ${question}
                            </button>
                        </h2>
                        <div id="${answerId}" class="accordion-collapse collapse" aria-labelledby="${qId}-header">
                            <div class="accordion-body">
                                ${renderMarkdown(answer)}
                            </div>
                        </div>
                    </div>`;
                    });
                } else {
                    html += `<div class="alert alert-info">${renderMarkdown(result.basic_questions)}</div>`;
                }
                html += '</div>'; // 關閉 accordion
            }

            // 中級問題部分
            if (result.intermediate_questions && result.intermediate_questions.length > 0) {
                html += '<h6><i class="fas fa-graduation-cap me-2 text-success"></i>中級問題</h6>';
                html += '<div class="accordion mb-3" id="qa-intermediate-accordion">';

                if (Array.isArray(result.intermediate_questions)) {
                    result.intermediate_questions.forEach((question, index) => {
                        const qId = `interm-q-${index}`;
                        const answerId = `interm-a-${index}`;
                        const answer = result.answers && result.answers[question] ?
                            result.answers[question] : '查看答案功能準備中...';

                        html += `
                    <div class="accordion-item">
                        <h2 class="accordion-header" id="${qId}-header">
                            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#${answerId}" aria-expanded="false" aria-controls="${answerId}">
                                ${question}
                            </button>
                        </h2>
                        <div id="${answerId}" class="accordion-collapse collapse" aria-labelledby="${qId}-header">
                            <div class="accordion-body">
                                ${renderMarkdown(answer)}
                            </div>
                        </div>
                    </div>`;
                    });
                } else {
                    html += `<div class="alert alert-info">${renderMarkdown(result.intermediate_questions)}</div>`;
                }
                html += '</div>'; // 關閉 accordion
            }

            // 高級問題部分
            if (result.advanced_questions && result.advanced_questions.length > 0) {
                html += '<h6><i class="fas fa-brain me-2 text-danger"></i>高級問題</h6>';
                html += '<div class="accordion mb-3" id="qa-advanced-accordion">';

                if (Array.isArray(result.advanced_questions)) {
                    result.advanced_questions.forEach((question, index) => {
                        const qId = `adv-q-${index}`;
                        const answerId = `adv-a-${index}`;
                        const answer = result.answers && result.answers[question] ?
                            result.answers[question] : '查看答案功能準備中...';

                        html += `
                    <div class="accordion-item">
                        <h2 class="accordion-header" id="${qId}-header">
                            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#${answerId}" aria-expanded="false" aria-controls="${answerId}">
                                ${question}
                            </button>
                        </h2>
                        <div id="${answerId}" class="accordion-collapse collapse" aria-labelledby="${qId}-header">
                            <div class="accordion-body">
                                ${renderMarkdown(answer)}
                            </div>
                        </div>
                    </div>`;
                    });
                } else {
                    html += `<div class="alert alert-info">${renderMarkdown(result.advanced_questions)}</div>`;
                }
                html += '</div>'; // 關閉 accordion
            }

            // 批判性思考問題
            if (result.critical_thinking && result.critical_thinking.length > 0) {
                html += '<h6><i class="fas fa-lightbulb me-2 text-warning"></i>批判性思考</h6>';
                html += '<div class="accordion mb-3" id="qa-critical-accordion">';

                if (Array.isArray(result.critical_thinking)) {
                    result.critical_thinking.forEach((question, index) => {
                        const qId = `crit-q-${index}`;
                        const answerId = `crit-a-${index}`;
                        const answer = result.answers && result.answers[question] ?
                            result.answers[question] : '查看答案功能準備中...';

                        html += `
                    <div class="accordion-item">
                        <h2 class="accordion-header" id="${qId}-header">
                            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#${answerId}" aria-expanded="false" aria-controls="${answerId}">
                                ${question}
                            </button>
                        </h2>
                        <div id="${answerId}" class="accordion-collapse collapse" aria-labelledby="${qId}-header">
                            <div class="accordion-body">
                                ${renderMarkdown(answer)}
                            </div>
                        </div>
                    </div>`;
                    });
                } else {
                    html += `<div class="alert alert-info">${renderMarkdown(result.critical_thinking)}</div>`;
                }
                html += '</div>'; // 關閉 accordion
            }

            // 學習建議
            if (result.learning_progression) {
                html += `<div class="alert alert-light border-start border-4 border-info mb-3">
                <h6><i class="fas fa-route me-2 text-info"></i>學習路徑</h6>
                ${renderMarkdown(result.learning_progression)}
            </div>`;
            }

            html += '</div>'; // 關閉容器
        } else if (type === 'feynman') {
            // 費曼技巧解析的特殊顯示
            html += '<div class="feynman-technique-container p-3 border rounded">';

            if (result.simple_explanation) {
                html += '<h6><i class="fas fa-lightbulb me-2 text-warning"></i>簡單解釋</h6>';
                html += `<div class="alert alert-light border-start border-4 border-warning p-3 mb-3">${renderMarkdown(result.simple_explanation)}</div>`;
            }

            if (result.analogies && Array.isArray(result.analogies)) {
                html += '<h6><i class="fas fa-exchange-alt me-2 text-info"></i>類比</h6>';
                html += '<ul class="list-group mb-3">';
                result.analogies.forEach(analogy => {
                    html += `<li class="list-group-item">${renderMarkdown(analogy)}</li>`;
                });
                html += '</ul>';
            }

            if (result.step_by_step && Array.isArray(result.step_by_step)) {
                html += '<h6><i class="fas fa-tasks me-2 text-success"></i>步驟說明</h6>';
                html += '<ol class="list-group list-group-numbered mb-3">';
                result.step_by_step.forEach(step => {
                    html += `<li class="list-group-item">${renderMarkdown(step)}</li>`;
                });
                html += '</ol>';
            }

            if (result.examples && Array.isArray(result.examples)) {
                html += '<h6><i class="fas fa-flask me-2 text-primary"></i>實例</h6>';
                html += '<div class="card mb-3">';
                result.examples.forEach((example, index) => {
                    html += `<div class="card-body border-bottom ${index > 0 ? 'pt-3' : ''}">${renderMarkdown(example)}</div>`;
                });
                html += '</div>';
            }

            if (result.potential_gaps && Array.isArray(result.potential_gaps)) {
                html += '<h6><i class="fas fa-exclamation-circle me-2 text-danger"></i>可能的盲點</h6>';
                html += '<ul class="list-group mb-3">';
                result.potential_gaps.forEach(gap => {
                    html += `<li class="list-group-item list-group-item-warning">${renderMarkdown(gap)}</li>`;
                });
                html += '</ul>';
            }

            if (result.teaching_points && Array.isArray(result.teaching_points)) {
                html += '<h6><i class="fas fa-chalkboard-teacher me-2 text-success"></i>教學重點</h6>';
                html += '<ul class="list-group mb-3">';
                result.teaching_points.forEach(point => {
                    html += `<li class="list-group-item list-group-item-success">${renderMarkdown(point)}</li>`;
                });
                html += '</ul>';
            }

            html += '</div>';
        } else if (type === 'memory_palace') {
            // 記憶宮殿法的特殊顯示
            html += `<div class="memory-palace-container p-3 border rounded">`;

            if (result.memory_story) {
                html += '<h6><i class="fas fa-book me-2 text-primary"></i>記憶故事</h6>';
                html += `<div class="alert alert-light border-start border-4 border-primary p-3 mb-3">${renderMarkdown(result.memory_story)}</div>`;
            }

            if (result.spatial_layout) {
                html += '<h6><i class="fas fa-map-signs me-2 text-info"></i>空間佈局</h6>';
                html += `<div class="card mb-3">
                      <div class="card-body">
                        ${renderMarkdown(result.spatial_layout)}
                      </div>
                     </div>`;
            }

            if (result.key_anchors) {
                html += '<h6><i class="fas fa-anchor me-2 text-success"></i>關鍵記憶錨點</h6>';

                // 新格式：key_anchors 是對象數組
                if (Array.isArray(result.key_anchors) && typeof result.key_anchors[0] === 'object') {
                    html += '<div class="list-group mb-3">';
                    result.key_anchors.forEach(anchor => {
                        html += `<div class="list-group-item list-group-item-action flex-column align-items-start">
                                <div class="d-flex w-100 justify-content-between">
                                    <h6 class="mb-1">${anchor.anchor || '未命名錨點'}</h6>
                                </div>
                                <p class="mb-1">${anchor.content || anchor.anchor || '無內容'}</p>
                                ${anchor.visual ? `<small class="text-muted"><em><i class="fas fa-eye me-1"></i>${anchor.visual}</em></small>` : ''}
                             </div>`;
                    });
                    html += '</div>';
                }
                // 舊格式：key_anchors 是字符串數組
                else if (Array.isArray(result.key_anchors)) {
                    html += '<ul class="list-group list-group-flush mb-3">';
                    result.key_anchors.forEach(anchor => {
                        html += `<li class="list-group-item">${anchor}</li>`;
                    });
                    html += '</ul>';
                } else {
                    // 如果不是數組，可能是字符串
                    html += `<div class="mb-3">${renderMarkdown(result.key_anchors)}</div>`;
                }
            }

            if (result.visual_imagery) {
                html += '<h6><i class="fas fa-image me-2 text-warning"></i>視覺想像</h6>';
                html += `<div class="card mb-3 bg-light">
                      <div class="card-body">
                        <em>${renderMarkdown(result.visual_imagery)}</em>
                      </div>
                     </div>`;
            }

            if (result.memory_cues) {
                html += '<h6><i class="fas fa-lightbulb me-2 text-warning"></i>記憶提示</h6>';
                if (Array.isArray(result.memory_cues)) {
                    html += '<div class="d-flex flex-wrap mb-3">';
                    result.memory_cues.forEach(cue => {
                        html += `<span class="badge bg-warning text-dark m-1 p-2">${cue}</span>`;
                    });
                    html += '</div>';
                } else {
                    // 如果不是數組，可能是字符串
                    html += `<div class="mb-3">${renderMarkdown(result.memory_cues)}</div>`;
                }
            }

            if (result.practice_routine) {
                html += '<h6><i class="fas fa-calendar-check me-2 text-info"></i>練習建議</h6>';
                html += `<div class="alert alert-light border-start border-4 border-info mb-3">
                        ${renderMarkdown(result.practice_routine)}
                     </div>`;
            }

            // 關閉記憶宮殿容器
            html += `</div>`;
        } else if (type === 'comparison') {
            // 對比分析整理的特殊顯示
            html += '<div class="comparison-container p-3 border rounded">';

            // 關鍵概念
            if (result.key_concepts && Array.isArray(result.key_concepts)) {
                html += '<h6><i class="fas fa-key me-2 text-primary"></i>關鍵概念</h6>';
                html += '<div class="mb-4">';
                html += '<div class="d-flex flex-wrap">';
                result.key_concepts.forEach(concept => {
                    html += `<span class="badge bg-primary m-1 p-2">${concept}</span>`;
                });
                html += '</div>';
                html += '</div>';
            }

            // 相似點
            if (result.similarities && Array.isArray(result.similarities)) {
                html += '<h6><i class="fas fa-equals me-2 text-success"></i>相似點</h6>';
                html += '<ul class="list-group mb-4">';
                result.similarities.forEach(similarity => {
                    html += `<li class="list-group-item list-group-item-success">${renderMarkdown(similarity)}</li>`;
                });
                html += '</ul>';
            }

            // 差異點
            if (result.differences && Array.isArray(result.differences)) {
                html += '<h6><i class="fas fa-not-equal me-2 text-danger"></i>差異點</h6>';
                html += '<ul class="list-group mb-4">';
                result.differences.forEach(difference => {
                    html += `<li class="list-group-item list-group-item-danger">${renderMarkdown(difference)}</li>`;
                });
                html += '</ul>';
            }

            // 關聯性
            if (result.relationships && Array.isArray(result.relationships)) {
                html += '<h6><i class="fas fa-project-diagram me-2 text-info"></i>關聯性</h6>';
                html += '<ul class="list-group mb-4">';
                result.relationships.forEach(relationship => {
                    html += `<li class="list-group-item list-group-item-info">${renderMarkdown(relationship)}</li>`;
                });
                html += '</ul>';
            }

            // 對比表格
            if (result.comparison_table && Array.isArray(result.comparison_table)) {
                html += '<h6><i class="fas fa-table me-2 text-warning"></i>對比表格</h6>';
                html += '<div class="table-responsive mb-4">';
                html += '<table class="table table-bordered table-striped">';
                
                // 表頭
                if (result.comparison_table.length > 0) {
                    html += '<thead class="table-light"><tr>';
                    const headers = Object.keys(result.comparison_table[0]);
                    headers.forEach(header => {
                        html += `<th>${header}</th>`;
                    });
                    html += '</tr></thead>';
                    
                    // 表內容
                    html += '<tbody>';
                    result.comparison_table.forEach(row => {
                        html += '<tr>';
                        headers.forEach(header => {
                            html += `<td>${row[header]}</td>`;
                        });
                        html += '</tr>';
                    });
                    html += '</tbody>';
                }
                
                html += '</table>';
                html += '</div>';
            }

            // 優缺點分析
            if (result.pros_and_cons && Array.isArray(result.pros_and_cons)) {
                html += '<h6><i class="fas fa-balance-scale me-2 text-primary"></i>優缺點分析</h6>';
                html += '<div class="row row-cols-1 row-cols-md-2 g-4 mb-4">';
                
                result.pros_and_cons.forEach(item => {
                    html += `
                    <div class="col">
                        <div class="card h-100">
                            <div class="card-header bg-light">
                                <h5 class="card-title mb-0">${item.concept}</h5>
                            </div>
                            <div class="card-body">
                                <h6 class="text-success"><i class="fas fa-thumbs-up me-2"></i>優點</h6>
                                <ul class="mb-3">
                                ${Array.isArray(item.pros) ? item.pros.map(pro => `<li>${pro}</li>`).join('') : ''}
                                </ul>
                                
                                <h6 class="text-danger"><i class="fas fa-thumbs-down me-2"></i>缺點</h6>
                                <ul>
                                ${Array.isArray(item.cons) ? item.cons.map(con => `<li>${con}</li>`).join('') : ''}
                                </ul>
                            </div>
                        </div>
                    </div>
                    `;
                });
                
                html += '</div>';
            }

            html += '</div>'; // 關閉容器
        } else if (type === 'format_enhance') {
            // 格式化與補強直接使用 Markdown 渲染展示內容
            if (result.formatted_content) {
                html += `<div class="ai-organized-content markdown-content mb-3">${renderMarkdown(result.formatted_content)}</div>`;

                // 添加一個按鈕，讓用戶可以將格式化結果應用到原始筆記
                html += `<div class="alert alert-warning">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        <strong>提醒：</strong> 應用此格式化結果將會替換原始筆記內容！
                    </div>
                    <button class="btn btn-sm btn-warning" onclick="applyFormattedContent('${type}')">
                        <i class="fas fa-check me-1"></i>應用到筆記
                    </button>
                </div>
            </div>`;
            }
        }

        // 如果沒有任何HTML內容，嘗試從其他欄位生成內容
        if (!html) {
            // 檢查是否有任何可用的內容欄位
            const possibleContentFields = [
                'organized_content', 'formatted_content', 'content',
                'summary', 'description', 'text', 'data'
            ];

            for (const field of possibleContentFields) {
                if (result[field]) {
                    console.log(`使用 ${field} 欄位作為備用內容`);
                    if (typeof result[field] === 'string') {
                        html = `<div class="ai-organized-content markdown-content mb-3">${renderMarkdown(result[field])}</div>`;
                        break;
                    } else if (typeof result[field] === 'object') {
                        html = `<div class="mb-3"><pre class="bg-light p-2">${JSON.stringify(result[field], null, 2)}</pre></div>`;
                        break;
                    }
                }
            }

            // 如果仍然沒有內容，顯示調試信息
            if (!html) {
                console.warn(`${type} 類型的結果沒有可用內容，可用欄位:`, Object.keys(result));

                // 使用診斷工具（如果存在）
                if (window.showOrganizationDebugInfo) {
                    html = window.showOrganizationDebugInfo(type, result);
                } else {
                    html = `
                    <div class="alert alert-warning">
                        <h6><i class="fas fa-exclamation-triangle me-2"></i>內容格式問題</h6>
                        <p class="mb-2">AI 整理結果格式異常，可能的原因：</p>
                        <ul class="mb-2">
                            <li>AI 回應格式不完整</li>
                            <li>JSON 解析錯誤</li>
                            <li>網路連線問題</li>
                        </ul>
                        <button class="btn btn-sm btn-outline-primary" onclick="regenerateOrganization('${type}', '${type}')">
                            <i class="fas fa-sync me-1"></i>重新生成
                        </button>
                        <details class="mt-2">
                            <summary class="small text-muted">調試信息</summary>
                            <pre class="small mt-2">${JSON.stringify(result, null, 2)}</pre>
                        </details>
                    </div>
                `;
                }
            }

            // 添加除錯按鈕（只有開發模式才顯示）
            if (window.diagnoseOrganizationIssue) {
                const diagnosis = window.diagnoseOrganizationIssue(type, result);
                if (diagnosis.status !== 'ok') {
                    html += `
                    <div class="text-end mb-3">
                        <button class="btn btn-sm btn-outline-dark" 
                                onclick="console.log('診斷 ${type}:', diagnoseOrganizationIssue('${type}', ${JSON.stringify(result).replace(/"/g, '\\"')}))"
                                title="在控制台查看詳細診斷信息">
                            <i class="fas fa-bug me-1"></i>診斷
                        </button>
                    </div>
                `;
                }
            }
        }

        return html;
    }

    // 重新生成特定類型的整理
    function regenerateOrganization(type, name) {
        if (confirm(`確定要重新生成「${name}」嗎？這將覆蓋現有的結果。`)) {
            organizeNote(type, name);
        }
    }

    // 重新生成 AI 建議
    function refreshAISuggestions() {
        const btn = document.getElementById('refresh-suggestions-btn');
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> 生成中...';
        btn.disabled = true;

        fetch(`/notes/${currentNoteId}/suggestions`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateSuggestionsDisplay(data.suggestions);
                    showAlert('AI 建議已更新！', 'success');
                } else {
                    showAlert('生成建議失敗：' + data.error, 'danger');
                }
            })
            .catch(error => {
                showAlert('發生錯誤：' + error.message, 'danger');
            })
            .finally(() => {
                btn.innerHTML = '<i class="fas fa-sync-alt me-1"></i> 重新生成建議';
                btn.disabled = false;
            });
    }

    // 更新建議顯示
    function updateSuggestionsDisplay(suggestions) {
        const content = document.getElementById('ai-suggestions-content');
        let html = '';

        if (suggestions.related_notes && suggestions.related_notes.length > 0) {
            html += `<div class="mb-2"><strong>相關筆記 (${suggestions.related_notes.length}):</strong>`;
            suggestions.related_notes.forEach(note => {
                html += `<div class="small text-muted">• ${note}</div>`;
            });
            html += '</div>';
        }

        if (suggestions.knowledge_points && suggestions.knowledge_points.length > 0) {
            html += `<div class="mb-2"><strong>相關知識點 (${suggestions.knowledge_points.length}):</strong>`;
            suggestions.knowledge_points.forEach(kp => {
                html += `<div class="small text-muted">• ${kp}</div>`;
            });
            html += '</div>';
        }

        if (suggestions.study_suggestions && suggestions.study_suggestions.length > 0) {
            html += `<div class="mb-2"><strong>學習建議 (${suggestions.study_suggestions.length}):</strong>`;
            suggestions.study_suggestions.forEach(suggestion => {
                html += `<div class="small text-muted">• ${suggestion}</div>`;
            });
            html += '</div>';
        }

        if (html === '') {
            html = '<p class="text-muted">暫無相關建議</p>';
        }

        content.innerHTML = html;
    }

    // AI 整理筆記
    function organizeNote(type, name) {
        loadingModal.show();

        fetch(`/notes/${currentNoteId}/organize`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                organization_type: type
            })
        })
            .then(response => response.json())
            .then(data => {
                loadingModal.hide();
                if (data.success) {
                    displayAIOrganization(data, name);
                    // 重新載入預先生成的結果
                    setTimeout(() => {
                        loadPreGeneratedResults();
                    }, 1000);
                } else {
                    showAlert('AI 整理失敗：' + data.error, 'danger');
                }
            })
            .catch(error => {
                loadingModal.hide();
                showAlert('發生錯誤：' + error.message, 'danger');
            });
    }

    // 顯示 AI 整理結果
    function displayAIOrganization(data, typeName) {
        const resultDiv = document.getElementById('ai-organization-result');
        const contentDiv = document.getElementById('ai-organization-content');

        let html = `<h6 class="text-primary"><i class="fas fa-magic me-2"></i>${typeName}</h6>`;

        if (data.result.organized_content) {
            html += `<div class="alert alert-light">${data.result.organized_content.replace(/\n/g, '<br>')}</div>`;
        }

        // 根據不同的整理類型顯示特定內容
        if (data.organization_type === 'mindmap' && data.result.mindmap_structure) {
            html += '<h6>心智圖結構：</h6>';
            html += '<div class="small"><pre>' + JSON.stringify(data.result.mindmap_structure, null, 2) + '</pre></div>';
        } else if (data.organization_type === 'hierarchical' && data.result.main_points) {
            html += '<h6>主要重點：</h6><ul>';
            data.result.main_points.forEach(point => {
                html += `<li>${point}</li>`;
            });
            html += '</ul>';
        } else if (data.organization_type === 'qa_learning' && data.result.basic_questions) {
            html += '<h6>基礎問題：</h6><ul>';
            data.result.basic_questions.forEach(q => {
                html += `<li>${q}</li>`;
            });
            html += '</ul>';
        }

        contentDiv.innerHTML = html;
        resultDiv.style.display = 'block';
        resultDiv.scrollIntoView({ behavior: 'smooth' });
    }

    // 生成測驗
    function generateQuiz() {
        loadingModal.show();

        fetch(`/notes/${currentNoteId}/quiz`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
            .then(response => response.json())
            .then(data => {
                loadingModal.hide();
                if (data.success) {
                    displayQuiz(data.quiz);
                } else {
                    showAlert('生成測驗失敗：' + data.error, 'danger');
                }
            })
            .catch(error => {
                loadingModal.hide();
                showAlert('發生錯誤：' + error.message, 'danger');
            });
    }

    // 載入已保存的測驗
    function loadSavedQuiz() {
        fetch(`/notes/${currentNoteId}/quiz`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayQuiz(data.quiz);
                } else {
                    showAlert('沒有找到已保存的測驗', 'info');
                }
            })
            .catch(error => {
                showAlert('發生錯誤：' + error.message, 'danger');
            });
    }

    // 顯示測驗
    function displayQuiz(quiz) {
        const contentDiv = document.getElementById('quiz-content');
        const closeBtn = document.getElementById('quiz-close-btn');

        let html = '';

        if (quiz.questions) {
            quiz.questions.forEach((q, index) => {
                // 確保 options 始終是數組
                if (!Array.isArray(q.options)) {
                    console.warn(`Question ${index + 1} options is not an array. Converting...`);
                    if (typeof q.options === 'string') {
                        // 嘗試解析 JSON 字符串
                        try {
                            q.options = JSON.parse(q.options);
                            if (!Array.isArray(q.options)) {
                                q.options = [q.options.toString()];
                            }
                        } catch (e) {
                            // 如果解析失敗，將字符串轉為單元素數組
                            q.options = [q.options];
                        }
                    } else if (q.options === null || q.options === undefined) {
                        q.options = ['無選項'];
                    } else {
                        // 如果是其他類型，轉換為字符串並放入數組
                        q.options = [q.options.toString()];
                    }
                }
                
                html += `
                <div class="card mb-3">
                    <div class="card-header">
                        <strong>題目 ${index + 1}</strong>
                        <span class="badge bg-${q.difficulty === 'easy' ? 'success' : q.difficulty === 'medium' ? 'warning' : 'danger'} ms-2">
                            ${q.difficulty === 'easy' ? '簡單' : q.difficulty === 'medium' ? '中等' : '困難'}
                        </span>
                    </div>
                    <div class="card-body">
                        <p><strong>${q.question}</strong></p>
                        <div class="options">
                            ${q.options.map((option, i) => `
                                <div class="form-check">
                                    <input class="form-check-input" type="radio" name="q${index}" id="q${index}_${i}" value="${String.fromCharCode(65 + i)}">
                                    <label class="form-check-label" for="q${index}_${i}">
                                        ${String.fromCharCode(65 + i)}. ${option}
                                    </label>
                                </div>
                            `).join('')}
                        </div>
                        <div class="mt-2">
                            <button class="btn btn-sm btn-outline-info" onclick="showAnswer(${index}, '${q.correct_answer}', '${q.explanation}')">
                                顯示答案
                            </button>
                        </div>
                        <div id="answer-${index}" class="mt-2" style="display: none;"></div>
                    </div>
                </div>
            `;
            });
        }

        contentDiv.innerHTML = html;
        closeBtn.classList.remove('d-none'); // 顯示關閉按鈕
        document.querySelector('.card-header h5 i').classList.remove('fa-question-circle');
        document.querySelector('.card-header h5 i').classList.add('fa-check-circle');
        document.getElementById('quiz-controls').classList.add('d-none'); // 隱藏測驗控制區
        
        // 滾動到測驗區域
        contentDiv.scrollIntoView({ behavior: 'smooth' });
    }

    // 顯示答案
    function showAnswer(questionIndex, correctAnswer, explanation) {
        // 使用HTML實體進行轉義
        const escapedCorrectAnswer = correctAnswer.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
            
        const escapedExplanation = explanation.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
            
        const answerDiv = document.getElementById(`answer-${questionIndex}`);
        answerDiv.innerHTML = `
        <div class="alert alert-info">
            <strong>正確答案：${escapedCorrectAnswer}</strong><br>
            <small>${escapedExplanation}</small>
        </div>
    `;
        answerDiv.style.display = 'block';
    }

    // 隱藏 AI 結果
    function hideAIResult() {
        document.getElementById('ai-organization-result').style.display = 'none';
    }

    // 隱藏測驗結果
    function hideQuizResult() {
        document.getElementById('quiz-content').innerHTML = '';
        document.getElementById('quiz-close-btn').classList.add('d-none');
        document.getElementById('quiz-controls').classList.remove('d-none');
        document.querySelector('.card-header h5 i').classList.remove('fa-check-circle');
        document.querySelector('.card-header h5 i').classList.add('fa-question-circle');
    }
    
    // 生成模擬題並加入題庫
    function generateMockQuestions() {
        if (!currentNoteId) {
            showAlert('無法獲取筆記ID', 'danger');
            return;
        }
        
        // 顯示處理中提示
        const resultDiv = document.getElementById('mock-questions-result');
        resultDiv.innerHTML = `
            <div class="alert alert-info">
                <div class="spinner-border spinner-border-sm text-info me-2" role="status"></div>
                正在生成模擬題，請稍候...
            </div>
        `;
        resultDiv.style.display = 'block';
        
        // 禁用生成按鈕，避免重複點擊
        const generateBtn = document.getElementById('generate-questions-btn');
        generateBtn.disabled = true;
        
        // 發送請求
        fetch(`/notes/${currentNoteId}/generate-mock-questions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 成功生成模擬題
                let questionLinks = '';
                if (data.questions && data.questions.length > 0) {
                    questionLinks = '<ul class="mt-2">';
                    data.questions.forEach(q => {
                        questionLinks += `<li><a href="/question/${q.id}" target="_blank">${q.title}</a></li>`;
                    });
                    questionLinks += '</ul>';
                }
                
                resultDiv.innerHTML = `
                    <div class="alert alert-success">
                        <i class="fas fa-check-circle me-2"></i>
                        ${data.message}
                        ${questionLinks}
                    </div>
                `;
            } else {
                // 生成失敗
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        生成模擬題失敗: ${data.error || '未知錯誤'}
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('生成模擬題時發生錯誤:', error);
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    處理請求時發生錯誤，請稍後重試
                </div>
            `;
        })
        .finally(() => {
            // 恢復按鈕狀態
            generateBtn.disabled = false;
            
            // 滾動到結果區域
            resultDiv.scrollIntoView({ behavior: 'smooth' });
        });
    }

    // 簡單的 Markdown 渲染函數
    function renderMarkdown(text) {
        if (!text) return '';

        // 簡單的 Markdown 轉換
        return text
            // 標題
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            // 粗體
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/__(.*?)__/g, '<strong>$1</strong>')
            // 斜體
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/_(.*?)_/g, '<em>$1</em>')
            // 程式碼塊
            .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            // 連結
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>')
            // 引用
            .replace(/^> (.*$)/gim, '<blockquote>$1</blockquote>')
            // 列表項目
            .replace(/^\* (.*$)/gim, '<li>$1</li>')
            .replace(/^- (.*$)/gim, '<li>$1</li>')
            .replace(/^\d+\. (.*$)/gim, '<li>$1</li>')
            // 包裝列表
            .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
            // 段落
            .replace(/\n\n/g, '</p><p>')
            .replace(/^(?!<[hup]|<li|<blockquote)/gm, '<p>')
            .replace(/(?<!>)$/gm, '</p>')
            // 清理多餘的段落標籤
            .replace(/<p><\/p>/g, '')
            .replace(/<p>(<[hul])/g, '$1')
            .replace(/(<\/[hul]>)<\/p>/g, '$1');
    }

    // 顯示警告訊息
    function showAlert(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

        document.querySelector('.container').insertBefore(alertDiv, document.querySelector('.container').firstChild);

        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }

    // 將格式化內容應用到原始筆記
    function applyFormattedContent(type) {
        if (!confirm('警告：這將會替換原始筆記的內容！是否確定要繼續？')) {
            return;
        }

        // 獲取格式化的內容
        const analysisId = organizationAnalysisIds[type];
        if (!analysisId) {
            showAlert('無法找到格式化結果的ID，請重新生成', 'danger');
            return;
        }

        // 顯示讀取中
        loadingModal.show();

        // 發送請求更新筆記內容
        fetch(`/notes/${currentNoteId}/apply-formatted-content`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                analysis_id: analysisId
            })
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`伺服器回應錯誤，狀態碼: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                loadingModal.hide();
                if (data.success) {
                    showAlert('筆記內容已成功更新！請重新整理頁面以查看最新版本', 'success');
                    // 2秒後重新載入頁面
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                } else {
                    showAlert('更新筆記內容失敗：' + (data.error || '未知錯誤'), 'danger');
                }
            })
            .catch(error => {
                loadingModal.hide();
                console.error('應用格式化內容時出錯:', error);
                showAlert('發生錯誤：' + error.message, 'danger');
            });
    }