/* AI 增強表單功能的 JavaScript 支援 */

// AI 建議應用函數
function applySuggestion(fieldName, suggestion) {
    const field = document.querySelector(`[name="${fieldName}"]`);
    if (field) {
        if (field.tagName.toLowerCase() === 'textarea') {
            // 對於文字區域，在游標位置插入建議
            const cursorPos = field.selectionStart;
            const textBefore = field.value.substring(0, cursorPos);
            const textAfter = field.value.substring(cursorPos);
            field.value = textBefore + suggestion + textAfter;
            field.selectionStart = field.selectionEnd = cursorPos + suggestion.length;
        } else {
            // 對於普通輸入欄位，替換或追加內容
            field.value = field.value ? field.value + ' ' + suggestion : suggestion;
        }
        field.focus();
        
        // 觸發輸入事件以更新任何綁定的預覽
        field.dispatchEvent(new Event('input', { bubbles: true }));
    }
}

// 標籤相關功能
let currentTags = [];

function addSuggestedTag(tag) {
    if (!currentTags.includes(tag)) {
        currentTags.push(tag);
        updateTagsDisplay();
        updateTagsInput();
    }
}

function removeTag(tag) {
    const index = currentTags.indexOf(tag);
    if (index > -1) {
        currentTags.splice(index, 1);
        updateTagsDisplay();
        updateTagsInput();
    }
}

function updateTagsDisplay() {
    const display = document.querySelector('.tags-display');
    if (display) {
        display.innerHTML = currentTags.map(tag => 
            `<span class="badge bg-primary me-1">
                ${tag} 
                <i class="fas fa-times ms-1" onclick="removeTag('${tag}')" style="cursor: pointer;"></i>
            </span>`
        ).join('');
    }
}

function updateTagsInput() {
    const input = document.querySelector('.tags-input');
    if (input) {
        input.value = currentTags.join(', ');
    }
}

// 初始化標籤輸入功能
function initializeTagsInput() {
    const tagsInput = document.querySelector('.tags-input');
    if (tagsInput) {
        // 載入現有標籤
        if (tagsInput.value) {
            currentTags = tagsInput.value.split(',').map(tag => tag.trim()).filter(tag => tag);
            updateTagsDisplay();
        }
        
        tagsInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const newTag = this.value.trim();
                if (newTag && !currentTags.includes(newTag)) {
                    currentTags.push(newTag);
                    updateTagsDisplay();
                    updateTagsInput();
                    this.value = '';
                }
            }
        });
    }
}

// AI 內容分析功能
async function performAIAnalysis(contentFieldId) {
    const contentField = document.getElementById(contentFieldId);
    const resultsContainer = document.querySelector('.ai-analysis-results');
    
    if (!contentField || !contentField.value.trim()) {
        alert('請先輸入內容再進行分析');
        return;
    }
    
    try {
        // 顯示載入狀態
        resultsContainer.classList.remove('d-none');
        resultsContainer.innerHTML = `
            <div class="card">
                <div class="card-body text-center">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">分析中...</span>
                    </div>
                    <p class="mt-2">AI 正在分析內容...</p>
                </div>
            </div>
        `;
        
        // 發送 AJAX 請求到後端進行 AI 分析
        const response = await fetch('/api/ai-analysis', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                content: contentField.value
            })
        });
        
        if (response.ok) {
            const analysis = await response.json();
            displayAnalysisResults(analysis);
        } else {
            throw new Error('分析請求失敗');
        }
    } catch (error) {
        console.error('AI 分析錯誤:', error);
        resultsContainer.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <div class="alert alert-danger">
                        分析失敗，請稍後再試
                    </div>
                </div>
            </div>
        `;
    }
}

function displayAnalysisResults(analysis) {
    const resultsContainer = document.querySelector('.ai-analysis-results');
    
    let keywordsHtml = '';
    if (analysis.keywords && analysis.keywords.length > 0) {
        keywordsHtml = `
            <div class="analysis-keywords mt-2">
                <strong>關鍵字：</strong>
                ${analysis.keywords.map(keyword => 
                    `<span class="badge bg-success me-1" onclick="applySuggestion('tags', '${keyword}')">${keyword}</span>`
                ).join('')}
            </div>
        `;
    }
    
    let categoriesHtml = '';
    if (analysis.categories && analysis.categories.length > 0) {
        categoriesHtml = `
            <div class="analysis-categories mt-2">
                <strong>建議分類：</strong>
                ${analysis.categories.map(category => 
                    `<span class="badge bg-info me-1">${category}</span>`
                ).join('')}
            </div>
        `;
    }
    
    resultsContainer.innerHTML = `
        <div class="card">
            <div class="card-body">
                <h6><i class="fas fa-brain"></i> 分析結果：</h6>
                <div class="analysis-summary">
                    <strong>摘要：</strong>
                    <p class="text-muted">${analysis.summary || '無法生成摘要'}</p>
                </div>
                ${keywordsHtml}
                ${categoriesHtml}
            </div>
        </div>
    `;
}

// AI 增強按鈕功能
function initializeAIEnhancement() {
    document.querySelectorAll('.ai-enhance-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const container = this.closest('.ai-enhanced-field');
            const input = container.querySelector('.ai-input, .ai-textarea');
            
            if (input && input.value.trim()) {
                enhanceContentWithAI(input);
            } else {
                alert('請先輸入內容再使用 AI 增強功能');
            }
        });
    });
}

async function enhanceContentWithAI(inputElement) {
    const originalContent = inputElement.value;
    
    try {
        // 顯示載入狀態
        inputElement.disabled = true;
        const enhanceBtn = inputElement.parentElement.querySelector('.ai-enhance-btn');
        const originalBtnText = enhanceBtn.innerHTML;
        enhanceBtn.innerHTML = '<i class="spinner-border spinner-border-sm"></i> 增強中...';
        
        const response = await fetch('/api/ai-enhance', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                content: originalContent,
                type: inputElement.tagName.toLowerCase() === 'textarea' ? 'long_text' : 'short_text'
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            inputElement.value = result.enhanced_content;
            
            // 觸發輸入事件以更新預覽
            inputElement.dispatchEvent(new Event('input', { bubbles: true }));
        } else {
            throw new Error('增強請求失敗');
        }
    } catch (error) {
        console.error('AI 增強錯誤:', error);
        alert('AI 增強功能暫時無法使用，請稍後再試');
    } finally {
        // 恢復原狀態
        inputElement.disabled = false;
        const enhanceBtn = inputElement.parentElement.querySelector('.ai-enhance-btn');
        enhanceBtn.innerHTML = '<i class="fas fa-magic"></i> AI 增強';
    }
}

// 頁面載入完成後初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeTagsInput();
    initializeAIEnhancement();
});
