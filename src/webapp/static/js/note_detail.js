// note_detail.js - 筆記詳情頁面的 JavaScript 功能 (重構版本)

// 全域變數
let currentNoteId = null;
let loadingModal;
let organizationAnalysisIds = {};
let currentRequests = new Map(); // 追蹤當前的請求

// 清除舊的 AI 組織內容
function clearOldOrganizationContent() {
    console.log('清除舊的 AI 組織內容');
    
    // 取消所有正在進行的請求
    currentRequests.forEach((controller, requestId) => {
        console.log(`取消請求: ${requestId}`);
        controller.abort();
    });
    currentRequests.clear();
    
    // 清除 organizationAnalysisIds
    organizationAnalysisIds = {};
    
    // 只移除 AI 組織分頁（保留原始內容分頁和內容）
    const contentTabs = document.getElementById('content-tabs');
    if (contentTabs) {
        // 只移除 id 以 organization_ 開頭的分頁
        const organizationTabs = contentTabs.querySelectorAll('button[id^="organization_"]');
        organizationTabs.forEach(tab => {
            tab.parentElement.remove();
        });
    }

    // 只移除 AI 組織內容分頁（保留 #content）
    const tabContent = document.getElementById('content-tab-pane');
    if (tabContent) {
        const organizationPanes = tabContent.parentElement.querySelectorAll('.tab-pane[id^="organization_"]');
        organizationPanes.forEach(pane => {
            pane.remove();
        });
    }
    
    // 確保原始內容分頁處於活動狀態
    const originalTab = document.querySelector('button[data-bs-target="#original-content"]');
    const originalPane = document.getElementById('original-content');
    
    if (originalTab && originalPane) {
        // 移除所有分頁的活動狀態
        document.querySelectorAll('.nav-link.active').forEach(tab => {
            tab.classList.remove('active');
        });
        
        document.querySelectorAll('.tab-pane.active').forEach(pane => {
            pane.classList.remove('active', 'show');
        });
        
        // 激活原始內容分頁
        originalTab.classList.add('active');
        originalPane.classList.add('active', 'show');
    }
    
    // 關閉加載模態框
    if (loadingModal) {
        loadingModal.hide();
    }
    
    console.log('舊的 AI 組織內容已清除');
}

// 頁面載入時初始化
document.addEventListener('DOMContentLoaded', function () {
    // 確保 currentNoteId 已經被設置
    console.log('初始化 note_detail.js, currentNoteId:', currentNoteId);
    
    // 清除舊的 AI 組織內容
    clearOldOrganizationContent();
    
    // 初始化 loading modal
    const loadingModalElement = document.getElementById('loadingModal');
    if (loadingModalElement) {
        loadingModal = new bootstrap.Modal(loadingModalElement);
    } else {
        console.warn('找不到 loadingModal 元素');
    }
    
    // 全域錯誤處理
    window.addEventListener('error', function (event) {
        console.error('全域錯誤捕獲:', event.error);
        
        if (event.error instanceof SyntaxError && event.error.message.includes('JSON')) {
            console.warn('偵測到 JSON 解析錯誤');
            showAlert('偵測到資料格式錯誤，系統將嘗試自動修復', 'warning');
        }
    });
    
    loadPreGeneratedResults();
    initializeContentTabs();
});

// 初始化內容標籤頁
function initializeContentTabs() {
    const contentTabs = document.getElementById('content-tabs');
    
    if (contentTabs && !contentTabs.dataset.eventsBound) {
        contentTabs.dataset.eventsBound = 'true';
        
        contentTabs.addEventListener('click', function(event) {
            const triggerEl = event.target.closest('button[data-bs-toggle="tab"]');
            if (triggerEl && triggerEl.id !== 'add-organization-tab') {
                event.preventDefault();
                if (!event.target.closest('button[onclick*="removeOrganizationTab"]')) {
                    const tabName = triggerEl.getAttribute('data-bs-target');
                    if (tabName) {
                        // 先移除所有 tab-pane 的 active/show 狀態
                        document.querySelectorAll('.tab-pane').forEach(pane => {
                            pane.classList.remove('active', 'show');
                        });
                        // 先移除所有 nav-link 的 active 狀態
                        document.querySelectorAll('.nav-link').forEach(tab => {
                            tab.classList.remove('active');
                        });
                        // 激活當前 tab 與 pane
                        triggerEl.classList.add('active');
                        const targetPane = document.querySelector(tabName);
                        if (targetPane) {
                            targetPane.classList.add('active', 'show');
                        }
                    }
                }
            }
        });
    }
}

// 載入預先生成的結果
function loadPreGeneratedResults() {
    if (!currentNoteId) return;
    
    // 取消現有的載入請求
    const requestId = 'load_pre_generated';
    if (currentRequests.has(requestId)) {
        currentRequests.get(requestId).abort();
        currentRequests.delete(requestId);
    }

    // 創建新的 AbortController
    const controller = new AbortController();
    currentRequests.set(requestId, controller);
    
    fetch(`/notes/${currentNoteId}/pre-generated-results`, {
        signal: controller.signal
    })
        .then(response => response.json())
        .then(data => {
            // 清除完成的請求
            currentRequests.delete(requestId);
            
            console.log('預先生成結果回應:', data);
            
            if (data.success && data.results) {
                // 處理不同的 results 格式
                let resultsArray = [];
                
                if (Array.isArray(data.results)) {
                    resultsArray = data.results;
                } else if (typeof data.results === 'object') {
                    // 如果 results 是物件，轉換為陣列
                    resultsArray = Object.keys(data.results).map(key => ({
                        analysis_type: `organization_${key}`,
                        id: data.results[key].id || key,
                        result: data.results[key]
                    }));
                    console.log('轉換物件格式的 results 為陣列:', resultsArray);
                }
                
                if (resultsArray.length > 0) {
                    resultsArray.forEach(result => {
                        if (result.analysis_type && result.analysis_type.startsWith('organization_')) {
                            const orgType = result.analysis_type.replace('organization_', '');
                            organizationAnalysisIds[orgType] = result.id;
                            
                            const orgConfig = getOrganizationConfig(orgType);
                            if (orgConfig) {
                                addOrganizationTab(orgType, orgConfig.name, orgConfig.icon, result.result);
                            }
                        }
                    });
                    
                    // 所有標籤載入完畢後，確保切換回原始內容標籤
                    setTimeout(() => {
                        const originalTab = document.querySelector('button[data-bs-target="#original-content"]');
                        const originalPane = document.getElementById('original-content');
                        
                        if (originalTab && originalPane) {
                            // 移除所有分頁的活動狀態
                            document.querySelectorAll('.nav-link.active').forEach(tab => {
                                tab.classList.remove('active');
                            });
                            
                            document.querySelectorAll('.tab-pane.active').forEach(pane => {
                                pane.classList.remove('active', 'show');
                            });
                            
                            // 激活原始內容分頁
                            originalTab.classList.add('active');
                            originalPane.classList.add('active', 'show');
                            console.log('已強制切換回原始內容標籤');
                        }
                    }, 100);
                } else {
                    console.log('沒有找到預先生成的結果');
                }
            } else {
                console.log('沒有預先生成的結果或回應不成功');
            }
        })
        .catch(error => {
            // 清除完成或失敗的請求
            currentRequests.delete(requestId);
            
            // 檢查是否是請求被取消
            if (error.name === 'AbortError') {
                console.log('載入預先生成結果請求被取消');
                return;
            }
            
            console.error('載入預先生成結果失敗:', error);
        });
}

// 取得整理配置
function getOrganizationConfig(type) {
    const configs = {
        'mindmap': { name: '心智圖', icon: 'fas fa-project-diagram' },
        'hierarchical': { name: '層次化筆記', icon: 'fas fa-sitemap' },
        'feynman': { name: '費曼技巧', icon: 'fas fa-graduation-cap' },
        'qa_learning': { name: '問答式學習', icon: 'fas fa-question-circle' },
        'comparison': { name: '比較分析', icon: 'fas fa-balance-scale' },
        'memory_palace': { name: '記憶宮殿', icon: 'fas fa-brain' },
        'mandala_ninegrid': { name: '曼陀羅九宮格', icon: 'fas fa-th' },
        'format_enhance': { name: '格式化與補強', icon: 'fas fa-magic' }
    };
    return configs[type];
}

// 顯示整理選擇器
function showOrganizationSelector() {
    const organizationTypes = [
        { type: 'mindmap', name: '心智圖', icon: 'fas fa-project-diagram', description: '將內容轉換為視覺化心智圖' },
        { type: 'hierarchical', name: '層次化筆記', icon: 'fas fa-sitemap', description: '按主題層次整理內容' },
        { type: 'feynman', name: '費曼技巧', icon: 'fas fa-graduation-cap', description: '用簡單語言解釋複雜概念' },
        { type: 'qa_learning', name: '問答式學習', icon: 'fas fa-question-circle', description: '生成問答對幫助記憶' },
        { type: 'comparison', name: '比較分析', icon: 'fas fa-balance-scale', description: '對比分析不同概念' },
        { type: 'memory_palace', name: '記憶宮殿', icon: 'fas fa-brain', description: '空間記憶法整理內容' },
        { type: 'mandala_ninegrid', name: '曼陀羅九宮格', icon: 'fas fa-th', description: '九宮格思維導圖' },
        { type: 'format_enhance', name: '格式化與補強', icon: 'fas fa-magic', description: '美化格式並補充內容' }
    ];

    let modalHtml = `
        <div class="modal fade" id="organizationModal" tabindex="-1" aria-labelledby="organizationModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="organizationModalLabel">
                            <i class="fas fa-robot me-2"></i>AI 筆記整理
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="關閉"></button>
                    </div>
                    <div class="modal-body">
                        <p class="text-muted mb-4">選擇一種整理方式，AI 將會為您重新組織筆記內容：</p>
                        <div class="row g-3">`;

    organizationTypes.forEach(org => {
        modalHtml += `
            <div class="col-md-6">
                <div class="card h-100 organization-card" onclick="organizeNote('${org.type}', '${org.name}', '${org.icon}')" style="cursor: pointer;">
                    <div class="card-body text-center">
                        <i class="${org.icon} fa-2x text-primary mb-3"></i>
                        <h6 class="card-title">${org.name}</h6>
                        <p class="card-text small text-muted">${org.description}</p>
                    </div>
                </div>
            </div>`;
    });

    modalHtml += `
                        </div>
                    </div>
                </div>
            </div>
        </div>`;

    // 移除舊的 modal（如果存在）
    const existingModal = document.getElementById('organizationModal');
    if (existingModal) {
        existingModal.remove();
    }

    // 添加新的 modal
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // 顯示 modal
    const modal = new bootstrap.Modal(document.getElementById('organizationModal'));
    modal.show();

    // 添加 hover 效果
    document.querySelectorAll('.organization-card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
            this.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
        });

        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '';
        });
    });
}

// AI 整理筆記
function organizeNote(type, name, icon) {
    console.log('開始 AI 整理:', { type, name, icon, currentNoteId });
    
    // 檢查 currentNoteId
    if (!currentNoteId) {
        console.error('currentNoteId 未設置');
        showAlert('無法取得筆記 ID，請重新載入頁面', 'danger');
        return;
    }
    
    // 關閉選擇器 modal
    const organizationModal = bootstrap.Modal.getInstance(document.getElementById('organizationModal'));
    if (organizationModal) {
        organizationModal.hide();
    }

    // 檢查是否已經存在這種類型的整理
    if (organizationAnalysisIds[type]) {
        if (!confirm(`已存在「${name}」的整理結果，確定要重新生成嗎？`)) {
            return;
        }
    }

    // 取消現有的同類型請求
    const requestId = `organize_${type}`;
    if (currentRequests.has(requestId)) {
        currentRequests.get(requestId).abort();
        currentRequests.delete(requestId);
    }

    // 創建新的 AbortController
    const controller = new AbortController();
    currentRequests.set(requestId, controller);

    // 開始生成
    loadingModal.show();

    fetch(`/notes/${currentNoteId}/organize`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            organization_type: type
        }),
        signal: controller.signal
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`伺服器回應錯誤，狀態碼: ${response.status}`);
        }
        return response.json().catch(err => {
            console.error("JSON解析失敗:", err);
            return response.text().then(text => ({
                success: false,
                error: "JSON解析失敗",
                raw_text: text
            }));
        });
    })
    .then(data => {
        // 清除完成的請求
        currentRequests.delete(requestId);
        loadingModal.hide();

        console.log('AI整理回應數據:', data);

        if (data.raw_text) {
            console.error("API回傳的資料無法解析為JSON");
            showAlert(`解析 ${name} 回應資料失敗，請查看控制台獲取詳細信息`, 'danger');
            return;
        }

        if (data.success) {
            console.log('AI 整理成功，準備建立標籤頁:', { type, name, result: data.result });
            
            if (data.analysis_id) {
                organizationAnalysisIds[type] = data.analysis_id;
            }

            if (type === 'format_enhance') {
                handleFormatEnhanceResult(data.result);
                showAlert(`${name} 完成！原始內容已更新`, 'success');
            } else {
                console.log('調用 addOrganizationTab');
                addOrganizationTab(type, name, icon, data.result);
                showAlert(`${name} 整理完成！`, 'success');
            }
        } else {
            console.error('AI整理失敗:', data.error);
            showAlert(`${name} 整理失敗: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        // 清除完成或失敗的請求
        currentRequests.delete(requestId);
        loadingModal.hide();
        
        // 檢查是否是請求被取消
        if (error.name === 'AbortError') {
            console.log(`請求被取消: ${name}`);
            return; // 不顯示錯誤訊息，因為是主動取消
        }
        
        console.error('整理請求失敗:', error);
        showAlert(`${name} 整理失敗: ${error.message}`, 'danger');
    });
}

// 添加整理標籤頁
function addOrganizationTab(type, name, icon, result) {
    console.log('addOrganizationTab 被調用:', { type, name, icon, result });
    
    const contentTabs = document.getElementById('content-tabs');
    const contentTabsContent = document.getElementById('content-tab-content');
    
    console.log('找到的元素:', { contentTabs, contentTabsContent });
    
    if (!contentTabs || !contentTabsContent) {
        console.error('找不到標籤容器元素:', { contentTabs, contentTabsContent });
        return;
    }

    const tabId = `${type}-tab`;
    const contentId = `${type}-content`;

    // 移除現有的標籤（如果存在）
    const existingTab = document.getElementById(tabId);
    const existingContent = document.getElementById(contentId);
    if (existingTab) existingTab.remove();
    if (existingContent) existingContent.remove();

    // 創建新標籤
    const tabButton = document.createElement('li');
    tabButton.className = 'nav-item';
    tabButton.innerHTML = `
        <button class="nav-link" id="${tabId}" data-bs-toggle="tab" data-bs-target="#${contentId}" type="button">
            <i class="${icon} me-2"></i>${name}
            <button type="button" class="btn btn-sm btn-link text-danger ms-2 p-0" 
                    onclick="removeOrganizationTab('${type}', '${name}')" 
                    title="刪除此整理">
                <i class="fas fa-times"></i>
            </button>
        </button>
    `;

    // 找到 "+" 按鈕並在其前面插入新標籤
    const addButton = document.getElementById('add-organization-tab');
    console.log('找到的新增按鈕:', addButton);
    
    if (addButton && addButton.parentElement) {
        contentTabs.insertBefore(tabButton, addButton.parentElement);
        console.log('標籤已插入到新增按鈕前面');
    } else {
        contentTabs.appendChild(tabButton);
        console.log('標籤已附加到容器末端');
    }

    // 創建內容區域
    const tabContent = document.createElement('div');
    tabContent.className = 'tab-pane fade';
    tabContent.id = contentId;
    tabContent.innerHTML = formatOrganizationResult(type, result);
    
    contentTabsContent.appendChild(tabContent);
    console.log('內容區域已創建:', contentId);

    // 不自動切換到新標籤，保持原始內容為預設
    console.log('標籤已創建但不自動切換:', tabId);
}

// 通用內容解析函數 - 處理嵌套的 JSON 結構
function parseNestedContent(result, contentType) {
    console.log(`解析 ${contentType} 內容:`, result, typeof result);
    
    // 如果是資料庫記錄格式 {analysis_id, created_at, result: {...}}
    if (result && typeof result === 'object' && result.result) {
        console.log(`偵測到資料庫記錄格式，使用 result 欄位:`, result.result);
        result = result.result;
    }
    
    // 處理嵌套的結構：如果有 content 欄位，則使用 content
    if (result && typeof result === 'object' && result.content) {
        if (typeof result.content === 'string') {
            try {
                const parsed = JSON.parse(result.content);
                console.log(`成功解析 ${contentType} content 欄位中的 JSON:`, parsed);
                return { success: true, data: parsed };
            } catch (e) {
                console.error(`解析 ${contentType} content 欄位 JSON 失敗:`, e);
                return { success: false, error: `解析錯誤：${result.content}` };
            }
        } else {
            // content 已經是物件，直接使用
            return { success: true, data: result.content };
        }
    } 
    // 如果 result 本身是字符串，嘗試解析
    else if (typeof result === 'string') {
        try {
            const parsed = JSON.parse(result);
            return { success: true, data: parsed };
        } catch (e) {
            console.error(`解析 ${contentType} JSON 失敗:`, e);
            return { success: false, error: `解析錯誤：${result}` };
        }
    }
    // 如果 result 已經是物件，直接使用
    else if (typeof result === 'object' && result !== null) {
        return { success: true, data: result };
    }
    
    return { success: false, error: `無效的 ${contentType} 內容格式` };
}

// 格式化整理結果
function formatOrganizationResult(type, result) {
    console.log('formatOrganizationResult 被調用:', { type, result, typeOfResult: typeof result });
    
    let html = '<div class="p-3">';

    try {
        // 處理資料庫格式：{analysis_id: xxx, created_at: xxx, result: {actual_content}}
        if (result && typeof result === 'object' && result.result) {
            console.log('偵測到資料庫格式，使用 result 欄位:', result.result);
            result = result.result;
        }
        
        // 現在對實際內容進行解析
        const parseResult = parseNestedContent(result, type);
        
        if (!parseResult.success) {
            html += `<div class="alert alert-warning">${parseResult.error}</div>`;
            html += '</div>';
            return html;
        }
        
        result = parseResult.data;
        console.log(`${type} 最終解析後的資料:`, result);

        if (type === 'mindmap') {
            html += formatMindmapContent(result);
        } else if (type === 'hierarchical') {
            html += formatHierarchicalContent(result);
        } else if (type === 'feynman') {
            html += formatFeynmanContent(result);
        } else if (type === 'qa_learning') {
            html += formatQALearningContent(result);
        } else if (type === 'comparison') {
            html += formatComparisonContent(result);
        } else if (type === 'memory_palace') {
            html += formatMemoryPalaceContent(result);
        } else if (type === 'mandala_ninegrid') {
            html += formatMandalaNineGridContent(result);
        } else {
            html += formatGenericContent(result);
        }
    } catch (error) {
        console.error(`格式化 ${type} 結果時出錯:`, error);
        html += generateFallbackContent(type, result);
    }

    html += '</div>';
    return html;
}

// 格式化心智圖內容
function formatMindmapContent(result) {
    console.log('formatMindmapContent 處理:', result, typeof result);
    
    let html = '';
    
    // 優先使用 mindmap_data 進行 ECharts 渲染
    if (result.mindmap_data) {
        const chartId = `echart-mindmap-${Date.now()}`;
        html += '<h6><i class="fas fa-project-diagram me-2 text-primary"></i>心智圖 <small class="text-muted">(可拖拽縮放)</small></h6>';
        html += `<div class="mindmap-scroll-container" style="width: 100%; height: 800px; overflow: hidden; border: 1px solid #eee; position: relative; user-select: none;">
            <div id="${chartId}" style="width: 200%; height: 120%; min-width: 1600px; min-height: 960px;" class="mindmap-container"></div>
        </div>`;
        
        // 初始化 ECharts 並支援拖曳與縮放
        setTimeout(() => {
            try {
                const chartDom = document.getElementById(chartId);
                const scrollContainer = chartDom ? chartDom.parentElement : null;
                if (chartDom && scrollContainer && typeof echarts !== 'undefined') {
                    const myChart = echarts.init(chartDom);
                    const option = {
                        series: [{
                            type: 'tree',
                            data: [result.mindmap_data],
                            top: '5%', left: '5%', bottom: '5%', right: '10%',
                            symbolSize: 16,
                            layout: 'orthogonal',
                            orient: 'LR',
                            edgeShape: 'polyline',
                            itemStyle: { borderColor: '#c23531' },
                            lineStyle: { color: '#c23531' },
                            label: { fontSize: 12, fontWeight: 'bold' }
                        }],
                        toolbox: {
                            show: true,
                            feature: {
                                saveAsImage: {},
                                restore: {}
                            }
                        },
                        animation: true
                    };
                    myChart.setOption(option);

                    // 支援左右拖曳（平移）
                    let isDragging = false;
                    let startX = 0, startY = 0;
                    let scrollLeftStart = 0, scrollTopStart = 0;
                    scrollContainer.style.cursor = 'grab';
                    scrollContainer.addEventListener('mousedown', function(e) {
                        isDragging = true;
                        startX = e.pageX - scrollContainer.offsetLeft;
                        startY = e.pageY - scrollContainer.offsetTop;
                        scrollLeftStart = scrollContainer.scrollLeft;
                        scrollTopStart = scrollContainer.scrollTop;
                        scrollContainer.style.cursor = 'grabbing';
                        e.preventDefault();
                    });
                    scrollContainer.addEventListener('mousemove', function(e) {
                        if (!isDragging) return;
                        e.preventDefault();
                        const x = e.pageX - scrollContainer.offsetLeft;
                        const y = e.pageY - scrollContainer.offsetTop;
                        const walkX = (x - startX) * 1.2;
                        const walkY = (y - startY) * 1.2;
                        const newScrollLeft = scrollLeftStart - walkX;
                        const newScrollTop = scrollTopStart - walkY;
                        const maxScrollLeft = scrollContainer.scrollWidth - scrollContainer.clientWidth;
                        const maxScrollTop = scrollContainer.scrollHeight - scrollContainer.clientHeight;
                        scrollContainer.scrollLeft = Math.max(0, Math.min(maxScrollLeft, newScrollLeft));
                        scrollContainer.scrollTop = Math.max(0, Math.min(maxScrollTop, newScrollTop));
                    });
                    scrollContainer.addEventListener('mouseup', function() {
                        isDragging = false;
                        scrollContainer.style.cursor = 'grab';
                    });
                    scrollContainer.addEventListener('mouseleave', function() {
                        isDragging = false;
                        scrollContainer.style.cursor = 'grab';
                    });

                    // 滾輪縮放
                    scrollContainer.addEventListener('wheel', function(e) {
                        e.preventDefault();
                        const scaleStep = 0.1;
                        let curWidth = chartDom.offsetWidth;
                        let curHeight = chartDom.offsetHeight;
                        if (e.deltaY < 0) {
                            curWidth *= (1 + scaleStep);
                            curHeight *= (1 + scaleStep);
                        } else {
                            curWidth *= (1 - scaleStep);
                            curHeight *= (1 - scaleStep);
                        }
                        chartDom.style.width = curWidth + 'px';
                        chartDom.style.height = curHeight + 'px';
                        myChart.resize();
                    });
                } else {
                    console.warn('ECharts 未載入或 chartDom 不存在');
                }
            } catch (e) {
                console.error("ECharts 心智圖初始化失敗:", e);
            }
        }, 150);
    }
    // 如果沒有 mindmap_data，嘗試使用 mindmap_code 進行 Mermaid 渲染
    else if (result.mindmap_code) {
        html += '<h6><i class="fas fa-project-diagram me-2 text-primary"></i>心智圖</h6>';
        html += `<div class="mindmap-container mb-3" id="mindmap-${Date.now()}">`;
        html += '<div class="mermaid">' + result.mindmap_code + '</div>';
        html += '</div>';
        
        // 初始化 Mermaid
        if (typeof mermaid !== 'undefined') {
            setTimeout(() => {
                mermaid.init();
            }, 100);
        }
    }
    // 後備方案：使用 mindmap_structure 顯示結構
    else if (result.mindmap_structure) {
        html += '<h6><i class="fas fa-project-diagram me-2 text-primary"></i>心智圖結構</h6>';
        html += '<div class="small"><pre class="bg-light p-2">' + JSON.stringify(result.mindmap_structure, null, 2) + '</pre></div>';
    }
    // 最終後備：顯示其他可能的欄位
    else if (result.central_topic && result.main_branches) {
        html += '<h6><i class="fas fa-project-diagram me-2 text-primary"></i>心智圖內容</h6>';
        html += `<div class="alert alert-info">
            <h6>中心主題：${result.central_topic}</h6>
            <p><strong>主要分支：</strong></p>
            <ul>`;
        
        if (Array.isArray(result.main_branches)) {
            result.main_branches.forEach(branch => {
                if (typeof branch === 'string') {
                    html += `<li>${branch}</li>`;
                } else if (branch.name) {
                    html += `<li>${branch.name}</li>`;
                }
            });
        }
        
        html += '</ul></div>';
    }
    // 如果都沒有，顯示所有可用欄位
    else {
        html += '<h6><i class="fas fa-project-diagram me-2 text-primary"></i>心智圖內容</h6>';
        html += '<div class="alert alert-warning">';
        html += '<p>未找到預期的心智圖欄位，顯示原始資料：</p>';
        html += '<pre class="small">' + JSON.stringify(result, null, 2) + '</pre>';
        html += '</div>';
    }
    
    if (result.question_summary) {
        html += '<h6><i class="fas fa-info-circle me-2 text-info"></i>題目摘要</h6>';
        html += `<div class="alert alert-info">${renderMarkdown(result.question_summary.summary || '')}</div>`;
        
        if (result.question_summary.solving_tips) {
            html += '<h6><i class="fas fa-lightbulb me-2 text-warning"></i>解題技巧</h6>';
            html += `<div class="alert alert-warning">${renderMarkdown(result.question_summary.solving_tips)}</div>`;
        }
    }
    
    return html;
}

// 格式化層次化內容
function formatHierarchicalContent(result) {
    console.log('formatHierarchicalContent 處理:', result, typeof result);
    
    let html = '<div class="hierarchical-container">';
    
    if (result.title) {
        html += `<h4 class="text-center mb-4">${result.title}</h4>`;
    }

    if (result.main_points && Array.isArray(result.main_points)) {
        html += '<h5><i class="fas fa-list me-2 text-primary"></i>主要重點</h5>';
        html += '<ul class="list-group mb-4">';
        result.main_points.forEach(point => {
            html += `<li class="list-group-item">${renderMarkdown(point)}</li>`;
        });
        html += '</ul>';
    }

    if (result.sub_points && Array.isArray(result.sub_points)) {
        html += '<h5><i class="fas fa-sitemap me-2 text-success"></i>子重點</h5>';
        html += '<div class="row">';
        result.sub_points.forEach((sub, idx) => {
            html += '<div class="col-md-6 mb-3">';
            html += '<div class="card">';
            html += '<div class="card-body">';
            html += `<h6 class="card-title">${sub.title || `子重點 ${idx + 1}`}</h6>`;
            html += `<div class="card-text">${renderMarkdown(sub.content || '')}</div>`;
            html += '</div></div></div>';
        });
        html += '</div>';
    }

    if (result.key_concepts && Array.isArray(result.key_concepts)) {
        html += '<h5><i class="fas fa-lightbulb me-2 text-warning"></i>關鍵概念</h5>';
        html += '<div class="row">';
        result.key_concepts.forEach(concept => {
            html += '<div class="col-md-6 mb-3">';
            html += '<div class="card border-warning">';
            html += '<div class="card-body">';
            html += `<h6 class="card-title text-warning">${concept.term}</h6>`;
            html += `<div class="card-text">${renderMarkdown(concept.definition || '')}</div>`;
            html += '</div></div></div>';
        });
        html += '</div>';
    }

    if (result.learning_tips) {
        html += '<h5><i class="fas fa-graduation-cap me-2 text-info"></i>學習建議</h5>';
        html += '<div class="alert alert-info">';
        html += renderMarkdown(result.learning_tips);
        html += '</div>';
    }

    html += '</div>';
    return html;
}

// 格式化費曼技巧內容
function formatFeynmanContent(result) {
    console.log('formatFeynmanContent 處理:', result, typeof result);
    
    let html = '<div class="feynman-container">';
    
    if (result.simple_explanation) {
        html += '<h6><i class="fas fa-lightbulb me-2 text-warning"></i>簡單解釋</h6>';
        html += `<div class="alert alert-light border-start border-4 border-warning">${renderMarkdown(result.simple_explanation)}</div>`;
    }
    
    if (result.analogies) {
        html += '<h6><i class="fas fa-link me-2 text-info"></i>類比說明</h6>';
        
        if (Array.isArray(result.analogies)) {
            result.analogies.forEach(analogy => {
                html += `<div class="card mb-3">`;
                html += `<div class="card-body">${renderMarkdown(analogy)}</div>`;
                html += `</div>`;
            });
        } else if (typeof result.analogies === 'string') {
            html += `<div class="card mb-3">`;
            html += `<div class="card-body">${renderMarkdown(result.analogies)}</div>`;
            html += `</div>`;
        }
    }
    
    if (result.examples) {
        html += '<h6><i class="fas fa-example me-2 text-success"></i>實例說明</h6>';
        
        if (Array.isArray(result.examples)) {
            html += '<div class="list-group">';
            result.examples.forEach(example => {
                html += `<div class="list-group-item">${renderMarkdown(example)}</div>`;
            });
            html += '</div>';
        } else if (typeof result.examples === 'string') {
            html += `<div class="list-group">`;
            html += `<div class="list-group-item">${renderMarkdown(result.examples)}</div>`;
            html += '</div>';
        }
    }
    
    if (result.key_concepts) {
        html += '<h6><i class="fas fa-key me-2 text-primary"></i>關鍵概念</h6>';
        
        if (Array.isArray(result.key_concepts)) {
            html += '<ul class="list-group list-group-flush">';
            result.key_concepts.forEach(concept => {
                html += `<li class="list-group-item">${renderMarkdown(concept)}</li>`;
            });
            html += '</ul>';
        }
    }
    
    html += '</div>';
    return html;
}

// 格式化問答式學習內容
function formatQALearningContent(result) {
    console.log('formatQALearningContent 處理:', result, typeof result);
    
    let html = '<div class="qa-learning-container">';
    
    if (result.topic) {
        html += `<h4 class="text-center mb-4 text-primary"><i class="fas fa-graduation-cap me-2"></i>${result.topic}</h4>`;
    }
    
    if (result.qa_pairs && Array.isArray(result.qa_pairs)) {
        html += '<h5><i class="fas fa-question-circle me-2 text-primary"></i>問答練習</h5>';
        
        result.qa_pairs.forEach((qa, index) => {
            html += `<div class="card mb-4 shadow-sm">`;
            html += `<div class="card-header bg-primary text-white">`;
            html += `<h6 class="mb-0"><i class="fas fa-question me-2"></i>問題 ${index + 1}</h6>`;
            html += `</div>`;
            html += `<div class="card-body">`;
            
            // 問題
            html += `<div class="mb-3">`;
            html += `<h6 class="text-primary"><i class="fas fa-question-circle me-2"></i>問題</h6>`;
            html += `<p class="border-start border-primary border-3 ps-3">${renderMarkdown(qa.question)}</p>`;
            html += `</div>`;
            
            // 答案
            html += `<div class="mb-3">`;
            html += `<h6 class="text-success"><i class="fas fa-check-circle me-2"></i>答案</h6>`;
            html += `<div class="alert alert-light border-start border-success border-3">${renderMarkdown(qa.answer)}</div>`;
            html += `</div>`;
            
            // 解釋
            if (qa.explanation) {
                html += `<div class="mb-3">`;
                html += `<h6 class="text-info"><i class="fas fa-lightbulb me-2"></i>詳細解釋</h6>`;
                html += `<div class="alert alert-info">${renderMarkdown(qa.explanation)}</div>`;
                html += `</div>`;
            }
            
            // 關鍵要點
            if (qa.key_points && Array.isArray(qa.key_points) && qa.key_points.length > 0) {
                html += `<div class="mb-3">`;
                html += `<h6 class="text-warning"><i class="fas fa-key me-2"></i>關鍵要點</h6>`;
                html += '<ul class="list-group list-group-flush">';
                qa.key_points.forEach(point => {
                    html += `<li class="list-group-item border-0 px-0"><i class="fas fa-arrow-right me-2 text-warning"></i>${renderMarkdown(point)}</li>`;
                });
                html += '</ul>';
                html += `</div>`;
            }
            
            html += `</div></div>`;
        });
    }
    
    // 學習建議
    if (result.learning_tips && Array.isArray(result.learning_tips) && result.learning_tips.length > 0) {
        html += '<div class="mt-4">';
        html += '<h5><i class="fas fa-lightbulb me-2 text-warning"></i>學習建議</h5>';
        html += '<div class="alert alert-warning">';
        html += '<ul class="mb-0">';
        result.learning_tips.forEach(tip => {
            html += `<li>${renderMarkdown(tip)}</li>`;
        });
        html += '</ul>';
        html += '</div>';
        html += '</div>';
    }
    
    // 復習問題
    if (result.review_questions && Array.isArray(result.review_questions) && result.review_questions.length > 0) {
        html += '<div class="mt-4">';
        html += '<h5><i class="fas fa-clipboard-check me-2 text-secondary"></i>復習檢測</h5>';
        html += '<div class="alert alert-secondary">';
        html += '<ol>';
        result.review_questions.forEach(question => {
            html += `<li class="mb-2">${renderMarkdown(question)}</li>`;
        });
        html += '</ol>';
        html += '</div>';
        html += '</div>';
    }
    
    // 總結
    if (result.summary) {
        html += '<div class="mt-4">';
        html += '<h5><i class="fas fa-bookmark me-2 text-info"></i>學習總結</h5>';
        html += `<div class="alert alert-info border-start border-info border-4">${renderMarkdown(result.summary)}</div>`;
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

// 格式化比較分析內容
function formatComparisonContent(result) {
    console.log('formatComparisonContent 處理:', result, typeof result);
    
    let html = '<div class="comparison-container">';
    
    // 關鍵概念
    if (result.key_concepts && Array.isArray(result.key_concepts)) {
        html += '<h6><i class="fas fa-key me-2 text-primary"></i>關鍵概念</h6>';
        html += '<div class="list-group mb-3">';
        result.key_concepts.forEach(concept => {
            html += `<div class="list-group-item">${renderMarkdown(concept)}</div>`;
        });
        html += '</div>';
    }
    
    // 相似點
    if (result.similarities && Array.isArray(result.similarities)) {
        html += '<h6><i class="fas fa-equals me-2 text-success"></i>相似點</h6>';
        html += '<div class="alert alert-success">';
        html += '<ul>';
        result.similarities.forEach(similarity => {
            html += `<li>${renderMarkdown(similarity)}</li>`;
        });
        html += '</ul></div>';
    }
    
    // 差異點
    if (result.differences && Array.isArray(result.differences)) {
        html += '<h6><i class="fas fa-not-equal me-2 text-warning"></i>差異點</h6>';
        html += '<div class="alert alert-warning">';
        html += '<ul>';
        result.differences.forEach(difference => {
            html += `<li>${renderMarkdown(difference)}</li>`;
        });
        html += '</ul></div>';
    }
    
    // 關聯性
    if (result.relationships && Array.isArray(result.relationships)) {
        html += '<h6><i class="fas fa-link me-2 text-info"></i>關聯性</h6>';
        html += '<div class="alert alert-info">';
        html += '<ul>';
        result.relationships.forEach(relationship => {
            html += `<li>${renderMarkdown(relationship)}</li>`;
        });
        html += '</ul></div>';
    }
    
    // 比較表格
    if (result.comparison_table && Array.isArray(result.comparison_table)) {
        html += '<h6><i class="fas fa-table me-2 text-primary"></i>比較表格</h6>';
        html += '<div class="table-responsive">';
        html += '<table class="table table-bordered table-striped">';
        
        // 假設第一個對象定義了表頭
        if (result.comparison_table.length > 0) {
            const headers = Object.keys(result.comparison_table[0]);
            html += '<thead class="table-dark"><tr>';
            headers.forEach(header => {
                html += `<th>${header}</th>`;
            });
            html += '</tr></thead><tbody>';
            
            result.comparison_table.forEach(row => {
                html += '<tr>';
                headers.forEach(header => {
                    html += `<td>${renderMarkdown(row[header] || '')}</td>`;
                });
                html += '</tr>';
            });
            html += '</tbody>';
        }
        
        html += '</table></div>';
    } else if (typeof result.comparison_table === 'string') {
        html += '<h6><i class="fas fa-table me-2 text-primary"></i>比較分析</h6>';
        html += `<div class="alert alert-light">${renderMarkdown(result.comparison_table)}</div>`;
    }
    
    // 優缺點分析
    if (result.pros_and_cons && Array.isArray(result.pros_and_cons)) {
        html += '<h6><i class="fas fa-balance-scale me-2 text-secondary"></i>優缺點分析</h6>';
        html += '<div class="row">';
        result.pros_and_cons.forEach(item => {
            html += '<div class="col-md-6 mb-3">';
            html += '<div class="card">';
            html += `<div class="card-header"><strong>${item.concept || '項目'}</strong></div>`;
            html += '<div class="card-body">';
            
            if (item.pros && Array.isArray(item.pros)) {
                html += '<h6 class="text-success">優點</h6>';
                html += '<ul class="text-success">';
                item.pros.forEach(pro => {
                    html += `<li>${renderMarkdown(pro)}</li>`;
                });
                html += '</ul>';
            }
            
            if (item.cons && Array.isArray(item.cons)) {
                html += '<h6 class="text-danger">缺點</h6>';
                html += '<ul class="text-danger">';
                item.cons.forEach(con => {
                    html += `<li>${renderMarkdown(con)}</li>`;
                });
                html += '</ul>';
            }
            
            html += '</div></div></div>';
        });
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

// 格式化記憶宮殿內容
function formatMemoryPalaceContent(result) {
    console.log('formatMemoryPalaceContent 處理:', result, typeof result);
    
    let html = '<div class="memory-palace-container">';
    
    // 記憶故事
    if (result.memory_story) {
        html += '<h6><i class="fas fa-book-open me-2 text-primary"></i>記憶故事</h6>';
        html += `<div class="alert alert-primary">${renderMarkdown(result.memory_story)}</div>`;
    }
    
    // 空間佈局
    if (result.spatial_layout) {
        html += '<h6><i class="fas fa-map me-2 text-info"></i>空間佈局</h6>';
        html += `<div class="alert alert-info">${renderMarkdown(result.spatial_layout)}</div>`;
    }
    
    // 關鍵錨點
    if (result.key_anchors && Array.isArray(result.key_anchors)) {
        html += '<h6><i class="fas fa-anchor me-2 text-success"></i>關鍵錨點</h6>';
        html += '<div class="row">';
        
        result.key_anchors.forEach((anchor, index) => {
            html += '<div class="col-md-6 mb-3">';
            html += '<div class="card border-success">';
            html += `<div class="card-header bg-success text-white">`;
            html += `<h6 class="mb-0">${anchor.anchor || `錨點 ${index + 1}`}</h6>`;
            html += `</div>`;
            html += '<div class="card-body">';
            
            if (anchor.content) {
                html += `<p><strong>內容:</strong> ${renderMarkdown(anchor.content)}</p>`;
            }
            
            if (anchor.visual) {
                html += `<p><strong>視覺想像:</strong> ${renderMarkdown(anchor.visual)}</p>`;
            }
            
            html += '</div></div></div>';
        });
        
        html += '</div>';
    }
    
    // 視覺想像
    if (result.visual_imagery) {
        html += '<h6><i class="fas fa-eye me-2 text-warning"></i>視覺想像</h6>';
        html += `<div class="alert alert-warning">${renderMarkdown(result.visual_imagery)}</div>`;
    }
    
    // 記憶提示
    if (result.memory_cues && Array.isArray(result.memory_cues)) {
        html += '<h6><i class="fas fa-lightbulb me-2 text-secondary"></i>記憶提示</h6>';
        html += '<div class="alert alert-secondary">';
        html += '<ul>';
        result.memory_cues.forEach(cue => {
            html += `<li>${renderMarkdown(cue)}</li>`;
        });
        html += '</ul></div>';
    }
    
    // 練習建議
    if (result.practice_routine) {
        html += '<h6><i class="fas fa-dumbbell me-2 text-dark"></i>練習建議</h6>';
        html += `<div class="alert alert-dark">${renderMarkdown(result.practice_routine)}</div>`;
    }
    
    // 備用欄位處理
    if (result.location) {
        html += '<h6><i class="fas fa-map-marker-alt me-2 text-primary"></i>記憶地點</h6>';
        html += `<div class="alert alert-primary">${renderMarkdown(result.location)}</div>`;
    }
    
    if (result.route) {
        html += '<h6><i class="fas fa-route me-2 text-info"></i>行進路線</h6>';
        html += `<div class="alert alert-info">${renderMarkdown(result.route)}</div>`;
    }
    
    if (result.memory_stations && Array.isArray(result.memory_stations)) {
        html += '<h6><i class="fas fa-brain me-2 text-success"></i>記憶站點</h6>';
        
        result.memory_stations.forEach((station, index) => {
            html += `<div class="card mb-3">`;
            html += `<div class="card-header">`;
            html += `<h6 class="mb-0">站點 ${index + 1}: ${station.position || ''}</h6>`;
            html += `</div>`;
            html += `<div class="card-body">`;
            html += `<p><strong>內容:</strong> ${renderMarkdown(station.content || '')}</p>`;
            html += `<p><strong>視覺化:</strong> ${renderMarkdown(station.visualization || '')}</p>`;
            html += `<p><strong>記憶口訣:</strong> ${renderMarkdown(station.mnemonic || '')}</p>`;
            html += `</div></div>`;
        });
    }
    
    html += '</div>';
    return html;
}

// 格式化曼陀羅九宮格內容
function formatMandalaNineGridContent(result) {
    console.log('formatMandalaNineGridContent 處理:', result, typeof result);
    
    let html = '<div class="mandala-container">';
    
    // 中心主題
    if (result.central_theme) {
        html += `<h4 class="text-center mb-4"><i class="fas fa-bullseye me-2 text-primary"></i>${result.central_theme}</h4>`;
    }
    
    // 九宮格佈局
    if (result.grid_layout) {
        html += '<h6><i class="fas fa-th me-2 text-info"></i>九宮格佈局</h6>';
        html += '<div class="mandala-grid-container mb-4">';
        html += '<div class="row text-center">';
        
        const gridOrder = [
            'top_left', 'top_center', 'top_right',
            'middle_left', 'center', 'middle_right', 
            'bottom_left', 'bottom_center', 'bottom_right'
        ];
        
        gridOrder.forEach((position, index) => {
            const content = result.grid_layout[position] || '';
            const isCenter = position === 'center';
            const cellClass = isCenter ? 'mandala-center-cell' : 'mandala-cell';
            
            if (index % 3 === 0 && index > 0) {
                html += '</div><div class="row text-center">';
            }
            
            html += '<div class="col-4 mb-2">';
            html += `<div class="${cellClass} p-3 border ${isCenter ? 'bg-primary text-white' : 'bg-light'}" style="min-height: 80px; display: flex; align-items: center; justify-content: center;">`;
            html += `<div class="cell-content"><strong>${content}</strong></div>`;
            html += '</div></div>';
        });
        
        html += '</div></div>';
    }
    
    // 詳細說明
    if (result.detailed_explanations) {
        html += '<h6><i class="fas fa-info-circle me-2 text-success"></i>詳細說明</h6>';
        html += '<div class="accordion" id="mandalaAccordion">';
        
        Object.entries(result.detailed_explanations).forEach(([key, explanation], index) => {
            const isCenter = key === 'center';
            const title = result.grid_layout?.[key] || key;
            
            html += `<div class="accordion-item">`;
            html += `<h2 class="accordion-header" id="heading${index}">`;
            html += `<button class="accordion-button ${index !== 0 ? 'collapsed' : ''}" type="button" data-bs-toggle="collapse" data-bs-target="#collapse${index}">`;
            html += `${isCenter ? '🎯' : '📍'} ${title}`;
            html += `</button></h2>`;
            html += `<div id="collapse${index}" class="accordion-collapse collapse ${index === 0 ? 'show' : ''}" data-bs-parent="#mandalaAccordion">`;
            html += `<div class="accordion-body">${renderMarkdown(explanation)}</div>`;
            html += `</div></div>`;
        });
        
        html += '</div>';
    }
    
    // 連結關係
    if (result.connections && Array.isArray(result.connections)) {
        html += '<h6><i class="fas fa-link me-2 text-warning"></i>連結關係</h6>';
        html += '<div class="alert alert-warning">';
        html += '<ul>';
        result.connections.forEach(connection => {
            const fromName = result.grid_layout?.[connection.from] || connection.from;
            const toName = result.grid_layout?.[connection.to] || connection.to;
            html += `<li><strong>${fromName}</strong> ↔ <strong>${toName}</strong>: ${renderMarkdown(connection.relation)}</li>`;
        });
        html += '</ul></div>';
    }
    
    // 思考過程
    if (result.thinking_process) {
        html += '<h6><i class="fas fa-brain me-2 text-secondary"></i>思考過程</h6>';
        html += `<div class="alert alert-secondary">${renderMarkdown(result.thinking_process)}</div>`;
    }
    
    // 實際應用
    if (result.practical_applications && Array.isArray(result.practical_applications)) {
        html += '<h6><i class="fas fa-tools me-2 text-dark"></i>實際應用</h6>';
        html += '<div class="alert alert-dark">';
        html += '<ul>';
        result.practical_applications.forEach(app => {
            html += `<li>${renderMarkdown(app)}</li>`;
        });
        html += '</ul></div>';
    }
    
    // 學習路徑
    if (result.learning_path) {
        html += '<h6><i class="fas fa-graduation-cap me-2 text-primary"></i>學習路徑</h6>';
        html += `<div class="alert alert-primary">${renderMarkdown(result.learning_path)}</div>`;
    }
    
    // 備用欄位 - 舊格式兼容
    if (result.title && !result.central_theme) {
        html += `<h4 class="text-center mb-4">${result.title}</h4>`;
    }
    
    if (result.grid && Array.isArray(result.grid) && !result.grid_layout) {
        html += '<div class="mandala-grid">';
        result.grid.forEach((cell, index) => {
            const position = index === 4 ? 'center-cell' : '';
            html += `<div class="mandala-cell ${position}">`;
            html += `<div class="cell-content">${renderMarkdown(cell)}</div>`;
            html += `</div>`;
        });
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

// 格式化通用內容
function formatGenericContent(result) {
    let html = '<div class="generic-content">';
    
    if (typeof result === 'string') {
        html += renderMarkdown(result);
    } else if (typeof result === 'object') {
        html += '<pre class="bg-light p-3">' + JSON.stringify(result, null, 2) + '</pre>';
    } else {
        html += '<div class="alert alert-warning">無法顯示內容</div>';
    }
    
    html += '</div>';
    return html;
}

// 生成後備內容
function generateFallbackContent(type, result) {
    let html = '<div class="alert alert-warning">';
    html += '<h6>顯示原始整理結果：</h6>';
    html += '<pre class="small bg-light p-2">' + JSON.stringify(result, null, 2) + '</pre>';
    html += '</div>';
    return html;
}

// 渲染 Markdown（簡化版本）
function renderMarkdown(text) {
    if (!text) return '';
    
    // 簡單的 Markdown 處理
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
}

// 處理格式化增強結果
function handleFormatEnhanceResult(result) {
    if (result.enhanced_content) {
        // 這裡可以更新原始內容
        console.log('格式化增強完成:', result);
    }
}

// 移除整理標籤頁
function removeOrganizationTab(type, name) {
    if (confirm(`確定要刪除「${name}」整理嗎？`)) {
        const tabId = `${type}-tab`;
        const contentId = `${type}-content`;
        
        const tab = document.getElementById(tabId);
        const content = document.getElementById(contentId);
        
        if (tab) tab.parentElement.remove();
        if (content) content.remove();
        
        // 如果有後端 API，也刪除保存的結果
        if (organizationAnalysisIds[type]) {
            fetch(`/notes/${currentNoteId}/organizations/${organizationAnalysisIds[type]}`, {
                method: 'DELETE'
            }).catch(error => {
                console.error('刪除分析結果失敗:', error);
            });
        }
        
        // 刪除對應的分析 ID
        delete organizationAnalysisIds[type];
        
        // 取消相關的正在進行請求
        const requestId = `organize_${type}`;
        if (currentRequests.has(requestId)) {
            currentRequests.get(requestId).abort();
            currentRequests.delete(requestId);
        }
        
        showAlert(`已刪除「${name}」整理`, 'info');
    }
}

// 顯示提示訊息
function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alert-container') || document.body;
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    alertContainer.appendChild(alertDiv);
    
    // 自動移除提示
    setTimeout(() => {
        if (alertDiv.parentElement) {
            alertDiv.remove();
        }
    }, 5000);
}

// 重新生成特定類型的整理
function regenerateOrganization(type, name) {
    if (confirm(`確定要重新生成「${name}」嗎？這將覆蓋現有的結果。`)) {
        const config = getOrganizationConfig(type);
        if (config) {
            organizeNote(type, config.name, config.icon);
        }
    }
}

// 其他輔助函數...

// AI 建議相關函數
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

// 確保全域可用的函數
window.showOrganizationSelector = showOrganizationSelector;
window.organizeNote = organizeNote;
window.removeOrganizationTab = removeOrganizationTab;
window.regenerateOrganization = regenerateOrganization;
window.refreshAISuggestions = refreshAISuggestions;
