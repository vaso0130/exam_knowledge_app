/**
 * 全新WYSIWYG筆記編輯器
 * 功能特色：
 * 1. WYSIWYG富文本編輯
 * 2. 直接複製貼上圖片支援
 * 3. 手寫筆輸入與AI格式化
 * 4. 整合LSP與Ghost AI功能
 * 5. 現代化UI設計
 */

class WYSIWYGEditor {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.options = {
            theme: 'light',
            placeholder: '開始寫下您的筆記...',
            autoSave: true,
            enableHandwriting: true,
            enableLSP: true,
            enableGhost: true,
            ...options
        };
        
        // 編輯器狀態
        this.content = '';
        this.isReady = false;
        this.editor = null;
        this.toolbar = null;
        this.statusBar = null;
        
        // LSP 和 Ghost 狀態
        this.lspSocket = null;
        this.lspEnabled = this.options.enableLSP;
        this.ghostEnabled = this.options.enableGhost;
        this.ghostDecorations = [];
        
        // 手寫相關
        this.handwritingCanvas = null;
        this.handwritingContext = null;
        this.isDrawing = false;
        
        // 事件處理器
        this.eventHandlers = new Map();
        
        this.init();
    }
    
    /**
     * 初始化編輯器
     */
    async init() {
        try {
            this.createEditorStructure();
            this.setupToolbar();
            this.initEditor();
            this.setupEventHandlers();
            this.setupImagePasting();
            this.setupHandwriting();
            this.setupAIFeatures();
            
            if (this.lspEnabled) {
                await this.initLSP();
            }
            
            if (this.ghostEnabled) {
                this.initGhost();
            }
            
            this.isReady = true;
            this.emit('ready');
        } catch (error) {
            console.error('編輯器初始化失敗:', error);
            this.emit('error', error);
        }
    }
    
    /**
     * 創建編輯器DOM結構
     */
    createEditorStructure() {
        // 檢查手寫Modal是否已經存在，如果不存在才創建
        let modalHTML = '';
        if (!document.getElementById('handwritingModal')) {
            modalHTML = `
            <!-- 手寫輸入模態框 -->
            <div class="modal fade" id="handwritingModal" tabindex="-1">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-pen-fancy me-2"></i>手寫輸入
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="handwriting-container">
                                <canvas class="handwriting-canvas" 
                                        width="1024" height="768"
                                        style="max-width: 100%; height: auto; border: 2px solid #dee2e6; border-radius: 8px; background: white;">
                                </canvas>
                                <div class="handwriting-controls mt-3">
                                    <div class="btn-group" role="group">
                                        <button type="button" class="btn btn-outline-primary active" 
                                                data-tool="pen">
                                            <i class="fas fa-pen me-1"></i>筆刷
                                        </button>
                                        <button type="button" class="btn btn-outline-secondary" 
                                                data-tool="eraser">
                                            <i class="fas fa-eraser me-1"></i>橡皮擦
                                        </button>
                                    </div>
                                    <div class="btn-group ms-3" role="group">
                                        <button type="button" class="btn btn-outline-danger" 
                                                data-action="clear">
                                            <i class="fas fa-trash me-1"></i>清除
                                        </button>
                                    </div>
                                    <div class="ms-auto">
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input" type="radio" 
                                                   name="handwritingMode" id="modeImage" value="image" checked>
                                            <label class="form-check-label" for="modeImage">
                                                插入為圖片
                                            </label>
                                        </div>
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input" type="radio" 
                                                   name="handwritingMode" id="modeText" value="text">
                                            <label class="form-check-label" for="modeText">
                                                AI轉換為文字
                                            </label>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                <i class="fas fa-times me-1"></i>取消
                            </button>
                            <button type="button" class="btn btn-primary" id="insertHandwriting">
                                <i class="fas fa-check me-1"></i>插入
                            </button>
                        </div>
                    </div>
                </div>
            </div>`;
        }
        
        this.container.innerHTML = `
            <div class="wysiwyg-editor" data-theme="${this.options.theme}">
                <!-- 工具列 -->
                <div class="editor-toolbar">
                    <!-- 格式化按鈕 -->
                    <button class="toolbar-btn" data-command="bold" title="粗體 (Ctrl+B)">
                        <i class="fas fa-bold"></i>
                    </button>
                    <button class="toolbar-btn" data-command="italic" title="斜體 (Ctrl+I)">
                        <i class="fas fa-italic"></i>
                    </button>
                    <button class="toolbar-btn" data-command="underline" title="底線 (Ctrl+U)">
                        <i class="fas fa-underline"></i>
                    </button>
                    <button class="toolbar-btn" data-command="strikethrough" title="刪除線">
                        <i class="fas fa-strikethrough"></i>
                    </button>
                    <div class="toolbar-separator"></div>
                    <!-- 字體顏色 -->
                    <button class="toolbar-btn" data-command="foreColor" title="文字顏色">
                        <i class="fas fa-palette"></i>
                    </button>
                    <button class="toolbar-btn" data-command="backColor" title="背景顏色">
                        <i class="fas fa-fill-drip"></i>
                    </button>
                    <div class="toolbar-separator"></div>
                    <!-- 標題 -->
                    <select class="toolbar-select" data-command="heading">
                        <option value="">一般文字</option>
                        <option value="h1">標題 1</option>
                        <option value="h2">標題 2</option>
                        <option value="h3">標題 3</option>
                        <option value="h4">標題 4</option>
                        <option value="h5">標題 5</option>
                        <option value="h6">標題 6</option>
                    </select>
                    <div class="toolbar-separator"></div>
                    <!-- 清單 -->
                    <button class="toolbar-btn" data-command="insertUnorderedList" title="無序清單">
                        <i class="fas fa-list-ul"></i>
                    </button>
                    <button class="toolbar-btn" data-command="insertOrderedList" title="有序清單">
                        <i class="fas fa-list-ol"></i>
                    </button>
                    <button class="toolbar-btn" data-command="indent" title="增加縮排">
                        <i class="fas fa-indent"></i>
                    </button>
                    <button class="toolbar-btn" data-command="outdent" title="減少縮排">
                        <i class="fas fa-outdent"></i>
                    </button>
                    <div class="toolbar-separator"></div>
                    <!-- 插入 -->
                    <button class="toolbar-btn" data-command="insertImage" title="插入圖片">
                        <i class="fas fa-image"></i>
                    </button>
                    <button class="toolbar-btn" data-command="createLink" title="插入連結">
                        <i class="fas fa-link"></i>
                    </button>
                    <button class="toolbar-btn" data-command="insertTable" title="插入表格">
                        <i class="fas fa-table"></i>
                    </button>
                    <button class="toolbar-btn" data-command="insertCode" title="插入程式碼">
                        <i class="fas fa-code"></i>
                    </button>
                    <div class="toolbar-separator"></div>
                    <!-- 手寫 -->
                    <button class="toolbar-btn" data-command="handwriting" title="手寫輸入">
                        <i class="fas fa-pen-fancy"></i>
                    </button>
                    <div class="toolbar-separator"></div>
                    <!-- 檢視 -->
                    <button class="toolbar-btn" data-command="togglePreview" title="預覽">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="toolbar-btn" data-command="toggleMarkdown" title="Markdown">
                        <i class="fab fa-markdown"></i>
                    </button>
                    <div class="toolbar-separator"></div>
                    <!-- 功能開關 -->
                    <div class="toggle-switches">
                        <label class="toggle-switch" title="LSP">
                            <input type="checkbox" id="wysiwyg-lsp-toggle" checked>
                            <span class="toggle-slider"></span>
                            <span class="toggle-label">LSP</span>
                        </label>
                        <label class="toggle-switch" title="Ghost AI">
                            <input type="checkbox" id="wysiwyg-ghost-toggle">
                            <span class="toggle-slider"></span>
                            <span class="toggle-label">Ghost</span>
                        </label>
                    </div>
                </div>
                
                <!-- 編輯區域 -->
                <div class="editor-content">
                    <div class="editor-main note-content markdown-content" contenteditable="true" 
                         data-placeholder="${this.options.placeholder}">
                    </div>
                    
                    <!-- Ghost文字覆蓋層 -->
                    <div class="ghost-overlay"></div>
                </div>
                
                <!-- 狀態列 -->
                <div class="editor-status">
                    <div class="status-left">
                        <span class="word-count">0 字</span>
                        <span class="char-count">0 字元</span>
                    </div>
                    <div class="status-right">
                        <span class="lsp-status" title="LSP狀態">
                            <i class="fas fa-circle text-secondary"></i> LSP
                        </span>
                        <span class="ghost-status" title="Ghost AI狀態">
                            <i class="fas fa-circle text-secondary"></i> Ghost
                        </span>
                        <span class="cursor-position">第 1 行，第 1 列</span>
                    </div>
                </div>
            </div>
        `;
        
        // 如果Modal不存在，則創建並添加到body
        if (modalHTML) {
            document.body.insertAdjacentHTML('beforeend', modalHTML);
        }
        
        // 取得DOM元素引用
        this.editor = this.container.querySelector('.editor-main');
        this.toolbar = this.container.querySelector('.editor-toolbar');
        this.statusBar = this.container.querySelector('.editor-status');
        this.ghostOverlay = this.container.querySelector('.ghost-overlay');
    }
    
    /**
     * 設置工具列
     */
    setupToolbar() {
        this.toolbar.addEventListener('click', (e) => {
            const btn = e.target.closest('.toolbar-btn');
            if (!btn) return;
            
            // 顏色選擇
            if (btn.dataset.command === 'foreColor' || btn.dataset.command === 'backColor') {
                e.preventDefault();
                this.showColorPicker(btn.dataset.command, btn);
                return;
            }
            
            e.preventDefault();
            const command = btn.dataset.command;
            this.executeCommand(command, btn);
        });
        
        this.toolbar.addEventListener('change', (e) => {
            if (e.target.classList.contains('toolbar-select')) {
                const command = e.target.dataset.command;
                const value = e.target.value;
                this.executeCommand(command, value);
            }
            
            if (e.target.classList.contains('toolbar-color')) {
                const command = e.target.dataset.command;
                const color = e.target.value;
                this.executeCommand(command, color);
            }
        });
        
        // AI設定開關事件監聽
        this.setupAIControls();
    }
    
    /**
     * 設置AI控制開關
     */
    setupAIControls() {
        // LSP開關 - 同步HTML設定區域和工具欄
        const htmlLspToggle = document.getElementById('lspToggle');
        const toolbarLspToggle = document.getElementById('wysiwyg-lsp-toggle');
        
        const handleLspChange = (enabled) => {
            this.lspEnabled = enabled;
            this.updateLSPStatus(this.lspEnabled ? 'enabled' : 'disabled');
            this.showNotification(
                this.lspEnabled ? 'success' : 'info',
                `LSP語言伺服器已${this.lspEnabled ? '啟用' : '停用'}`
            );
            
            // 同步兩個開關的狀態
            if (htmlLspToggle) htmlLspToggle.checked = enabled;
            if (toolbarLspToggle) toolbarLspToggle.checked = enabled;
        };
        
        if (htmlLspToggle) {
            htmlLspToggle.addEventListener('change', (e) => {
                handleLspChange(e.target.checked);
            });
        }
        
        if (toolbarLspToggle) {
            toolbarLspToggle.addEventListener('change', (e) => {
                handleLspChange(e.target.checked);
            });
        }
        
        // Ghost開關 - 同步HTML設定區域和工具欄
        const htmlGhostToggle = document.getElementById('ghostToggle');
        const toolbarGhostToggle = document.getElementById('wysiwyg-ghost-toggle');
        
        const handleGhostChange = (enabled) => {
            this.ghostEnabled = enabled;
            this.updateGhostStatus(this.ghostEnabled ? 'enabled' : 'disabled');
            if (!this.ghostEnabled) {
                this.clearGhost();
            }
            this.showNotification(
                `Ghost AI已${this.ghostEnabled ? '啟用' : '停用'}`,
                this.ghostEnabled ? 'success' : 'info'
            );
            
            // 同步兩個開關的狀態
            if (htmlGhostToggle) htmlGhostToggle.checked = enabled;
            if (toolbarGhostToggle) toolbarGhostToggle.checked = enabled;
        };
        
        if (htmlGhostToggle) {
            htmlGhostToggle.addEventListener('change', (e) => {
                handleGhostChange(e.target.checked);
            });
        }
        
        if (toolbarGhostToggle) {
            toolbarGhostToggle.addEventListener('change', (e) => {
                handleGhostChange(e.target.checked);
            });
        }
    }
    
    /**
     * 初始化編輯器
     */
    initEditor() {
        // 設置編輯器樣式
        this.editor.style.minHeight = '400px';
        this.editor.style.padding = '20px';
        this.editor.style.outline = 'none';
        this.editor.style.lineHeight = '1.6';
        this.editor.style.fontSize = '16px';
        
        // 允許富文本編輯
        document.execCommand('defaultParagraphSeparator', false, 'p');
    }
    
    /**
     * 設置事件處理器
     */
    setupEventHandlers() {
        // 內容變更事件
        this.editor.addEventListener('input', () => {
            this.content = this.getContent();
            this.updateStatus();
            this.emit('contentChange', this.content);
            
            // 只在有足夠內容時才觸發Ghost
            if (this.ghostEnabled && this.content && this.content.trim().length > 15) {
                this.scheduleGhost();
            }
        });
        
        // 鍵盤事件
        this.editor.addEventListener('keydown', (e) => {
            this.handleKeydown(e);
        });
        
        // 游標位置變更
        this.editor.addEventListener('selectionchange', () => {
            this.updateCursorPosition();
        });
        
        // 焦點事件
        this.editor.addEventListener('focus', () => {
            this.container.classList.add('editor-focused');
        });
        
        this.editor.addEventListener('blur', () => {
            this.container.classList.remove('editor-focused');
        });
    }
    
    /**
     * 設置圖片貼上功能
     */
    setupImagePasting() {
        this.editor.addEventListener('paste', async (e) => {
            const items = Array.from(e.clipboardData.items);
            
            for (const item of items) {
                if (item.type.startsWith('image/')) {
                    e.preventDefault();
                    
                    const file = item.getAsFile();
                    if (file) {
                        try {
                            const imageUrl = await this.uploadImage(file);
                            this.insertImage(imageUrl);
                        } catch (error) {
                            console.error('圖片上傳失敗:', error);
                            this.showMessage('圖片上傳失敗', 'error');
                        }
                    }
                    return;
                }
            }
        });
    }
    
    /**
     * 設置手寫功能
     */
    setupHandwriting() {
        if (!this.options.enableHandwriting) return;
        
        // 防止重複設置
        if (this.handwritingSetup) return;
        this.handwritingSetup = true;
        
        const modal = document.getElementById('handwritingModal');
        const canvas = modal.querySelector('.handwriting-canvas');
        const insertBtn = modal.querySelector('#insertHandwriting');
        
        // 檢查元素是否存在
        if (!modal || !canvas || !insertBtn) {
            console.warn('手寫功能初始化失敗：缺少必要的DOM元素');
            return;
        }
        
        // 初始化手寫畫布
        this.handwritingCanvas = canvas;
        this.handwritingContext = canvas.getContext('2d');
        
        // 設置畫布樣式
        this.handwritingContext.lineWidth = 2;
        this.handwritingContext.lineCap = 'round';
        this.handwritingContext.lineJoin = 'round';
        this.handwritingContext.strokeStyle = '#000';
        
        // 手寫工具切換 - 檢查是否已經綁定事件，避免重複綁定
        if (!modal.hasAttribute('data-event-bound')) {
            modal.addEventListener('click', (e) => {
                const toolBtn = e.target.closest('[data-tool]');
                if (toolBtn) {
                    modal.querySelectorAll('[data-tool]').forEach(btn => 
                        btn.classList.remove('active'));
                    toolBtn.classList.add('active');
                    
                    const tool = toolBtn.dataset.tool;
                    if (tool === 'eraser') {
                        this.handwritingContext.globalCompositeOperation = 'destination-out';
                    } else {
                        this.handwritingContext.globalCompositeOperation = 'source-over';
                    }
                }
                
                const actionBtn = e.target.closest('[data-action]');
                if (actionBtn) {
                    const action = actionBtn.dataset.action;
                    if (action === 'clear') {
                        this.clearHandwriting();
                    }
                }
            });
            modal.setAttribute('data-event-bound', 'true');
        }
        // 手寫繪製事件
        this.setupHandwritingDrawing();
        
        // 插入按鈕 - 檢查是否已經綁定事件，避免重複綁定
        if (!insertBtn.hasAttribute('data-event-bound')) {
            insertBtn.addEventListener('click', async () => {
                const mode = modal.querySelector('input[name="handwritingMode"]:checked').value;
                await this.insertHandwriting(mode);
                const modalInstance = bootstrap.Modal.getInstance(modal);
                if (modalInstance) {
                    modalInstance.hide();
                }
            });
            insertBtn.setAttribute('data-event-bound', 'true');
        }
    }
    
    /**
     * 設置手寫繪製
     */
    setupHandwritingDrawing() {
        const canvas = this.handwritingCanvas;
        
        // 檢查是否已經綁定事件，避免重複綁定
        if (canvas.hasAttribute('data-drawing-events-bound')) {
            return;
        }
        
        let isDrawing = false;
        let lastPoint = null;
        
        // 滑鼠事件
        canvas.addEventListener('mousedown', (e) => {
            isDrawing = true;
            lastPoint = this.getCanvasPoint(e);
        });
        
        canvas.addEventListener('mousemove', (e) => {
            if (!isDrawing) return;
            
            const currentPoint = this.getCanvasPoint(e);
            this.drawLine(lastPoint, currentPoint);
            lastPoint = currentPoint;
        });
        
        canvas.addEventListener('mouseup', () => {
            isDrawing = false;
            lastPoint = null;
        });
        
        // 觸控事件（支援手機和平板）
        canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            isDrawing = true;
            lastPoint = this.getCanvasPoint(e.touches[0]);
        }, { passive: false });
        
        canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            if (!isDrawing) return;
            
            const currentPoint = this.getCanvasPoint(e.touches[0]);
            this.drawLine(lastPoint, currentPoint);
            lastPoint = currentPoint;
        }, { passive: false });
        
        canvas.addEventListener('touchend', (e) => {
            e.preventDefault();
            isDrawing = false;
            lastPoint = null;
        });
        
        // 標記事件已綁定
        canvas.setAttribute('data-drawing-events-bound', 'true');
    }
    
    /**
     * 取得畫布座標
     */
    getCanvasPoint(e) {
        const rect = this.handwritingCanvas.getBoundingClientRect();
        return {
            x: (e.clientX - rect.left) * (this.handwritingCanvas.width / rect.width),
            y: (e.clientY - rect.top) * (this.handwritingCanvas.height / rect.height)
        };
    }
    
    /**
     * 繪製線條
     */
    drawLine(from, to) {
        const ctx = this.handwritingContext;
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        ctx.lineTo(to.x, to.y);
        ctx.stroke();
    }
    
    /**
     * 清除手寫內容
     */
    clearHandwriting() {
        const ctx = this.handwritingContext;
        ctx.clearRect(0, 0, this.handwritingCanvas.width, this.handwritingCanvas.height);
    }
    
    /**
     * 插入手寫內容
     */
    async insertHandwriting(mode) {
        const canvas = this.handwritingCanvas;
        const dataUrl = canvas.toDataURL('image/png');
        
        if (mode === 'image') {
            // 直接插入為圖片
            try {
                const result = await this.uploadImageFromDataUrl(dataUrl);
                this.insertImage(result.url);
                this.showMessage('手寫內容已插入為圖片', 'success');
            } catch (error) {
                console.error('圖片上傳失敗:', error);
                this.showMessage('圖片上傳失敗', 'error');
            }
        } else {
            // AI轉換為文字 - 先上傳檔案，再用檔案路徑進行OCR
            try {
                // 先上傳保存檔案
                const result = await this.uploadImageFromDataUrl(dataUrl);
                // 使用檔案路徑進行OCR (更高效)
                const text = await this.convertHandwritingToTextFromPath(result.path);
                this.insertText(text);
                this.showMessage('手寫內容已轉換為文字', 'success');
            } catch (error) {
                console.error('手寫辨識失敗:', error);
                this.showMessage('手寫辨識失敗', 'error');
            }
        }
        
        this.clearHandwriting();
    }
    
    /**
     * 執行編輯器命令
     */
    executeCommand(command, value = null) {
        this.editor.focus();
        
        switch (command) {
            case 'heading':
                this.formatHeading(value);
                break;
                
            case 'insertImage':
                this.showImageDialog();
                break;
                
            case 'insertLink':
                this.showLinkDialog();
                break;
                
            case 'insertTable':
                this.insertTable();
                break;
                
            case 'insertCode':
                this.insertCodeBlock();
                break;
                
            case 'handwriting':
                this.showHandwritingModal();
                break;
                
            case 'aiComplete':
                this.triggerAICompletion();
                break;
                
            case 'togglePreview':
                this.togglePreview();
                break;
                
            case 'toggleMarkdown':
                this.toggleMarkdown();
                break;
                
            default:
                document.execCommand(command, false, value);
        }
        
        this.updateToolbarState();
    }
    
    /**
     * 顯示輸入模態框（支援下拉選單）
     */
    showInputModal(title, fields, callback) {
        // 創建模態框HTML
        const modalId = 'input-modal-' + Date.now();
        const modalHTML = `
            <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <form id="${modalId}-form">
                                ${fields.map((field, index) => {
                                    if (field.type === 'select') {
                                        return `
                                            <div class="mb-3">
                                                <label for="${modalId}-field-${index}" class="form-label">${field.label}</label>
                                                <select class="form-select" id="${modalId}-field-${index}">
                                                    ${field.options.map(option => 
                                                        `<option value="${option.value}" ${option.value === field.defaultValue ? 'selected' : ''}>${option.text}</option>`
                                                    ).join('')}
                                                </select>
                                            </div>
                                        `;
                                    } else {
                                        return `
                                            <div class="mb-3">
                                                <label for="${modalId}-field-${index}" class="form-label">${field.label}</label>
                                                <input type="${field.type || 'text'}" class="form-control" 
                                                       id="${modalId}-field-${index}" 
                                                       value="${field.defaultValue || ''}"
                                                       placeholder="${field.placeholder || ''}">
                                            </div>
                                        `;
                                    }
                                }).join('')}
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                            <button type="button" class="btn btn-primary" id="${modalId}-confirm">確定</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 添加到頁面
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        // 初始化模態框
        const modal = new bootstrap.Modal(document.getElementById(modalId));
        
        // 處理確定按鈕
        document.getElementById(`${modalId}-confirm`).addEventListener('click', () => {
            const values = fields.map((_, index) => {
                const element = document.getElementById(`${modalId}-field-${index}`);
                return element.value;
            });
            
            modal.hide();
            if (callback) callback(values);
        });
        
        // 清理模態框
        document.getElementById(modalId).addEventListener('hidden.bs.modal', () => {
            document.getElementById(modalId).remove();
        });
        
        modal.show();
        
        // 聚焦第一個輸入框或選擇框
        setTimeout(() => {
            const firstInput = document.querySelector(`#${modalId} input, #${modalId} select`);
            if (firstInput) firstInput.focus();
        }, 500);
    }

    /**
     * 插入表格
     */
    insertTable() {
        this.showInputModal('插入表格', [
            { label: '行數', defaultValue: '3', placeholder: '請輸入表格行數' },
            { label: '列數', defaultValue: '3', placeholder: '請輸入表格列數' }
        ], (values) => {
            const [rows, cols] = values;
            
            if (!rows || !cols) return;
            
            const rowCount = parseInt(rows);
            const colCount = parseInt(cols);
            
            if (rowCount < 1 || colCount < 1) return;
            
            let tableHTML = '<table>';
            
            // 創建標題行
            tableHTML += '<thead><tr>';
            for (let j = 0; j < colCount; j++) {
                tableHTML += '<th>標題 ' + (j + 1) + '</th>';
            }
            tableHTML += '</tr></thead>';
            
            // 創建資料行
            tableHTML += '<tbody>';
            for (let i = 1; i < rowCount; i++) {
                tableHTML += '<tr>';
                for (let j = 0; j < colCount; j++) {
                    tableHTML += '<td>資料</td>';
                }
                tableHTML += '</tr>';
            }
            tableHTML += '</tbody></table><br>';
            
            document.execCommand('insertHTML', false, tableHTML);
        });
    }
    
    /**
     * 顯示程式語言選擇模態框
     */
    showCodeLanguageModal(callback) {
        const commonLanguages = [
            { value: 'javascript', label: 'JavaScript' },
            { value: 'python', label: 'Python' },
            { value: 'java', label: 'Java' },
            { value: 'csharp', label: 'C#' },
            { value: 'cpp', label: 'C++' },
            { value: 'c', label: 'C' },
            { value: 'html', label: 'HTML' },
            { value: 'css', label: 'CSS' },
            { value: 'sql', label: 'SQL' },
            { value: 'php', label: 'PHP' },
            { value: 'typescript', label: 'TypeScript' },
            { value: 'go', label: 'Go' },
            { value: 'rust', label: 'Rust' },
            { value: 'swift', label: 'Swift' },
            { value: 'kotlin', label: 'Kotlin' },
            { value: 'ruby', label: 'Ruby' },
            { value: 'bash', label: 'Bash/Shell' },
            { value: 'json', label: 'JSON' },
            { value: 'xml', label: 'XML' },
            { value: 'yaml', label: 'YAML' },
            { value: 'markdown', label: 'Markdown' },
            { value: 'plaintext', label: '純文字' }
        ];

        const modalId = 'code-language-modal-' + Date.now();
        const modalHTML = `
            <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">選擇程式語言</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label for="${modalId}-select" class="form-label">常用語言</label>
                                <select class="form-select" id="${modalId}-select">
                                    <option value="">請選擇...</option>
                                    ${commonLanguages.map(lang => 
                                        `<option value="${lang.value}">${lang.label}</option>`
                                    ).join('')}
                                </select>
                            </div>
                            <div class="mb-3">
                                <label for="${modalId}-custom" class="form-label">或輸入自定義語言</label>
                                <input type="text" class="form-control" id="${modalId}-custom" 
                                       placeholder="例如：python3, nodejs...">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                            <button type="button" class="btn btn-primary" id="${modalId}-confirm">插入程式碼</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        const modal = new bootstrap.Modal(document.getElementById(modalId));

        // 處理選擇變更
        const selectElement = document.getElementById(`${modalId}-select`);
        const customElement = document.getElementById(`${modalId}-custom`);
        
        selectElement.addEventListener('change', () => {
            if (selectElement.value) {
                customElement.value = '';
            }
        });

        customElement.addEventListener('input', () => {
            if (customElement.value) {
                selectElement.value = '';
            }
        });

        // 處理確定按鈕
        document.getElementById(`${modalId}-confirm`).addEventListener('click', () => {
            const language = selectElement.value || customElement.value || 'plaintext';
            modal.hide();
            if (callback) callback(language);
        });

        // 清理模態框
        document.getElementById(modalId).addEventListener('hidden.bs.modal', () => {
            document.getElementById(modalId).remove();
        });

        modal.show();
        setTimeout(() => selectElement.focus(), 500);
    }

    /**
     * 插入程式碼區塊
     */
    insertCodeBlock() {
        this.showCodeLanguageModal((language) => {
            const codeHTML = `
                <pre><code class="language-${language}">// 請在此輸入您的程式碼
console.log('Hello, World!');</code></pre>
            `;
            document.execCommand('insertHTML', false, codeHTML);
            
            // 使用全域的程式碼複製管理器為新插入的程式碼區塊添加複製按鈕
            setTimeout(() => {
                if (window.CodeCopyManager) {
                    window.CodeCopyManager.bindNewCodeBlocks();
                }
                // 觸發語法高亮
                this.highlightCodeBlocks();
            }, 100);
        });
    }

    
    /**
     * 顯示圖片對話框
     */
    showImageDialog() {
        this.showInputModal('插入圖片', [
            { label: '圖片URL', placeholder: '請輸入圖片URL' },
            { label: '替代文字 (Alt)', placeholder: '描述圖片內容 (可選)', defaultValue: '' }
        ], (values) => {
            const [url, alt] = values;
            if (url) {
                this.insertImage(url, alt || '圖片');
            }
        });
    }
    
    /**
     * 顯示連結對話框
     */
    showLinkDialog() {
        this.showInputModal('插入連結', [
            { label: '連結URL', placeholder: '請輸入連結URL' },
            { label: '連結文字', placeholder: '請輸入連結文字' }
        ], (values) => {
            const [url, text] = values;
            if (url) {
                const linkText = text || url;
                const linkHTML = `<a href="${url}" target="_blank">${linkText}</a>`;
                document.execCommand('insertHTML', false, linkHTML);
            }
        });
    }
    
    /**
     * 切換預覽模式
     */
    togglePreview() {
        // 實現預覽切換
        this.showMessage('預覽功能開發中', 'info');
    }
    
    /**
     * 切換Markdown模式
     */
    toggleMarkdown() {
        // 實現Markdown切換
        this.showMessage('請使用頁面上方的標籤頁切換模式', 'info');
    }
    
    /**
     * 格式化標題
     */
    formatHeading(level) {
        if (!level) {
            document.execCommand('formatBlock', false, 'p');
            return;
        }
        
        document.execCommand('formatBlock', false, level);
    }
    
    /**
     * 插入圖片
     */
    insertImage(url, alt = '') {
        const img = document.createElement('img');
        img.src = url;
        img.alt = alt || '圖片'; // 提供預設的alt文字
        img.style.maxWidth = '100%';
        img.style.height = 'auto';
        
        this.insertElement(img);
    }
    
    /**
     * 插入文字
     */
    insertText(text) {
        const selection = window.getSelection();
        if (selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            range.deleteContents();
            range.insertNode(document.createTextNode(text));
            range.collapse(false);
        }
    }
    
    /**
     * 插入元素
     */
    insertElement(element) {
        const selection = window.getSelection();
        if (selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            range.deleteContents();
            range.insertNode(element);
            range.collapse(false);
        }
    }
    
    /**
     * 顯示手寫模態框
     */
    showHandwritingModal() {
        const modalElement = document.getElementById('handwritingModal');
        // 檢查是否已經有 Modal 實例，避免重複創建
        let modal = bootstrap.Modal.getInstance(modalElement);
        if (!modal) {
            modal = new bootstrap.Modal(modalElement);
        }
        modal.show();
    }
    
    /**
     * 處理鍵盤事件
     */
    handleKeydown(e) {
        // Tab鍵接受Ghost建議
        if (e.key === 'Tab' && (this.ghostText || this.currentGhostContainer)) {
            e.preventDefault();
            this.acceptGhost();
            return;
        }
        
        // Esc鍵清除Ghost
        if (e.key === 'Escape' && (this.ghostText || this.currentGhostContainer)) {
            e.preventDefault();
            this.clearGhost();
            return;
        }
        
        // "/"鍵觸發AI命令選單
        if (e.key === '/' && this.ghostEnabled) {
            // 延遲執行，讓"/"字符先輸入
            setTimeout(() => {
                this.showAICommandMenu();
            }, 100);
        }
        
        // 快捷鍵處理
        if (e.ctrlKey || e.metaKey) {
            switch (e.key.toLowerCase()) {
                case 'b':
                    e.preventDefault();
                    this.executeCommand('bold');
                    break;
                case 'i':
                    e.preventDefault();
                    this.executeCommand('italic');
                    break;
                case 'u':
                    e.preventDefault();
                    this.executeCommand('underline');
                    break;
            }
        }
    }
    
    /**
     * 更新狀態列
     */
    updateStatus() {
        const text = this.editor.textContent || '';
        const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
        const charCount = text.length;
        
        const wordCountEl = this.statusBar.querySelector('.word-count');
        const charCountEl = this.statusBar.querySelector('.char-count');
        
        if (wordCountEl) wordCountEl.textContent = `${wordCount} 字`;
        if (charCountEl) charCountEl.textContent = `${charCount} 字元`;
    }
    
    /**
     * 更新游標位置
     */
    updateCursorPosition() {
        const selection = window.getSelection();
        if (selection.rangeCount === 0) return;
        
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        
        // 更新Ghost覆蓋層位置
        if (this.ghostOverlay) {
            this.ghostOverlay.style.left = rect.left + 'px';
            this.ghostOverlay.style.top = rect.bottom + 'px';
        }
        
        // 更新狀態列游標位置（簡化版）
        const positionEl = this.statusBar.querySelector('.cursor-position');
        if (positionEl) {
            positionEl.textContent = '正在編輯...';
        }
    }
    
    /**
     * 取得編輯器內容
     */
    getContent(format = 'html') {
        switch (format) {
            case 'html':
                return this.editor.innerHTML;
            case 'text':
                return this.editor.textContent;
            case 'markdown':
                return this.htmlToMarkdown(this.editor.innerHTML);
            default:
                return this.editor.innerHTML;
        }
    }
    
    /**
     * 設置編輯器內容
     */
    setContent(content, format = 'html') {
        switch (format) {
            case 'html':
                this.editor.innerHTML = content;
                break;
            case 'text':
                this.editor.textContent = content;
                break;
            case 'markdown':
                this.editor.innerHTML = this.markdownToHtml(content);
                break;
        }
        
        this.content = this.getContent();
        this.updateStatus();
        
        // 為新內容中的程式碼區塊綁定複製功能和語法高亮
        setTimeout(() => {
            if (window.CodeCopyManager) {
                window.CodeCopyManager.bindNewCodeBlocks();
            }
            
            // 觸發 Prism.js 語法高亮
            this.highlightCodeBlocks();
        }, 100);
    }
    
    /**
     * 觸發語法高亮
     */
    highlightCodeBlocks() {
        if (typeof Prism !== 'undefined') {
            // 處理編輯器內的代碼塊
            const codeBlocks = this.editor.querySelectorAll('pre code');
            codeBlocks.forEach(block => {
                // 確保代碼塊有正確的 language 類別
                if (!block.className.includes('language-')) {
                    block.className += ' language-plaintext';
                }
                // 移除 Prism 可能添加的類別，然後重新高亮
                block.classList.remove('prism-highlighted');
            });
            
            // 觸發 Prism.js 高亮
            Prism.highlightAllUnder(this.editor);
        }
    }
    
    /**
     * HTML轉Markdown（改進版）
     */
    htmlToMarkdown(html) {
        if (window.markdownConverter) {
            // 在使用 markdownConverter 之前先處理顏色標籤
            let processedHtml = html;
            
            // 處理有 color 屬性的 font 標籤，轉換為 span 標籤
            processedHtml = processedHtml.replace(/<font[^>]*color="([^"]*)"[^>]*>(.*?)<\/font>/gis, '<span style="color: $1;">$2</span>');
            
            const result = window.markdownConverter.htmlToMarkdown(processedHtml);
            return result;
        }
        
        // 簡化版轉換（備用）
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        
        // 基本的HTML到Markdown轉換
        let markdown = html;
        
        // 先處理複雜結構，再處理簡單標籤
        
        // 1. 圖片（在移除其他標籤之前處理）
        markdown = markdown.replace(/<img[^>]+src="([^"]*)"[^>]*alt="([^"]*)"[^>]*>/gi, '![$2]($1)');
        markdown = markdown.replace(/<img[^>]+alt="([^"]*)"[^>]*src="([^"]*)"[^>]*>/gi, '![$1]($2)');
        markdown = markdown.replace(/<img[^>]+src="([^"]*)"[^>]*>/gi, '![]($1)');
        
        // 2. 連結
        markdown = markdown.replace(/<a[^>]+href="([^"]*)"[^>]*>(.*?)<\/a>/gi, '[$2]($1)');
        
        // 3. 標題
        markdown = markdown.replace(/<h([1-6])[^>]*>(.*?)<\/h[1-6]>/gi, (match, level, content) => {
            const hashes = '#'.repeat(parseInt(level));
            return `\n${hashes} ${content.trim()}\n\n`;
        });
        
        // 4. 程式碼區塊（先處理多行，再處理單行）
        // 處理我們自定義的代碼塊格式
        markdown = markdown.replace(/<div[^>]*class="code-block-container"[^>]*>[\s\S]*?<span[^>]*class="code-language"[^>]*>([^<]*)<\/span>[\s\S]*?<code[^>]*class="language-([^"]*)"[^>]*>(.*?)<\/code>[\s\S]*?<\/div>/gis, (match, langDisplay, langClass, code) => {
            const lang = langClass || langDisplay.toLowerCase();
            return `\n\`\`\`${lang}\n${code.trim()}\n\`\`\`\n`;
        });
        
        // 處理標準的代碼塊格式
        markdown = markdown.replace(/<pre[^>]*><code[^>]*class="language-([^"]*)"[^>]*>(.*?)<\/code><\/pre>/gis, (match, lang, code) => {
            return `\n\`\`\`${lang}\n${code.trim()}\n\`\`\`\n`;
        });
        markdown = markdown.replace(/<pre[^>]*><code[^>]*>(.*?)<\/code><\/pre>/gis, (match, code) => {
            return `\n\`\`\`\n${code.trim()}\n\`\`\`\n`;
        });
        markdown = markdown.replace(/<code[^>]*>(.*?)<\/code>/gi, '`$1`');
        
        // 5. 列表（先處理有序，再處理無序）
        markdown = markdown.replace(/<ol[^>]*>(.*?)<\/ol>/gis, (match, content) => {
            let counter = 1;
            return '\n' + content.replace(/<li[^>]*>(.*?)<\/li>/gi, () => `${counter++}. $1\n`) + '\n';
        });
        markdown = markdown.replace(/<ul[^>]*>(.*?)<\/ul>/gis, (match, content) => {
            return '\n' + content.replace(/<li[^>]*>(.*?)<\/li>/gi, '- $1\n') + '\n';
        });
        
        // 6. 表格
        markdown = markdown.replace(/<table[^>]*>(.*?)<\/table>/gis, (match, tableContent) => {
            let result = '\n';
            const rows = tableContent.match(/<tr[^>]*>(.*?)<\/tr>/gis) || [];
            
            for (let i = 0; i < rows.length; i++) {
                const row = rows[i];
                const cells = row.match(/<t[hd][^>]*>(.*?)<\/t[hd]>/gis) || [];
                const cellContents = cells.map(cell => 
                    cell.replace(/<t[hd][^>]*>(.*?)<\/t[hd]>/gi, '$1').trim()
                );
                
                result += '| ' + cellContents.join(' | ') + ' |\n';
                
                // 在第一行後加分隔線
                if (i === 0) {
                    result += '|' + cellContents.map(() => ' --- ').join('|') + '|\n';
                }
            }
            
            return result + '\n';
        });
        
        // 7. 引用
        markdown = markdown.replace(/<blockquote[^>]*>(.*?)<\/blockquote>/gis, (match, content) => {
            return '\n> ' + content.replace(/\n/g, '\n> ').trim() + '\n\n';
        });
        
        // 8. 分隔線
        markdown = markdown.replace(/<hr[^>]*\/?>/gi, '\n---\n');
        
        // 9. 格式化文字（順序很重要，先處理刪除線，避免嵌套問題）
        console.log('處理格式化之前:', markdown);
        
        // 處理刪除線（使用更寬鬆的匹配）
        let beforeDel = markdown;
        markdown = markdown.replace(/<del[^>]*>(.*?)<\/del>/gis, '~~$1~~');
        markdown = markdown.replace(/<s[^>]*>(.*?)<\/s>/gis, '~~$1~~');
        markdown = markdown.replace(/<strike[^>]*>(.*?)<\/strike>/gis, '~~$1~~');
        if (beforeDel !== markdown) console.log('刪除線轉換完成:', markdown);
        
        // 處理粗體（在斜體之前處理）
        let beforeBold = markdown;
        markdown = markdown.replace(/<strong[^>]*>(.*?)<\/strong>/gis, '**$1**');
        markdown = markdown.replace(/<b[^>]*>(.*?)<\/b>/gis, '**$1**');
        if (beforeBold !== markdown) console.log('粗體轉換完成:', markdown);
        
        // 處理斜體（使用更寬鬆的匹配）
        let beforeItalic = markdown;
        markdown = markdown.replace(/<em[^>]*>(.*?)<\/em>/gis, '*$1*');
        markdown = markdown.replace(/<i[^>]*>(.*?)<\/i>/gis, '*$1*');
        if (beforeItalic !== markdown) console.log('斜體轉換完成:', markdown);
        
        // 處理下劃線（保持HTML格式）
        markdown = markdown.replace(/<u[^>]*>(.*?)<\/u>/gis, '<u>$1</u>');
        
        // 9.5 處理顏色樣式（在移除其他HTML標籤之前）
        console.log('處理顏色樣式之前:', markdown);
        
        // 處理有 style 屬性的 span 標籤，保留顏色資訊
        markdown = markdown.replace(/<span[^>]*style="([^"]*)"[^>]*>(.*?)<\/span>/gis, (match, style, content) => {
            // 檢查是否包含顏色樣式
            const hasColor = style.includes('color');
            const hasBackground = style.includes('background');
            
            if (hasColor || hasBackground) {
                // 保留完整的 span 標籤和樣式
                console.log('保留顏色樣式:', match);
                return match;
            }
            
            // 如果沒有顏色樣式，只返回內容
            return content;
        });
        
        // 處理有 color 屬性的 font 標籤
        markdown = markdown.replace(/<font[^>]*color="([^"]*)"[^>]*>(.*?)<\/font>/gis, '<span style="color: $1;">$2</span>');
        
        console.log('處理顏色樣式之後:', markdown);
        
        // 10. 段落和換行（改進換行處理）
        // 先處理段落，確保段落間有正確的間距
        markdown = markdown.replace(/<p[^>]*>(.*?)<\/p>/gis, (match, content) => {
            return content.trim() + '\n\n';
        });
        
        // 處理 br 標籤為單個換行
        markdown = markdown.replace(/<br[^>]*\/?>/gi, '\n');
        
        // 處理 div 標籤
        markdown = markdown.replace(/<div[^>]*>(.*?)<\/div>/gis, (match, content) => {
            return content.trim() + '\n';
        });
        
        // 11. 移除剩餘的HTML標籤（但保留顏色和下劃線標籤）
        // 先保護顏色和下劃線標籤
        const protectedTags = [];
        let protectedIndex = 0;
        
        // 保護所有含有 style 屬性的 span 標籤（包括顏色和背景色）
        markdown = markdown.replace(/<span[^>]*style="[^"]*"[^>]*>.*?<\/span>/gis, (match) => {
            console.log('保護樣式標籤:', match);
            const placeholder = `__PROTECTED_TAG_${protectedIndex}__`;
            protectedTags[protectedIndex] = match;
            protectedIndex++;
            return placeholder;
        });
        
        // 保護下劃線標籤
        markdown = markdown.replace(/<u[^>]*>.*?<\/u>/gis, (match) => {
            const placeholder = `__PROTECTED_TAG_${protectedIndex}__`;
            protectedTags[protectedIndex] = match;
            protectedIndex++;
            return placeholder;
        });
        
        // 移除其他HTML標籤
        markdown = markdown.replace(/<[^>]*>/g, '');
        
        // 恢復受保護的標籤
        for (let i = 0; i < protectedTags.length; i++) {
            markdown = markdown.replace(`__PROTECTED_TAG_${i}__`, protectedTags[i]);
        }
        
        console.log('恢復保護標籤後:', markdown);
        
        // 12. 清理HTML實體
        markdown = markdown.replace(/&nbsp;/g, ' ');
        markdown = markdown.replace(/&amp;/g, '&');
        markdown = markdown.replace(/&lt;/g, '<');
        markdown = markdown.replace(/&gt;/g, '>');
        markdown = markdown.replace(/&quot;/g, '"');
        markdown = markdown.replace(/&#39;/g, "'");
        
        // 13. 清理多餘的空行和空格
        markdown = markdown.replace(/\n{3,}/g, '\n\n');
        markdown = markdown.replace(/[ \t]+$/gm, ''); // 移除行尾空格
        markdown = markdown.replace(/^\s+|\s+$/g, ''); // 移除開頭和結尾空格
        
        console.log('htmlToMarkdown 輸出:', markdown);
        return markdown;
    }
    
    /**
     * Markdown轉HTML（改進版）
     */
    markdownToHtml(markdown) {
        if (window.markdownConverter) {
            return window.markdownConverter.markdownToHtml(markdown);
        }
        
        // 如果有marked.js，使用它並配置為與後端一致
        if (window.marked) {
            // 配置 marked 以匹配後端 Python markdown 的行為
            const renderer = new marked.Renderer();
            
            // 自訂代碼塊渲染
            renderer.code = function(code, language) {
                return `<pre><code class="language-${language || 'plaintext'}">${code}</code></pre>`;
            };
            
            // 自訂行內代碼渲染
            renderer.codespan = function(text) {
                return `<code>${text}</code>`;
            };
            
            marked.setOptions({
                renderer: renderer,
                breaks: true,        // 支援換行
                gfm: true,          // GitHub Flavored Markdown
                tables: true,       // 支援表格
                sanitize: false     // 不清理 HTML（因為我們需要保留樣式）
            });
            
            return marked.parse(markdown);
        }
        
        // 簡化版轉換（備用）
        let html = markdown;
        
        // 程式碼區塊（先處理多行程式碼，改進處理格式）
        // 處理標準格式：```language\ncode\n```
        html = html.replace(/```(\w+)?\n([\s\S]*?)\n```/g, (match, language, code) => {
            const lang = language || 'plaintext';
            return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`;
        });
        
        // 處理可能的錯誤格式：```language直接接代碼
        html = html.replace(/```(\w+)\s*([\s\S]*?)```/g, (match, language, code) => {
            // 如果已經被上面的規則處理過，跳過
            if (match.includes('<pre><code')) {
                return match;
            }
            
            const lang = language || 'plaintext';
            return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`;
        });
        
        // 行內程式碼
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // 標題
        html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
        html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
        
        // 粗體和斜體
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        // 段落
        html = html.replace(/\n\n/g, '</p><p>');
        html = '<p>' + html + '</p>';
        
        // 為轉換後的程式碼區塊綁定複製功能
        setTimeout(() => {
            if (window.CodeCopyManager) {
                window.CodeCopyManager.bindNewCodeBlocks();
            }
        }, 100);
        
        return html;
    }

    
    /**
     * 上傳圖片
     */
    async uploadImage(file) {
        const formData = new FormData();
        formData.append('image', file);
        
        // 添加CSRF token
        const csrfToken = document.querySelector('meta[name=csrf-token]')?.getAttribute('content');
        if (csrfToken) {
            formData.append('csrf_token', csrfToken);
        }
        
        const response = await fetch('/notes/upload-image', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('圖片上傳失敗');
        }
        
        const data = await response.json();
        return data.url;
    }
    
    /**
     * 從DataURL上傳圖片
     */
    async uploadImageFromDataUrl(dataUrl) {
        // 準備請求資料
        const requestData = { image: dataUrl };
        
        // 添加CSRF token
        const csrfToken = document.querySelector('meta[name=csrf-token]')?.getAttribute('content');
        if (csrfToken) {
            requestData.csrf_token = csrfToken;
        }
        
        const response = await fetch('/notes/upload-image-dataurl', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error('圖片上傳失敗');
        }
        
        const data = await response.json();
        return {
            url: data.url,
            path: data.path,
            filename: data.filename
        };
    }
    
    /**
     * 手寫轉文字 (使用base64 - 舊方法，保持兼容性)
     */
    async convertHandwritingToText(dataUrl) {
        // 準備請求資料
        const requestData = { image: dataUrl };
        
        // 添加CSRF token
        const csrfToken = document.querySelector('meta[name=csrf-token]')?.getAttribute('content');
        if (csrfToken) {
            requestData.csrf_token = csrfToken;
        }
        
        const response = await fetch('/notes/handwriting-to-text', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error('手寫辨識失敗');
        }
        
        const data = await response.json();
        return data.text;
    }
    
    /**
     * 手寫轉文字 (使用檔案路徑 - 推薦方法)
     */
    async convertHandwritingToTextFromPath(filePath) {
        // 準備請求資料
        const requestData = { file_path: filePath };
        
        // 添加CSRF token
        const csrfToken = document.querySelector('meta[name=csrf-token]')?.getAttribute('content');
        if (csrfToken) {
            requestData.csrf_token = csrfToken;
        }
        
        const response = await fetch('/notes/handwriting-to-text', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error('手寫辨識失敗');
        }
        
        const data = await response.json();
        return data.text;
    }
    
    /**
     * 顯示訊息
     */
    showMessage(message, type = 'info') {
        // 整合現有的showAlert功能
        if (window.showAlert) {
            window.showAlert(type, message);
        } else {
            console.log(`[${type}] ${message}`);
        }
    }
    
    /**
     * 顯示通知 (兼容性方法)
     */
    showNotification(message, type = 'info') {
        this.showMessage(message, type);
    }
    
    /**
     * 事件發送器
     */
    emit(eventName, data = null) {
        if (this.eventHandlers.has(eventName)) {
            this.eventHandlers.get(eventName).forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`事件處理器錯誤 (${eventName}):`, error);
                }
            });
        }
    }
    
    /**
     * 事件監聽器
     */
    on(eventName, handler) {
        if (!this.eventHandlers.has(eventName)) {
            this.eventHandlers.set(eventName, []);
        }
        this.eventHandlers.get(eventName).push(handler);
    }
    
    /**
     * 顯示固定顏色選擇器
     */
    showColorPicker(command, button) {
        // 保存當前的選擇範圍
        const selection = window.getSelection();
        let savedRange = null;
        if (selection.rangeCount > 0) {
            savedRange = selection.getRangeAt(0).cloneRange();
        }
        
        const colors = {
            foreColor: [
                '#000000', '#333333', '#666666', '#999999', '#CCCCCC',
                '#FF0000', '#FF6600', '#FFCC00', '#33CC00', '#0099CC',
                '#6633CC', '#CC0099', '#FFFFFF', '#FFFF00', '#00FFFF'
            ],
            backColor: [
                '#FFFFFF', '#FFFF99', '#FFCCCC', '#CCFFCC', '#CCCCFF',
                '#FFCC99', '#FF9999', '#99FF99', '#9999FF', '#CCCC99',
                '#FFE6CC', '#E6CCFF', '#CCE6FF', '#E6FFE6', '#F0F0F0'
            ]
        };
        
        const colorArray = colors[command] || colors.foreColor;
        
        // 創建彈出框
        const popup = document.createElement('div');
        popup.className = 'color-picker-popup';
        popup.style.cssText = `
            position: absolute;
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 1000;
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 4px;
            width: 200px;
        `;
        
        // 添加顏色方塊
        colorArray.forEach(color => {
            const colorBox = document.createElement('div');
            colorBox.className = 'color-box';
            colorBox.style.cssText = `
                width: 24px;
                height: 24px;
                background-color: ${color};
                border: 2px solid #ddd;
                border-radius: 4px;
                cursor: pointer;
                transition: all 0.2s;
            `;
            
            colorBox.addEventListener('mouseenter', () => {
                colorBox.style.transform = 'scale(1.1)';
                colorBox.style.borderColor = '#007bff';
            });
            
            colorBox.addEventListener('mouseleave', () => {
                colorBox.style.transform = 'scale(1)';
                colorBox.style.borderColor = '#ddd';
            });
            
            colorBox.addEventListener('click', () => {
                // 恢復選擇範圍
                if (savedRange) {
                    try {
                        const newSelection = window.getSelection();
                        newSelection.removeAllRanges();
                        newSelection.addRange(savedRange);
                    } catch (e) {
                        console.log('無法恢復選擇範圍:', e);
                    }
                }
                
                // 執行顏色命令
                this.executeCommand(command, color);
                
                // 移除彈出框
                if (document.body.contains(popup)) {
                    document.body.removeChild(popup);
                }
                
                // 重新聚焦編輯器
                this.editor.focus();
            });
            
            popup.appendChild(colorBox);
        });
        
        // 定位彈出框
        const rect = button.getBoundingClientRect();
        popup.style.left = rect.left + 'px';
        popup.style.top = (rect.bottom + 5) + 'px';
        
        // 添加到頁面
        document.body.appendChild(popup);
        
        // 點擊外部關閉
        const closePopup = (e) => {
            if (!popup.contains(e.target) && document.body.contains(popup)) {
                document.body.removeChild(popup);
                document.removeEventListener('click', closePopup);
                // 重新聚焦編輯器
                this.editor.focus();
            }
        };
        
        setTimeout(() => {
            document.addEventListener('click', closePopup);
        }, 100);
    }

    /**
     * 移除事件監聽器
     */
    off(eventName, handler) {
        if (this.eventHandlers.has(eventName)) {
            const handlers = this.eventHandlers.get(eventName);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
    
    // ===================
    // LSP 功能整合
    // ===================
    
    /**
     * 初始化LSP
     */
    async initLSP() {
        if (!this.lspEnabled) {
            console.log('LSP已停用');
            return;
        }
        
        console.log('開始初始化LSP...');
        
        try {
            // 先獲取正確的Gateway端口
            const response = await fetch('/notes/api/gateway-info');
            const gatewayInfo = await response.json();
            
            if (!gatewayInfo.success) {
                console.warn('無法獲取Gateway信息，使用默認端口');
            }
            
            // 使用正確的WebSocket URL
            const wsUrl = gatewayInfo.lsp_websocket_url || 'ws://localhost:8002/lsp/markdown';
            console.log('連接LSP:', wsUrl);
            
            this.lspSocket = new WebSocket(wsUrl);
            
            this.lspSocket.onopen = () => {
                console.log('LSP連接成功');
                this.updateLSPStatus('connected');
                this.sendLSPInitialize();
            };
            
            this.lspSocket.onmessage = (event) => {
                this.handleLSPMessage(JSON.parse(event.data));
            };
            
            this.lspSocket.onclose = () => {
                console.log('LSP連接關閉');
                this.updateLSPStatus('disconnected');
            };
            
            this.lspSocket.onerror = (error) => {
                console.error('LSP連接錯誤:', error);
                this.updateLSPStatus('error');
            };
            
        } catch (error) {
            console.error('LSP初始化失敗:', error);
            this.updateLSPStatus('error');
        }
    }
    
    /**
     * 發送LSP初始化
     */
    sendLSPInitialize() {
        if (!this.lspSocket || this.lspSocket.readyState !== WebSocket.OPEN) return;
        
        const message = {
            jsonrpc: '2.0',
            id: 1,
            method: 'initialize',
            params: {
                processId: null,
                clientInfo: { name: 'WYSIWYG Editor', version: '1.0.0' },
                capabilities: {
                    textDocument: {
                        completion: { dynamicRegistration: true },
                        hover: { dynamicRegistration: true }
                    }
                }
            }
        };
        
        this.lspSocket.send(JSON.stringify(message));
    }
    
    /**
     * 處理LSP消息
     */
    handleLSPMessage(message) {
        if (message.method === 'textDocument/publishDiagnostics') {
            this.handleDiagnostics(message.params);
        } else if (message.id && message.result) {
            this.handleLSPResponse(message);
        }
    }
    
    /**
     * 處理LSP回應
     */
    handleLSPResponse(message) {
        console.log('LSP回應:', message);
        // 處理各種LSP回應
        if (message.result && Array.isArray(message.result)) {
            // 處理補全建議
            this.showLSPSuggestions(message.result);
        }
    }
    
    /**
     * 處理診斷信息
     */
    handleDiagnostics(params) {
        console.log('LSP診斷:', params);
        // 可以在這裡顯示語法錯誤等
    }
    
    /**
     * 顯示LSP建議
     */
    showLSPSuggestions(suggestions) {
        console.log('LSP建議:', suggestions);
        // 可以在這裡實現代碼補全UI
    }
    
    /**
     * 更新LSP狀態
     */
    updateLSPStatus(status) {
        const statusEl = this.statusBar.querySelector('.lsp-status i');
        if (!statusEl) return;
        
        statusEl.className = 'fas fa-circle';
        switch (status) {
            case 'connected':
                statusEl.classList.add('text-success');
                break;
            case 'disconnected':
                statusEl.classList.add('text-secondary');
                break;
            case 'error':
                statusEl.classList.add('text-danger');
                break;
        }
    }
    
    // ===================
    // Ghost AI 功能整合
    // ===================
    
    /**
     * 初始化Ghost AI
     */
    initGhost() {
        if (!this.ghostEnabled) return;
        
        this.ghostText = '';
        this.ghostScheduleTimer = null;
        
        console.log('Ghost AI已初始化');
        this.updateGhostStatus('ready');
    }
    
    /**
     * 排程Ghost更新
     */
    scheduleGhost() {
        if (this.ghostScheduleTimer) {
            clearTimeout(this.ghostScheduleTimer);
        }
        
        this.ghostScheduleTimer = setTimeout(() => {
            this.updateGhost();
        }, 500);
    }
    
    /**
     * 更新Ghost建議
     */
    async updateGhost() {
        if (!this.ghostEnabled) return;
        
        try {
            const content = this.getContent('text');
            if (!content.trim()) return;
            
            // 取得游標位置附近的內容
            const selection = window.getSelection();
            const context = this.getContextAroundCursor(content, selection);
            
            // 檢查上下文是否有意義的內容（至少10個字符）
            if (!context || context.trim().length < 10) return;
            
            // 請求Ghost建議
            const suggestion = await this.requestGhostSuggestion(context);
            
            if (suggestion && suggestion.trim()) {
                this.displayGhost(suggestion);
            }
            
        } catch (error) {
            console.error('Ghost更新失敗:', error);
            // 如果是安全過濾器錯誤，不顯示錯誤通知
            if (!error.message.includes('安全過濾器') && !error.message.includes('400')) {
                this.showNotification('Ghost建議暫時無法使用', 'warning');
            }
        }
    }
    
    /**
     * 請求Ghost建議
     */
    async requestGhostSuggestion(context) {
        const headers = {
            'Content-Type': 'application/json'
        };
        
        // 添加CSRF token如果存在
        const csrfToken = document.querySelector('meta[name="csrf-token"]');
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken.getAttribute('content');
        }
        
        const response = await fetch('/notes/ai/ghost-suggestion', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                context: context,
                mode: 'supplement'
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorMessage = errorData.error || `HTTP ${response.status}`;
            
            // 如果是安全過濾器錯誤，拋出特殊錯誤
            if (response.status === 400 && errorMessage.includes('敏感詞彙')) {
                throw new Error('安全過濾器: ' + errorMessage);
            }
            
            throw new Error(`Ghost請求失敗: ${response.status} ${errorMessage}`);
        }
        
        const data = await response.json();
        return data.suggestion;
    }
    
    /**
     * 顯示Ghost文字
     */
    displayGhost(text) {
        console.log('displayGhost被調用，text:', text);
        
        // 處理Markdown語法轉換為HTML格式
        const processedText = this.convertMarkdownToHtml(text);
        this.ghostText = processedText;
        
        // 移除舊的Ghost建議
        this.clearGhost();
        
        // 獲取當前光標位置並保存
        const selection = window.getSelection();
        if (!selection.rangeCount) {
            console.log('沒有選擇範圍，無法顯示Ghost');
            return;
        }
        
        const range = selection.getRangeAt(0);
        
        // 確保range在編輯器內
        if (!this.editor.contains(range.commonAncestorContainer)) {
            console.log('選擇範圍不在編輯器內');
            return;
        }
        
        // 保存當前的光標位置 - 使用更穩健的方式
        try {
            this.savedRange = range.cloneRange();
            console.log('光標位置已保存');
        } catch (e) {
            console.log('無法保存光標位置:', e);
            this.savedRange = null;
        }
        
        const rect = range.getBoundingClientRect();
        
        // 創建Ghost建議容器
        const ghostContainer = document.createElement('div');
        ghostContainer.className = 'ghost-suggestion-container';
        ghostContainer.style.cssText = `
            position: absolute;
            background: #f8f9fa;
            border: 2px solid #007bff;
            border-radius: 8px;
            padding: 12px;
            max-width: 400px;
            z-index: 9999;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            font-family: inherit;
            font-size: 14px;
            line-height: 1.4;
            opacity: 0.9;
        `;
        
        // 添加建議內容
        const suggestionText = document.createElement('div');
        suggestionText.className = 'ghost-suggestion-text';
        suggestionText.style.cssText = `
            color: #555;
            margin-bottom: 8px;
            cursor: pointer;
            border-radius: 4px;
            padding: 4px;
            transition: background-color 0.2s;
        `;
        suggestionText.innerHTML = processedText;
        
        // 添加操作提示
        const ghostHint = document.createElement('div');
        ghostHint.className = 'ghost-hint';
        ghostHint.style.cssText = `
            font-size: 11px;
            color: #888;
            border-top: 1px solid #ddd;
            padding-top: 6px;
            text-align: center;
        `;
        ghostHint.textContent = '點擊接受建議，或按 Tab 鍵';
        
        ghostContainer.appendChild(suggestionText);
        ghostContainer.appendChild(ghostHint);
        
        // 計算顯示位置 - 在光標附近
        document.body.appendChild(ghostContainer);
        const containerRect = ghostContainer.getBoundingClientRect();
        
        let left = rect.left + window.scrollX;
        let top = rect.bottom + window.scrollY + 10;
        
        // 檢查邊界並調整位置
        if (left + containerRect.width > window.innerWidth) {
            left = window.innerWidth - containerRect.width - 10;
        }
        
        if (top + containerRect.height > window.innerHeight + window.scrollY) {
            top = rect.top + window.scrollY - containerRect.height - 10;
        }
        
        if (left < 0) left = 10;
        if (top < 0) top = rect.bottom + window.scrollY + 10;
        
        ghostContainer.style.left = left + 'px';
        ghostContainer.style.top = top + 'px';
        
        // 添加事件處理
        suggestionText.addEventListener('mouseenter', () => {
            suggestionText.style.backgroundColor = '#e3f2fd';
        });
        
        suggestionText.addEventListener('mouseleave', () => {
            suggestionText.style.backgroundColor = 'transparent';
        });
        
        suggestionText.addEventListener('click', () => {
            this.acceptGhost();
        });
        
        // 存儲引用
        this.currentGhostContainer = ghostContainer;
        
        console.log('Ghost建議顯示完成，位置:', { left, top });
    }
    
    /**
     * 轉換Markdown語法為HTML（適用於WYSIWYG編輯器）
     */
    convertMarkdownToHtml(markdown) {
        if (!markdown) return '';
        
        let html = markdown;
        
        // 轉換粗體 **text** -> <strong>text</strong>
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // 轉換斜體 *text* -> <em>text</em>
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        // 轉換行內代碼 `code` -> <code>code</code>
        html = html.replace(/`(.*?)`/g, '<code>$1</code>');
        
        // 轉換連結 [text](url) -> <a href="url">text</a>
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
        
        // 轉換換行符為<br>
        html = html.replace(/\n/g, '<br>');
        
        // 轉換標題（簡單處理）
        html = html.replace(/^### (.*$)/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.*$)/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.*$)/gm, '<h1>$1</h1>');
        
        return html;
    }
    
    /**
     * 接受Ghost建議
     */
    acceptGhost() {
        console.log('acceptGhost被調用，ghostText:', this.ghostText);
        if (!this.ghostText) {
            console.log('沒有ghostText，退出');
            return;
        }
        
        try {
            // 如果有保存的光標位置，嘗試恢復
            if (this.savedRange) {
                console.log('恢復保存的光標位置');
                const selection = window.getSelection();
                selection.removeAllRanges();
                
                // 檢查保存的range是否還有效
                try {
                    selection.addRange(this.savedRange);
                } catch (e) {
                    console.log('保存的range無效，使用編輯器末尾:', e);
                    // 如果保存的range無效，將光標設置到編輯器末尾
                    const range = document.createRange();
                    range.selectNodeContents(this.editor);
                    range.collapse(false);
                    selection.addRange(range);
                }
            } else {
                console.log('沒有保存的光標位置，使用當前位置');
            }
            
            // 插入Ghost文字
            console.log('開始插入內容:', this.ghostText);
            this.insertContentDirect(this.ghostText);
            
            // 清除Ghost
            this.clearGhost();
            
            // 顯示成功提示
            this.showNotification('Ghost建議已插入', 'success');
            console.log('Ghost插入完成');
            
        } catch (error) {
            console.error('acceptGhost出錯:', error);
            this.showNotification('插入失敗: ' + error.message, 'error');
        }
    }
    
    /**
     * 直接插入內容（更穩健的方法）
     */
    insertContentDirect(content) {
        console.log('insertContentDirect被調用，content:', content);
        
        if (!this.editor) {
            console.log('沒有editor，退出');
            return;
        }
        
        const selection = window.getSelection();
        let range;
        
        if (selection.rangeCount > 0) {
            range = selection.getRangeAt(0);
            console.log('使用當前選擇範圍');
        } else {
            // 如果沒有選擇範圍，創建一個在編輯器末尾的範圍
            range = document.createRange();
            range.selectNodeContents(this.editor);
            range.collapse(false);
            selection.removeAllRanges();
            selection.addRange(range);
            console.log('創建新的範圍在編輯器末尾');
        }
        
        try {
            // 確保range在編輯器內
            if (!this.editor.contains(range.commonAncestorContainer)) {
                console.log('range不在編輯器內，重新創建');
                range = document.createRange();
                range.selectNodeContents(this.editor);
                range.collapse(false);
                selection.removeAllRanges();
                selection.addRange(range);
            }
            
            // 刪除選中的內容（如果有）
            range.deleteContents();
            
            // 插入新內容
            if (content.includes('<') && content.includes('>')) {
                console.log('插入HTML內容');
                const fragment = document.createRange().createContextualFragment(content);
                range.insertNode(fragment);
            } else {
                console.log('插入純文字內容');
                const textNode = document.createTextNode(content);
                range.insertNode(textNode);
            }
            
            // 移動光標到插入內容的末尾
            range.collapse(false);
            selection.removeAllRanges();
            selection.addRange(range);
            
            // 觸發輸入事件
            this.editor.dispatchEvent(new Event('input', { bubbles: true }));
            
            // 更新預覽
            this.updatePreview();
            
            console.log('內容插入成功');
            
        } catch (error) {
            console.error('插入內容時出錯:', error);
            // 降級處理：直接在編輯器末尾添加內容
            console.log('降級處理：在編輯器末尾添加內容');
            if (content.includes('<') && content.includes('>')) {
                this.editor.insertAdjacentHTML('beforeend', ' ' + content);
            } else {
                this.editor.appendChild(document.createTextNode(' ' + content));
            }
            this.updatePreview();
        }
    }
    
    /**
     * 清除Ghost
     */
    clearGhost() {
        this.ghostText = '';
        this.savedRange = null;  // 清除保存的光標位置
        
        // 清除新的Ghost容器
        if (this.currentGhostContainer) {
            this.currentGhostContainer.remove();
            this.currentGhostContainer = null;
        }
        
        // 清除舊的Ghost覆蓋層
        if (this.ghostOverlay) {
            this.ghostOverlay.style.display = 'none';
            this.ghostOverlay.textContent = '';
        }
    }
    
    /**
     * 顯示AI命令選單
     */
    showAICommandMenu() {
        // 移除之前的選單
        this.hideAICommandMenu();
        
        // 獲取當前光標位置
        const selection = window.getSelection();
        if (!selection.rangeCount) return;
        
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        
        const commands = [
            { key: 'summary', label: '摘要', description: '生成內容重點摘要' },
            { key: 'outline', label: '大綱', description: '生成清晰的大綱結構' },
            { key: 'bullets', label: '條列', description: '整理為條列要點' },
            { key: 'qa', label: '問答', description: '萃取問答對' },
            { key: 'supplement', label: '內容補充', description: '延續撰寫補充內容' },
            { key: 'rewrite-formal', label: '重寫：正式', description: '改寫為正式表述' },
            { key: 'rewrite-brief', label: '重寫：精簡', description: '壓縮為精簡版本' },
            { key: 'abbr-explain', label: '縮寫詞解釋', description: '解釋文中縮寫詞' }
        ];
        
        // 創建選單容器
        const menu = document.createElement('div');
        menu.className = 'ai-command-menu';
        menu.style.cssText = `
            position: absolute;
            background: white;
            border: 2px solid #007bff;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            max-width: 280px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        `;
        
        // 添加標題
        const header = document.createElement('div');
        header.style.cssText = `
            padding: 8px 12px;
            background: #007bff;
            color: white;
            font-weight: bold;
            font-size: 14px;
            border-radius: 6px 6px 0 0;
        `;
        header.textContent = 'AI 命令選單';
        menu.appendChild(header);
        
        // 初始化選中索引
        this.currentMenuIndex = 0;
        this.menuItems = [];
        
        // 添加命令選項
        commands.forEach((cmd, index) => {
            const item = document.createElement('div');
            item.className = 'ai-command-item';
            item.style.cssText = `
                padding: 10px 12px;
                cursor: pointer;
                border-bottom: ${index < commands.length - 1 ? '1px solid #eee' : 'none'};
                transition: background-color 0.2s;
                ${index === 0 ? 'background-color: #f0f8ff;' : ''}
            `;
            
            item.innerHTML = `
                <div style="font-weight: 500; color: #333; font-size: 13px;">${cmd.label}</div>
                <div style="font-size: 11px; color: #666; margin-top: 2px;">${cmd.description}</div>
            `;
            
            // 存儲命令信息
            item.dataset.command = cmd.key;
            item.dataset.index = index;
            this.menuItems.push(item);
            
            // 鼠標懸停效果
            item.onmouseenter = () => {
                this.selectMenuItemByIndex(index);
            };
            
            // 點擊執行命令
            item.onclick = () => {
                this.executeAICommand(cmd.key);
                this.hideAICommandMenu();
            };
            
            menu.appendChild(item);
        });
        
        // 計算顯示位置 - 在光標附近
        document.body.appendChild(menu);
        const menuRect = menu.getBoundingClientRect();
        
        // 預設顯示在光標下方右側
        let left = rect.left + window.scrollX;
        let top = rect.bottom + window.scrollY + 5;
        
        // 檢查邊界並調整位置
        if (left + menuRect.width > window.innerWidth) {
            left = rect.right + window.scrollX - menuRect.width;
        }
        
        if (top + menuRect.height > window.innerHeight + window.scrollY) {
            top = rect.top + window.scrollY - menuRect.height - 5;
        }
        
        // 確保不會超出左邊界
        if (left < 0) {
            left = 10;
        }
        
        // 確保不會超出上邊界
        if (top < 0) {
            top = rect.bottom + window.scrollY + 5;
        }
        
        menu.style.left = left + 'px';
        menu.style.top = top + 'px';
        
        this.currentAIMenu = menu;
        
        // 添加鍵盤事件監聽
        this.setupMenuKeyboardHandlers();
    }
    
    /**
     * 設置選單鍵盤處理
     */
    setupMenuKeyboardHandlers() {
        this.menuKeyHandler = (e) => {
            if (!this.currentAIMenu) return;
            
            switch (e.key) {
                case 'Escape':
                    e.preventDefault();
                    this.hideAICommandMenu();
                    break;
                    
                case 'ArrowDown':
                    e.preventDefault();
                    this.selectMenuItemByIndex((this.currentMenuIndex + 1) % this.menuItems.length);
                    break;
                    
                case 'ArrowUp':
                    e.preventDefault();
                    this.selectMenuItemByIndex((this.currentMenuIndex - 1 + this.menuItems.length) % this.menuItems.length);
                    break;
                    
                case 'Enter':
                    e.preventDefault();
                    const selectedItem = this.menuItems[this.currentMenuIndex];
                    if (selectedItem) {
                        this.executeAICommand(selectedItem.dataset.command);
                        this.hideAICommandMenu();
                    }
                    break;
            }
        };
        
        document.addEventListener('keydown', this.menuKeyHandler);
    }
    
    /**
     * 選擇指定索引的選單項目
     */
    selectMenuItemByIndex(index) {
        if (!this.menuItems || index < 0 || index >= this.menuItems.length) return;
        
        // 清除之前的選中狀態
        this.menuItems.forEach(item => {
            item.style.backgroundColor = 'transparent';
        });
        
        // 設置新的選中狀態
        this.currentMenuIndex = index;
        this.menuItems[index].style.backgroundColor = '#f0f8ff';
    }
    
    /**
     * 隱藏AI命令選單
     */
    hideAICommandMenu() {
        if (this.currentAIMenu) {
            this.currentAIMenu.remove();
            this.currentAIMenu = null;
        }
        if (this.menuKeyHandler) {
            document.removeEventListener('keydown', this.menuKeyHandler);
            this.menuKeyHandler = null;
        }
        this.menuItems = null;
        this.currentMenuIndex = -1;
    }
    
    /**
     * 執行AI命令
     */
    async executeAICommand(command) {
        const content = this.getContent('text');
        if (!content.trim()) {
            this.showNotification('請先輸入一些內容', 'warning');
            return;
        }
        
        this.showNotification(`正在執行 ${command} 命令...`, 'info');
        
        try {
            const response = await fetch('/notes/ai/command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
                },
                body: JSON.stringify({
                    command: command,
                    content: content
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.result) {
                    // 在新行插入結果
                    this.insertContent('\n\n' + data.result);
                    this.showNotification('AI命令執行完成', 'success');
                } else {
                    this.showNotification('AI命令執行失敗', 'error');
                }
            } else {
                this.showNotification('AI服務暫時無法使用', 'error');
            }
        } catch (error) {
            console.error('AI命令執行錯誤:', error);
            this.showNotification('命令執行過程中發生錯誤', 'error');
        }
    }

    /**
     * 觸發Ghost建議
     */
    async triggerGhost() {
        console.log('triggerGhost方法被調用，ghostEnabled:', this.ghostEnabled);
        if (!this.ghostEnabled) {
            console.log('Ghost功能未啟用，返回');
            return;
        }
        
        try {
            // 獲取當前內容作為上下文
            const content = this.editor.textContent || this.editor.innerText || '';
            console.log('當前內容長度:', content.length, '內容:', content.substring(0, 50));
            
            // 如果內容太少，不觸發
            if (content.length < 10) {
                console.log('內容太少，不觸發Ghost建議');
                return;
            }
            
            console.log('準備發送Ghost請求');
            
            // 準備請求頭
            const headers = {
                'Content-Type': 'application/json'
            };
            
            // 添加CSRF token如果存在
            const csrfToken = document.querySelector('meta[name="csrf-token"]');
            if (csrfToken) {
                headers['X-CSRF-Token'] = csrfToken.getAttribute('content');
                console.log('已添加CSRF token');
            } else {
                console.log('未找到CSRF token');
            }
            
            // 呼叫Ghost API
            console.log('發送請求到:', '/notes/ai/ghost-suggestion');
            console.log('請求數據:', { context: content, mode: 'supplement' });
            
            const response = await fetch('/notes/ai/ghost-suggestion', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    context: content,
                    mode: 'supplement'
                })
            });
            
            console.log('收到響應，狀態:', response.status, response.statusText);
            
            if (response.ok) {
                const data = await response.json();
                console.log('Ghost響應數據:', data);
                if (data.success && data.suggestion) {
                    console.log('準備顯示Ghost建議:', data.suggestion);
                    this.displayGhost(data.suggestion);
                } else {
                    console.log('Ghost響應無建議或失敗');
                }
            } else {
                console.warn('Ghost請求失敗:', response.status);
                // 嘗試讀取錯誤響應
                try {
                    const errorData = await response.text();
                    console.error('錯誤詳情:', errorData);
                } catch (e) {
                    console.error('無法讀取錯誤響應:', e);
                }
            }
        } catch (error) {
            console.error('Ghost觸發錯誤:', error);
        }
    }
    
    /**
     * 切換Ghost模式
     */
    /**
     * 更新Ghost狀態
     */
    updateGhostStatus(status) {
        const statusEl = this.statusBar.querySelector('.ghost-status i');
        if (!statusEl) return;
        
        statusEl.className = 'fas fa-circle';
        switch (status) {
            case 'enabled':
            case 'ready':
                statusEl.classList.add('text-success');
                break;
            case 'disabled':
                statusEl.classList.add('text-secondary');
                break;
            case 'error':
                statusEl.classList.add('text-danger');
                break;
        }
    }
    
    /**
     * 更新LSP狀態
     */
    updateLSPStatus(status) {
        const statusEl = this.statusBar.querySelector('.lsp-status i');
        if (!statusEl) return;
        
        statusEl.className = 'fas fa-circle';
        switch (status) {
            case 'enabled':
            case 'ready':
                statusEl.classList.add('text-success');
                break;
            case 'disabled':
                statusEl.classList.add('text-secondary');
                break;
            case 'error':
                statusEl.classList.add('text-danger');
                break;
        }
    }
    
    /**
     * 取得游標附近內容
     */
    getContextAroundCursor(fullText, selection) {
        // 簡化版本，實際應該根據游標位置提取上下文
        const lines = fullText.split('\n');
        return lines.slice(-5).join('\n'); // 返回最後5行作為上下文
    }
    
    // ===================
    // 輔助方法
    // ===================
    
    /**
     * 觸發AI補完
     */
    async triggerAICompletion() {
        try {
            const content = this.getContent('text');
            const completion = await this.requestAICompletion(content);
            
            if (completion) {
                this.insertText(completion);
                this.showMessage('AI補完完成', 'success');
            }
            
        } catch (error) {
            console.error('AI補完失敗:', error);
            this.showMessage('AI補完失敗', 'error');
        }
    }
    
    /**
     * 請求AI補完
     */
    async requestAICompletion(content) {
        const response = await fetch('/notes/ai/completion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ content })
        });
        
        if (!response.ok) {
            throw new Error('AI補完請求失敗');
        }
        
        const data = await response.json();
        return data.completion;
    }
    
    /**
     * 更新工具列狀態
     */
    updateToolbarState() {
        // 更新格式化按鈕的活動狀態
        const commands = ['bold', 'italic', 'underline', 'strikethrough'];
        
        commands.forEach(command => {
            const btn = this.toolbar.querySelector(`[data-command="${command}"]`);
            if (btn) {
                const isActive = document.queryCommandState(command);
                btn.classList.toggle('active', isActive);
            }
        });
    }
    
    /**
     * 銷毀編輯器
     */
    destroy() {
        if (this.lspSocket) {
            this.lspSocket.close();
        }
        
        if (this.ghostScheduleTimer) {
            clearTimeout(this.ghostScheduleTimer);
        }
        
        this.eventHandlers.clear();
        
        if (this.container) {
            this.container.innerHTML = '';
        }
    }

    /**
     * 設定AI功能
     */
    setupAIFeatures() {
        this.setupAICommandButtons();
        this.setupAIPromptGeneration();
        this.setupAIAssistantToggle();
    }

    /**
     * 設定AI命令按鈕
     */
    setupAICommandButtons() {
        const aiButtons = document.querySelectorAll('.ai-cmd-btn');
        aiButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const command = e.target.getAttribute('data-command');
                this.executeAICommand(command);
            });
        });
    }

    /**
     * 設定AI Prompt生成
     */
    setupAIPromptGeneration() {
        const promptBtn = document.getElementById('generateFromPrompt');
        const promptInput = document.getElementById('aiPromptInput');

        if (promptBtn && promptInput) {
            promptBtn.addEventListener('click', () => {
                const prompt = promptInput.value.trim();
                if (prompt) {
                    this.generateFromPrompt(prompt);
                    promptInput.value = '';
                }
            });

            promptInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    promptBtn.click();
                }
            });
        }
    }

    /**
     * 設定AI助理切換
     */
    setupAIAssistantToggle() {
        const toggle = document.getElementById('aiAssistantToggle');
        if (toggle) {
            toggle.addEventListener('change', (e) => {
                this.aiAssistantEnabled = e.target.checked;
                if (this.aiAssistantEnabled) {
                    this.showNotification('AI助理已啟用', 'success');
                } else {
                    this.showNotification('AI助理已停用', 'info');
                }
            });
        }
    }

    /**
     * 執行AI命令
     */
    async executeAICommand(command) {
        const content = this.getContent();
        if (!content.trim()) {
            this.showNotification('請先輸入一些內容', 'warning');
            return;
        }

        this.showNotification('AI正在處理...', 'info');

        try {
            const response = await fetch('/notes/ai/command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.csrfToken || ''
                },
                body: JSON.stringify({
                    command: command,
                    content: content,
                    format: 'html'
                })
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    this.insertContent(result.generated_content);
                    this.showNotification('AI處理完成', 'success');
                } else {
                    this.showNotification('AI處理失敗: ' + result.error, 'error');
                }
            } else {
                this.showNotification('AI服務暫時無法使用', 'error');
            }
        } catch (error) {
            console.error('AI命令執行錯誤:', error);
            this.showNotification('AI處理過程中發生錯誤', 'error');
        }
    }

    /**
     * 從提示生成內容
     */
    async generateFromPrompt(prompt) {
        this.showNotification('AI正在根據提示生成內容...', 'info');

        try {
            const response = await fetch('/notes/ai/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    prompt: prompt,
                    format: 'html'
                })
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    this.insertContent(result.generated_content);
                    this.showNotification('內容生成完成', 'success');
                } else {
                    this.showNotification('內容生成失敗: ' + result.error, 'error');
                }
            } else {
                this.showNotification('AI服務暫時無法使用', 'error');
            }
        } catch (error) {
            console.error('AI生成錯誤:', error);
            this.showNotification('內容生成過程中發生錯誤', 'error');
        }
    }

    /**
     * 生成AI內容
     */
    async generateContent(prompt, type = 'general') {
        const headers = {
            'Content-Type': 'application/json'
        };
        
        // 添加CSRF token如果存在
        const csrfToken = document.querySelector('meta[name="csrf-token"]');
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken.getAttribute('content');
        }
        
        const response = await fetch('/notes/ai/generate', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                prompt: prompt,
                type: type
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`AI生成失敗: ${response.status} ${errorText}`);
        }
        
        const data = await response.json();
        return data.content;
    }

    /**
     * 完善內容
     */
    async completeContent(context) {
        const headers = {
            'Content-Type': 'application/json'
        };
        
        // 添加CSRF token如果存在
        const csrfToken = document.querySelector('meta[name="csrf-token"]');
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken.getAttribute('content');
        }
        
        const response = await fetch('/notes/ai/completion', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                context: context
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`內容完善失敗: ${response.status} ${errorText}`);
        }
        
        const data = await response.json();
        return data.content;
    }

    /**
     * 插入內容到編輯器
     */
    insertContent(content) {
        if (!this.editor) return;
        
        const selection = window.getSelection();
        if (selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            range.deleteContents();
            
            // 如果是HTML內容，直接插入
            if (content.includes('<') && content.includes('>')) {
                const fragment = document.createRange().createContextualFragment(content);
                range.insertNode(fragment);
            } else {
                // 純文字內容，創建文字節點
                const textNode = document.createTextNode(content);
                range.insertNode(textNode);
            }
            
            // 移動光標到插入內容的末尾
            range.collapse(false);
            selection.removeAllRanges();
            selection.addRange(range);
        } else {
            // 如果沒有選擇範圍，直接添加到編輯器末尾
            if (content.includes('<') && content.includes('>')) {
                this.editor.insertAdjacentHTML('beforeend', content);
            } else {
                this.editor.appendChild(document.createTextNode(content));
            }
        }
        
        // 觸發輸入事件以更新預覽
        this.updatePreview();
    }

    /**
     * 更新預覽
     */
    updatePreview() {
        // 如果存在全域的updatePreview函數，調用它
        if (typeof window.updatePreview === 'function') {
            window.updatePreview();
        } else {
            // 否則實現基本的預覽更新邏輯
            const previewContainer = document.getElementById('markdown-preview');
            if (previewContainer && this.editor) {
                const content = this.editor.innerHTML;
                if (typeof marked !== 'undefined') {
                    // 將HTML轉換為Markdown，然後再轉回HTML以保持一致性
                    const markdown = this.htmlToMarkdown(content);
                    previewContainer.innerHTML = marked.parse(markdown);
                } else {
                    previewContainer.innerHTML = content;
                }
            }
        }
        
        // 觸發語法高亮
        this.highlightCodeBlocks();
        
        // 為新插入的程式碼區塊綁定複製功能
        setTimeout(() => {
            if (window.CodeCopyManager) {
                window.CodeCopyManager.bindNewCodeBlocks();
            }
        }, 100);
    }

    /**
     * 高亮程式碼區塊
     */
    highlightCodeBlocks() {
        // 使用 Prism.js 進行語法高亮
        if (typeof Prism !== 'undefined') {
            // 對編輯器內的程式碼區塊進行高亮
            const codeBlocks = this.editor.querySelectorAll('pre code[class*="language-"]');
            codeBlocks.forEach(block => {
                Prism.highlightElement(block);
            });
            
            // 如果有預覽容器，也對其進行高亮
            const previewContainer = document.getElementById('markdown-preview');
            if (previewContainer) {
                const previewCodeBlocks = previewContainer.querySelectorAll('pre code[class*="language-"]');
                previewCodeBlocks.forEach(block => {
                    Prism.highlightElement(block);
                });
            }
        }
    }


}

// 全域暴露
window.WYSIWYGEditor = WYSIWYGEditor;

// 注意：不自動初始化，由模板負責初始化以避免重複實例
