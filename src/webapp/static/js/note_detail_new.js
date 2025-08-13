/**
 * 筆記詳情頁面JavaScript - 重構版本
 * 處理AI整理、測驗生成、內容管理等功能
 */

// 全域變數
let currentNoteId = '';
let organizationAnalysisIds = {};

// 初始化函數
document.addEventListener('DOMContentLoaded', function() {
    // 從URL獲取筆記ID
    const pathParts = window.location.pathname.split('/');
    currentNoteId = pathParts[pathParts.length - 1];
    
    console.log('筆記詳情頁面初始化, 筆記ID:', currentNoteId);
    
    // 初始化各種功能
    initializeEventListeners();
    loadPreGeneratedResults();
});

/**
 * 初始化事件監聽器
 */
function initializeEventListeners() {
    // AI整理按鈕
    const organizeBtn = document.getElementById('organize-note-btn');
    if (organizeBtn) {
        organizeBtn.addEventListener('click', showOrganizationSelector);
    }
    
    // 測驗生成按鈕
    const quizBtn = document.getElementById('generate-quiz-btn');
    if (quizBtn) {
        quizBtn.addEventListener('click', generateInteractiveQuiz);
    }
    
    // 模擬題生成按鈕
    const mockBtn = document.getElementById('generate-mock-btn');
    if (mockBtn) {
        mockBtn.addEventListener('click', generateMockQuestions);
    }
}

/**
 * 顯示AI整理選擇器
 */
function showOrganizationSelector() {
    const organizationTypes = [
        { type: 'mindmap', name: '心智圖', icon: 'fas fa-project-diagram' },
        { type: 'hierarchical', name: '階層整理', icon: 'fas fa-sitemap' },
        { type: 'feynman', name: '費曼技巧', icon: 'fas fa-user-graduate' },
        { type: 'qa_learning', name: '問答式學習', icon: 'fas fa-question-circle' },
        { type: 'comparison', name: '比較分析', icon: 'fas fa-balance-scale' },
        { type: 'memory_palace', name: '記憶宮殿', icon: 'fas fa-building' },
        { type: 'mandala_ninegrid', name: '曼陀羅九宮格', icon: 'fas fa-th' },
        { type: 'format_enhance', name: '格式增強', icon: 'fas fa-magic' }
    ];

    let modalHtml = `
        <div class="modal fade" id="organizationModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-robot me-2 text-primary"></i>選擇AI整理方式
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row g-3">
    `;

    organizationTypes.forEach(({ type, name, icon }) => {
        modalHtml += `
            <div class="col-md-6">
                <div class="card h-100 organization-card" style="cursor: pointer;" 
                     onclick="organizeNote('${type}', '${name}', '${icon}')">
                    <div class="card-body text-center">
                        <i class="${icon} fa-2x mb-3 text-primary"></i>
                        <h6 class="card-title">${name}</h6>
                        <p class="card-text small text-muted">
                            ${getOrganizationDescription(type)}
                        </p>
                    </div>
                </div>
            </div>
        `;
    });

    modalHtml += `
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // 移除現有的modal（如果存在）
    const existingModal = document.getElementById('organizationModal');
    if (existingModal) {
        existingModal.remove();
    }

    // 添加新modal到頁面
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // 顯示modal
    const modal = new bootstrap.Modal(document.getElementById('organizationModal'));
    modal.show();

    // 清理事件：modal關閉時移除元素
    document.getElementById('organizationModal').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
}

/**
 * 獲取整理方式描述
 */
function getOrganizationDescription(type) {
    const descriptions = {
        'mindmap': '將內容轉換為視覺化心智圖結構',
        'hierarchical': '按照邏輯層次重新組織內容',
        'feynman': '用簡單語言解釋複雜概念',
        'qa_learning': '轉換為問答式學習格式',
        'comparison': '分析比較不同概念或方法',
        'memory_palace': '創建記憶宮殿助記系統',
        'mandala_ninegrid': '使用曼陀羅九宮格思維法',
        'format_enhance': '優化格式並增強內容'
    };
    return descriptions[type] || '智能整理內容';
}

/**
 * 執行AI整理
 */
function organizeNote(type, name, icon) {
    // 關閉modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('organizationModal'));
    if (modal) {
        modal.hide();
    }

    // 顯示載入動畫
    const loadingModal = showLoadingModal(`正在使用${name}整理筆記...`);

    // 發送請求到後端
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
        hideLoadingModal(loadingModal);

        console.log('AI整理回應數據:', data);

        if (data.raw_text) {
            console.error("API回傳的資料無法解析為JSON:", data.raw_text);
            showAlert('整理結果格式異常，請稍後重試', 'danger');
            return;
        }

        if (data.success) {
            // 儲存analysis_id
            if (data.analysis_id) {
                organizationAnalysisIds[type] = data.analysis_id;
            }

            // 處理不同類型的結果
            if (type === 'format_enhance') {
                handleFormatEnhanceResult(data.result);
                showAlert(`${name} 完成！原始內容已更新`, 'success');
            } else {
                addOrganizationTab(type, name, icon, data.result);
                showAlert(`${name} 整理完成！`, 'success');
            }
        } else {
            throw new Error(data.error || '整理失敗');
        }
    })
    .catch(error => {
        hideLoadingModal(loadingModal);
        console.error('AI整理錯誤:', error);
        showAlert(`${name} 整理失敗: ${error.message}`, 'danger');
    });
}

/**
 * 添加整理結果標籤頁
 */
function addOrganizationTab(type, name, icon, result) {
    const tabContainer = document.getElementById('organization-tabs');
    const contentContainer = document.getElementById('organization-content');

    if (!tabContainer || !contentContainer) {
        console.error('找不到標籤頁容器');
        return;
    }

    // 創建標籤頁
    const tabId = `tab-${type}`;
    const contentId = `content-${type}`;

    // 檢查是否已存在該類型的標籤頁
    const existingTab = document.getElementById(tabId);
    if (existingTab) {
        // 更新現有內容
        const existingContent = document.getElementById(contentId);
        if (existingContent) {
            existingContent.innerHTML = formatOrganizationResult(type, result);
        }
        // 切換到該標籤頁
        const tab = new bootstrap.Tab(existingTab);
        tab.show();
        return;
    }

    // 創建新標籤頁
    const tabHtml = `
        <li class="nav-item" role="presentation">
            <button class="nav-link" id="${tabId}" data-bs-toggle="tab" 
                    data-bs-target="#${contentId}" type="button" role="tab">
                <i class="${icon} me-2"></i>${name}
                <button class="btn btn-sm btn-outline-secondary ms-2" 
                        onclick="regenerateOrganization('${type}', '${name}')" 
                        title="重新生成">
                    <i class="fas fa-redo"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger ms-1" 
                        onclick="removeOrganizationTab('${type}')" 
                        title="刪除">
                    <i class="fas fa-times"></i>
                </button>
            </button>
        </li>
    `;

    const contentHtml = `
        <div class="tab-pane fade" id="${contentId}" role="tabpanel" aria-labelledby="${tabId}">
            ${formatOrganizationResult(type, result)}
        </div>
    `;

    // 添加到DOM
    tabContainer.insertAdjacentHTML('beforeend', tabHtml);
    contentContainer.insertAdjacentHTML('beforeend', contentHtml);

    // 自動切換到新標籤頁
    const newTab = new bootstrap.Tab(document.getElementById(tabId));
    newTab.show();
}

/**
 * 格式化整理結果
 */
function formatOrganizationResult(type, result) {
    if (!result || typeof result !== 'object') {
        return '<div class="alert alert-warning">無法顯示整理結果</div>';
    }

    try {
        switch (type) {
            case 'mindmap':
                return formatMindmapContent(result);
            case 'hierarchical':
                return formatHierarchicalContent(result);
            case 'feynman':
                return formatFeynmanContent(result);
            case 'qa_learning':
                return formatQALearningContent(result);
            case 'comparison':
                return formatComparisonContent(result);
            case 'memory_palace':
                return formatMemoryPalaceContent(result);
            case 'mandala_ninegrid':
                return formatMandalaNinegridContent(result);
            default:
                return formatGenericContent(result);
        }
    } catch (error) {
        console.error(`格式化${type}結果時出錯:`, error);
        return `<div class="alert alert-danger">格式化結果時出錯: ${error.message}</div>`;
    }
}

/**
 * 格式化心智圖內容
 */
function formatMindmapContent(result) {
    let html = '<div class="mindmap-container">';
    
    if (result.mindmap_code) {
        html += `
            <div class="mindmap-display-container mb-4">
                <h6><i class="fas fa-project-diagram me-2 text-primary"></i>心智圖</h6>
                <div class="mermaid-container border rounded p-3" style="text-align: center;">
                    <pre class="mermaid">${result.mindmap_code}</pre>
                </div>
            </div>
        `;
    }
    
    if (result.question_summary) {
        html += `
            <div class="question-summary mb-3">
                <h6><i class="fas fa-lightbulb me-2 text-warning"></i>核心概念</h6>
                <div class="alert alert-light">
                    <strong>摘要：</strong>${result.question_summary.summary}<br>
                    <strong>解題技巧：</strong>${result.question_summary.solving_tips}
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

/**
 * 格式化階層內容
 */
function formatHierarchicalContent(result) {
    let html = '<div class="hierarchical-container">';
    
    if (result.title) {
        html += `<h4 class="text-center mb-4">${result.title}</h4>`;
    }
    
    if (result.main_points && Array.isArray(result.main_points)) {
        html += '<h5><i class="fas fa-list me-2"></i>主要重點</h5>';
        html += '<ul class="list-group mb-4">';
        result.main_points.forEach(point => {
            html += `<li class="list-group-item">${renderMarkdown(point)}</li>`;
        });
        html += '</ul>';
    }
    
    if (result.sub_topics && Array.isArray(result.sub_topics)) {
        html += '<h5><i class="fas fa-sitemap me-2"></i>子主題</h5>';
        html += '<div class="row">';
        result.sub_topics.forEach((topic, index) => {
            html += `
                <div class="col-md-6 mb-3">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">子主題 ${index + 1}</h6>
                            <p class="card-text">${renderMarkdown(topic)}</p>
                        </div>
                    </div>
                </div>
            `;
        });
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

/**
 * 格式化費曼技巧內容
 */
function formatFeynmanContent(result) {
    let html = '<div class="feynman-container">';
    
    if (result.simple_explanation) {
        html += `
            <h6><i class="fas fa-lightbulb me-2 text-warning"></i>簡單解釋</h6>
            <div class="alert alert-light border-start border-4 border-warning p-3 mb-3">
                ${renderMarkdown(result.simple_explanation)}
            </div>
        `;
    }
    
    if (result.analogies && Array.isArray(result.analogies)) {
        html += '<h6><i class="fas fa-lightbulb me-2 text-info"></i>類比說明</h6>';
        html += '<div class="mb-3">';
        result.analogies.forEach(analogy => {
            html += `<div class="alert alert-info">${renderMarkdown(analogy)}</div>`;
        });
        html += '</div>';
    }
    
    if (result.examples && Array.isArray(result.examples)) {
        html += '<h6><i class="fas fa-examples me-2 text-success"></i>實例說明</h6>';
        html += '<div class="mb-3">';
        result.examples.forEach(example => {
            html += `<div class="alert alert-success">${renderMarkdown(example)}</div>`;
        });
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

/**
 * 格式化問答式學習內容
 */
function formatQALearningContent(result) {
    let html = '<div class="qa-learning-container">';
    
    if (result.topic) {
        html += `<h4 class="text-center mb-4">${result.topic}</h4>`;
    }
    
    if (result.qa_pairs && Array.isArray(result.qa_pairs)) {
        html += '<div class="qa-pairs-container">';
        result.qa_pairs.forEach((pair, index) => {
            html += `
                <div class="card mb-3">
                    <div class="card-header">
                        <h6 class="mb-0">
                            <i class="fas fa-question-circle me-2 text-primary"></i>
                            問題 ${index + 1}
                        </h6>
                    </div>
                    <div class="card-body">
                        <p class="fw-bold">${pair.question}</p>
                        <div class="alert alert-light">
                            <strong>答案：</strong>${renderMarkdown(pair.answer)}
                        </div>
                        ${pair.explanation ? `
                            <div class="alert alert-info">
                                <strong>詳細解釋：</strong>${renderMarkdown(pair.explanation)}
                            </div>
                        ` : ''}
                        ${pair.key_points && Array.isArray(pair.key_points) ? `
                            <div class="mt-2">
                                <strong>重點：</strong>
                                <ul class="mb-0">
                                    ${pair.key_points.map(point => `<li>${point}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        });
        html += '</div>';
    }
    
    if (result.summary) {
        html += `
            <div class="summary-section mt-4">
                <h6><i class="fas fa-clipboard-list me-2"></i>總結</h6>
                <div class="alert alert-secondary">${renderMarkdown(result.summary)}</div>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

/**
 * 格式化比較分析內容
 */
function formatComparisonContent(result) {
    let html = '<div class="comparison-container">';
    
    // 基本的比較結果顯示
    if (result && typeof result === 'object') {
        html += '<div class="alert alert-info">';
        html += '<h6>比較分析結果：</h6>';
        html += '<pre class="small bg-light p-2">' + JSON.stringify(result, null, 2) + '</pre>';
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

/**
 * 格式化記憶宮殿內容
 */
function formatMemoryPalaceContent(result) {
    let html = '<div class="memory-palace-container">';
    
    if (result.location) {
        html += `
            <div class="location-section mb-4">
                <h6><i class="fas fa-building me-2 text-primary"></i>記憶地點</h6>
                <div class="alert alert-light">${result.location}</div>
            </div>
        `;
    }
    
    if (result.route) {
        html += `
            <div class="route-section mb-4">
                <h6><i class="fas fa-route me-2 text-info"></i>行進路線</h6>
                <div class="alert alert-info">${result.route}</div>
            </div>
        `;
    }
    
    if (result.memory_stations && Array.isArray(result.memory_stations)) {
        html += '<h6><i class="fas fa-map-marker-alt me-2 text-danger"></i>記憶站點</h6>';
        html += '<div class="memory-stations">';
        result.memory_stations.forEach((station, index) => {
            html += `
                <div class="card mb-3">
                    <div class="card-header">
                        <strong>站點 ${index + 1}: ${station.position}</strong>
                    </div>
                    <div class="card-body">
                        <p><strong>內容：</strong>${station.content}</p>
                        <p><strong>視覺化：</strong>${station.visualization}</p>
                        ${station.mnemonic ? `<p><strong>記憶口訣：</strong>${station.mnemonic}</p>` : ''}
                    </div>
                </div>
            `;
        });
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

/**
 * 格式化曼陀羅九宮格內容
 */
function formatMandalaNinegridContent(result) {
    let html = '<div class="mandala-container">';
    
    // 基本的九宮格結果顯示
    if (result && typeof result === 'object') {
        html += '<div class="alert alert-info">';
        html += '<h6>曼陀羅九宮格結果：</h6>';
        html += '<pre class="small bg-light p-2">' + JSON.stringify(result, null, 2) + '</pre>';
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

/**
 * 格式化通用內容
 */
function formatGenericContent(result) {
    let html = '<div class="generic-content">';
    
    if (result && typeof result === 'object') {
        html += '<div class="alert alert-info">';
        html += '<h6>整理結果：</h6>';
        html += '<pre class="small bg-light p-2">' + JSON.stringify(result, null, 2) + '</pre>';
        html += '</div>';
    } else {
        html += '<div class="alert alert-warning">無法顯示整理結果</div>';
    }
    
    html += '</div>';
    return html;
}

/**
 * 處理格式增強結果
 */
function handleFormatEnhanceResult(result) {
    if (result && result.enhanced_content) {
        // 更新頁面上的內容
        const contentElement = document.querySelector('.note-content');
        if (contentElement) {
            contentElement.innerHTML = renderMarkdown(result.enhanced_content);
        }
    }
}

/**
 * 渲染Markdown內容
 */
function renderMarkdown(content) {
    if (!content) return '';
    
    // 簡單的Markdown渲染，可以根據需要擴展
    return content
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');
}

/**
 * 重新生成整理結果
 */
function regenerateOrganization(type, name) {
    if (confirm(`確定要重新生成「${name}」嗎？這將覆蓋現有的結果。`)) {
        // 找到對應的icon
        const orgTypes = {
            'mindmap': 'fas fa-project-diagram',
            'hierarchical': 'fas fa-sitemap',
            'feynman': 'fas fa-user-graduate',
            'qa_learning': 'fas fa-question-circle',
            'comparison': 'fas fa-balance-scale',
            'memory_palace': 'fas fa-building',
            'mandala_ninegrid': 'fas fa-th',
            'format_enhance': 'fas fa-magic'
        };
        
        organizeNote(type, name, orgTypes[type] || 'fas fa-cog');
    }
}

/**
 * 移除整理結果標籤頁
 */
function removeOrganizationTab(type) {
    const tabId = `tab-${type}`;
    const contentId = `content-${type}`;
    
    const tab = document.getElementById(tabId);
    const content = document.getElementById(contentId);
    
    if (tab) tab.closest('li').remove();
    if (content) content.remove();
    
    // 刪除保存的analysis_id
    delete organizationAnalysisIds[type];
}

/**
 * 生成互動式測驗
 */
function generateInteractiveQuiz() {
    const loadingModal = showLoadingModal('正在生成互動式測驗...');
    
    fetch(`/notes/${currentNoteId}/quiz`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        hideLoadingModal(loadingModal);
        
        if (data.success) {
            displayQuizResults(data.quiz);
            showAlert('互動式測驗生成完成！', 'success');
        } else {
            throw new Error(data.error || '測驗生成失敗');
        }
    })
    .catch(error => {
        hideLoadingModal(loadingModal);
        console.error('測驗生成錯誤:', error);
        showAlert(`測驗生成失敗: ${error.message}`, 'danger');
    });
}

/**
 * 顯示測驗結果
 */
function displayQuizResults(quiz) {
    // 實現測驗顯示邏輯
    console.log('顯示測驗結果:', quiz);
}

/**
 * 生成模擬題
 */
function generateMockQuestions() {
    const loadingModal = showLoadingModal('正在生成模擬題...');
    
    fetch(`/notes/${currentNoteId}/generate-mock-questions`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        hideLoadingModal(loadingModal);
        
        if (data.success) {
            displayMockQuestions(data.questions);
            showAlert('模擬題生成完成！', 'success');
        } else {
            throw new Error(data.error || '模擬題生成失敗');
        }
    })
    .catch(error => {
        hideLoadingModal(loadingModal);
        console.error('模擬題生成錯誤:', error);
        showAlert(`模擬題生成失敗: ${error.message}`, 'danger');
    });
}

/**
 * 顯示模擬題
 */
function displayMockQuestions(questions) {
    // 實現模擬題顯示邏輯
    console.log('顯示模擬題:', questions);
}

/**
 * 載入預生成的結果
 */
function loadPreGeneratedResults() {
    fetch(`/notes/${currentNoteId}/pre-generated-results`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.results) {
                // 載入現有的整理結果
                Object.keys(data.results).forEach(type => {
                    const result = data.results[type];
                    if (result.analysis_id) {
                        organizationAnalysisIds[type] = result.analysis_id;
                    }
                    // 可以選擇性地顯示預生成的結果
                });
            }
        })
        .catch(error => {
            console.error('載入預生成結果錯誤:', error);
        });
}

/**
 * 顯示載入動畫
 */
function showLoadingModal(message) {
    const modalHtml = `
        <div class="modal fade" id="loadingModal" tabindex="-1" data-bs-backdrop="static">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-body text-center p-4">
                        <div class="spinner-border text-primary mb-3" role="status">
                            <span class="visually-hidden">載入中...</span>
                        </div>
                        <h6>${message}</h6>
                        <p class="text-muted small mb-0">請稍候，AI正在處理中...</p>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = new bootstrap.Modal(document.getElementById('loadingModal'));
    modal.show();
    
    return modal;
}

/**
 * 隱藏載入動畫
 */
function hideLoadingModal(modal) {
    if (modal) {
        modal.hide();
        setTimeout(() => {
            const modalElement = document.getElementById('loadingModal');
            if (modalElement) {
                modalElement.remove();
            }
        }, 300);
    }
}

/**
 * 顯示提示訊息
 */
function showAlert(message, type = 'info') {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show position-fixed" 
             style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', alertHtml);
    
    // 3秒後自動消失
    setTimeout(() => {
        const alert = document.querySelector('.alert:last-of-type');
        if (alert && alert.classList.contains('show')) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }
    }, 3000);
}

// 匯出函數供全域使用
window.showOrganizationSelector = showOrganizationSelector;
window.organizeNote = organizeNote;
window.regenerateOrganization = regenerateOrganization;
window.removeOrganizationTab = removeOrganizationTab;
window.generateInteractiveQuiz = generateInteractiveQuiz;
window.generateMockQuestions = generateMockQuestions;
