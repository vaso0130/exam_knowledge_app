// note_detail.js - 筆記詳情頁面的 JavaScript 功能 (重構版本)

// 全域變數
let currentNoteId = null;
let loadingModal;
let organizationAnalysisIds = {};

// 頁面載入時初始化
document.addEventListener('DOMContentLoaded', function () {
    // 初始化 loading modal
    loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));
    
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
                        const tab = new bootstrap.Tab(triggerEl);
                        tab.show();
                    }
                }
            }
        });
    }
}

// 載入預先生成的結果
function loadPreGeneratedResults() {
    if (!currentNoteId) return;
    
    fetch(`/notes/${currentNoteId}/pre-generated-results`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.results) {
                data.results.forEach(result => {
                    if (result.analysis_type && result.analysis_type.startsWith('organization_')) {
                        const orgType = result.analysis_type.replace('organization_', '');
                        organizationAnalysisIds[orgType] = result.id;
                        
                        const orgConfig = getOrganizationConfig(orgType);
                        if (orgConfig) {
                            addOrganizationTab(orgType, orgConfig.name, orgConfig.icon, result.result);
                        }
                    }
                });
            }
        })
        .catch(error => {
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
        loadingModal.hide();

        console.log('AI整理回應數據:', data);

        if (data.raw_text) {
            console.error("API回傳的資料無法解析為JSON");
            showAlert(`解析 ${name} 回應資料失敗，請查看控制台獲取詳細信息`, 'danger');
            return;
        }

        if (data.success) {
            if (data.analysis_id) {
                organizationAnalysisIds[type] = data.analysis_id;
            }

            if (type === 'format_enhance') {
                handleFormatEnhanceResult(data.result);
                showAlert(`${name} 完成！原始內容已更新`, 'success');
            } else {
                addOrganizationTab(type, name, icon, data.result);
                showAlert(`${name} 整理完成！`, 'success');
            }
        } else {
            console.error('AI整理失敗:', data.error);
            showAlert(`${name} 整理失敗: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        loadingModal.hide();
        console.error('整理請求失敗:', error);
        showAlert(`${name} 整理失敗: ${error.message}`, 'danger');
    });
}

// 添加整理標籤頁
function addOrganizationTab(type, name, icon, result) {
    const contentTabs = document.getElementById('content-tabs');
    const contentTabsContent = document.getElementById('content-tabs-content');
    
    if (!contentTabs || !contentTabsContent) return;

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
    if (addButton && addButton.parentElement) {
        contentTabs.insertBefore(tabButton, addButton.parentElement);
    } else {
        contentTabs.appendChild(tabButton);
    }

    // 創建內容區域
    const tabContent = document.createElement('div');
    tabContent.className = 'tab-pane fade';
    tabContent.id = contentId;
    tabContent.innerHTML = formatOrganizationResult(type, result);
    
    contentTabsContent.appendChild(tabContent);

    // 切換到新標籤
    const newTab = new bootstrap.Tab(document.getElementById(tabId));
    newTab.show();
}

// 格式化整理結果
function formatOrganizationResult(type, result) {
    let html = '<div class="p-3">';

    try {
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
    let html = '';
    
    if (result.mindmap_code) {
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
    let html = '<div class="hierarchical-container">';
    
    if (result.title) {
        html += `<h4 class="text-center mb-4">${result.title}</h4>`;
    }
    
    if (result.main_points) {
        html += '<h5><i class="fas fa-list me-2 text-primary"></i>主要重點</h5>';
        html += '<div class="list-group mb-4">';
        
        if (Array.isArray(result.main_points)) {
            result.main_points.forEach(point => {
                html += `<div class="list-group-item">${renderMarkdown(point)}</div>`;
            });
        }
        
        html += '</div>';
    }
    
    if (result.sub_topics) {
        html += '<h5><i class="fas fa-sitemap me-2 text-success"></i>子主題</h5>';
        html += '<div class="row">';
        
        if (Array.isArray(result.sub_topics)) {
            result.sub_topics.forEach((subtopic, index) => {
                html += '<div class="col-md-6 mb-3">';
                html += '<div class="card">';
                html += '<div class="card-body">';
                
                if (typeof subtopic === 'string') {
                    html += `<h6 class="card-title">子主題 ${index + 1}</h6>`;
                    html += `<p class="card-text">${renderMarkdown(subtopic)}</p>`;
                } else if (subtopic.title) {
                    html += `<h6 class="card-title">${subtopic.title}</h6>`;
                    html += `<p class="card-text">${renderMarkdown(subtopic.content || '')}</p>`;
                }
                
                html += '</div></div></div>';
            });
        }
        
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

// 格式化費曼技巧內容
function formatFeynmanContent(result) {
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
        }
    }
    
    html += '</div>';
    return html;
}

// 格式化問答式學習內容
function formatQALearningContent(result) {
    let html = '<div class="qa-learning-container">';
    
    if (result.topic) {
        html += `<h4 class="text-center mb-4">${result.topic}</h4>`;
    }
    
    if (result.qa_pairs && Array.isArray(result.qa_pairs)) {
        html += '<h5><i class="fas fa-question-circle me-2 text-primary"></i>問答練習</h5>';
        
        result.qa_pairs.forEach((qa, index) => {
            html += `<div class="card mb-3">`;
            html += `<div class="card-header">`;
            html += `<h6 class="mb-0">問題 ${index + 1}</h6>`;
            html += `</div>`;
            html += `<div class="card-body">`;
            html += `<p><strong>Q:</strong> ${renderMarkdown(qa.question)}</p>`;
            html += `<p><strong>A:</strong> ${renderMarkdown(qa.answer)}</p>`;
            
            if (qa.explanation) {
                html += `<p><strong>說明:</strong> ${renderMarkdown(qa.explanation)}</p>`;
            }
            
            if (qa.key_points && Array.isArray(qa.key_points)) {
                html += '<p><strong>重點:</strong></p>';
                html += '<ul>';
                qa.key_points.forEach(point => {
                    html += `<li>${renderMarkdown(point)}</li>`;
                });
                html += '</ul>';
            }
            
            html += `</div></div>`;
        });
    }
    
    if (result.summary) {
        html += '<h6><i class="fas fa-summary me-2 text-info"></i>總結</h6>';
        html += `<div class="alert alert-info">${renderMarkdown(result.summary)}</div>`;
    }
    
    html += '</div>';
    return html;
}

// 格式化比較分析內容
function formatComparisonContent(result) {
    let html = '<div class="comparison-container">';
    
    if (result.comparison_table) {
        html += '<h6><i class="fas fa-balance-scale me-2 text-primary"></i>比較表格</h6>';
        html += '<div class="table-responsive">';
        html += '<table class="table table-bordered">';
        
        // 這裡需要根據實際的比較表格格式來處理
        if (typeof result.comparison_table === 'string') {
            html += `<tbody><tr><td>${renderMarkdown(result.comparison_table)}</td></tr></tbody>`;
        }
        
        html += '</table>';
        html += '</div>';
    }
    
    if (result.analysis) {
        html += '<h6><i class="fas fa-analysis me-2 text-info"></i>分析結果</h6>';
        html += `<div class="alert alert-info">${renderMarkdown(result.analysis)}</div>`;
    }
    
    html += '</div>';
    return html;
}

// 格式化記憶宮殿內容
function formatMemoryPalaceContent(result) {
    let html = '<div class="memory-palace-container">';
    
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
    let html = '<div class="mandala-container">';
    
    if (result.title) {
        html += `<h4 class="text-center mb-4">${result.title}</h4>`;
    }
    
    if (result.grid && Array.isArray(result.grid)) {
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
        
        // 刪除對應的分析 ID
        delete organizationAnalysisIds[type];
        
        // 如果有後端 API，也刪除保存的結果
        if (organizationAnalysisIds[type]) {
            fetch(`/notes/${currentNoteId}/organizations/${organizationAnalysisIds[type]}`, {
                method: 'DELETE'
            }).catch(error => {
                console.error('刪除分析結果失敗:', error);
            });
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

// 確保全域可用的函數
window.showOrganizationSelector = showOrganizationSelector;
window.organizeNote = organizeNote;
window.removeOrganizationTab = removeOrganizationTab;
window.regenerateOrganization = regenerateOrganization;
