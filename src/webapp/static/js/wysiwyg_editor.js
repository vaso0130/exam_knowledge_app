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
        this.container.innerHTML = `
            <div class="wysiwyg-editor" data-theme="${this.options.theme}">
                <!-- 工具列 -->
                <div class="editor-toolbar">
                    <div class="toolbar-group">
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
                        <input type="color" class="toolbar-color" data-command="foreColor" title="文字顏色" value="#000000">
                        <input type="color" class="toolbar-color" data-command="backColor" title="背景顏色" value="#ffffff">
                    </div>
                    
                    <div class="toolbar-group">
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
                    </div>
                    
                    <div class="toolbar-group">
                        <!-- 清單 -->
                        <button class="toolbar-btn" data-command="insertUnorderedList" title="無序清單">
                            <i class="fas fa-list-ul"></i>
                        </button>
                        <button class="toolbar-btn" data-command="insertOrderedList" title="有序清單">
                            <i class="fas fa-list-ol"></i>
                        </button>
                        <button class="toolbar-btn" data-command="outdent" title="減少縮排">
                            <i class="fas fa-outdent"></i>
                        </button>
                        <button class="toolbar-btn" data-command="indent" title="增加縮排">
                            <i class="fas fa-indent"></i>
                        </button>
                    </div>
                    
                    <div class="toolbar-group">
                        <!-- 插入功能 -->
                        <button class="toolbar-btn" data-command="insertImage" title="插入圖片">
                            <i class="fas fa-image"></i>
                        </button>
                        <button class="toolbar-btn" data-command="insertLink" title="插入連結">
                            <i class="fas fa-link"></i>
                        </button>
                        <button class="toolbar-btn" data-command="insertTable" title="插入表格">
                            <i class="fas fa-table"></i>
                        </button>
                        <button class="toolbar-btn" data-command="insertCode" title="程式碼區塊">
                            <i class="fas fa-code"></i>
                        </button>
                    </div>
                    
                    <div class="toolbar-group">
                        <!-- 手寫功能 -->
                        <button class="toolbar-btn" data-command="handwriting" title="手寫輸入">
                            <i class="fas fa-pen-fancy"></i>
                        </button>
                    </div>
                    
                    <div class="toolbar-group">
                        <!-- AI功能 -->
                        <button class="toolbar-btn ai-btn" data-command="aiComplete" title="AI智能補完">
                            <i class="fas fa-magic"></i>
                        </button>
                        <button class="toolbar-btn ghost-btn" data-command="toggleGhost" title="切換Ghost模式">
                            <i class="fas fa-ghost"></i>
                        </button>
                    </div>
                    
                    <div class="toolbar-group ml-auto">
                        <!-- 視圖切換 -->
                        <button class="toolbar-btn" data-command="togglePreview" title="預覽模式">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="toolbar-btn" data-command="toggleMarkdown" title="Markdown模式">
                            <i class="fab fa-markdown"></i>
                        </button>
                    </div>
                </div>
                
                <!-- 編輯區域 -->
                <div class="editor-content">
                    <div class="editor-main" contenteditable="true" 
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
            
            <!-- 手寫輸入模態框 -->
            <div class="modal fade" id="handwritingModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
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
                                        width="800" height="400">
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
                                取消
                            </button>
                            <button type="button" class="btn btn-primary" id="insertHandwriting">
                                <i class="fas fa-check me-1"></i>插入
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
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
            
            if (this.ghostEnabled) {
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
        
        const modal = document.getElementById('handwritingModal');
        const canvas = modal.querySelector('.handwriting-canvas');
        const insertBtn = modal.querySelector('#insertHandwriting');
        
        // 初始化手寫畫布
        this.handwritingCanvas = canvas;
        this.handwritingContext = canvas.getContext('2d');
        
        // 設置畫布樣式
        this.handwritingContext.lineWidth = 2;
        this.handwritingContext.lineCap = 'round';
        this.handwritingContext.lineJoin = 'round';
        this.handwritingContext.strokeStyle = '#000';
        
        // 手寫工具切換
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
        
        // 手寫繪製事件
        this.setupHandwritingDrawing();
        
        // 插入按鈕
        insertBtn.addEventListener('click', async () => {
            const mode = modal.querySelector('input[name="handwritingMode"]:checked').value;
            await this.insertHandwriting(mode);
            bootstrap.Modal.getInstance(modal).hide();
        });
    }
    
    /**
     * 設置手寫繪製
     */
    setupHandwritingDrawing() {
        const canvas = this.handwritingCanvas;
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
        });
        
        canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            if (!isDrawing) return;
            
            const currentPoint = this.getCanvasPoint(e.touches[0]);
            this.drawLine(lastPoint, currentPoint);
            lastPoint = currentPoint;
        });
        
        canvas.addEventListener('touchend', (e) => {
            e.preventDefault();
            isDrawing = false;
            lastPoint = null;
        });
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
                const imageUrl = await this.uploadImageFromDataUrl(dataUrl);
                this.insertImage(imageUrl);
                this.showMessage('手寫內容已插入為圖片', 'success');
            } catch (error) {
                console.error('圖片上傳失敗:', error);
                this.showMessage('圖片上傳失敗', 'error');
            }
        } else {
            // AI轉換為文字
            try {
                const text = await this.convertHandwritingToText(dataUrl);
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
                
            case 'toggleGhost':
                this.toggleGhost();
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
     * 插入表格
     */
    insertTable() {
        const rows = prompt('請輸入表格行數:', '3');
        const cols = prompt('請輸入表格列數:', '3');
        
        if (!rows || !cols) return;
        
        const rowCount = parseInt(rows);
        const colCount = parseInt(cols);
        
        if (rowCount < 1 || colCount < 1) return;
        
        let tableHTML = '<table border="1" style="border-collapse: collapse; width: 100%;">';
        
        // 創建標題行
        tableHTML += '<thead><tr>';
        for (let j = 0; j < colCount; j++) {
            tableHTML += '<th style="padding: 8px; border: 1px solid #ddd;">標題 ' + (j + 1) + '</th>';
        }
        tableHTML += '</tr></thead>';
        
        // 創建資料行
        tableHTML += '<tbody>';
        for (let i = 1; i < rowCount; i++) {
            tableHTML += '<tr>';
            for (let j = 0; j < colCount; j++) {
                tableHTML += '<td style="padding: 8px; border: 1px solid #ddd;">資料</td>';
            }
            tableHTML += '</tr>';
        }
        tableHTML += '</tbody></table><br>';
        
        document.execCommand('insertHTML', false, tableHTML);
    }
    
    /**
     * 插入程式碼區塊
     */
    insertCodeBlock() {
        const language = prompt('請輸入程式語言 (可選):', 'javascript');
        const codeHTML = `<pre><code class="language-${language || ''}">${'請在此輸入程式碼'}</code></pre><br>`;
        document.execCommand('insertHTML', false, codeHTML);
    }
    
    /**
     * 顯示圖片對話框
     */
    showImageDialog() {
        const url = prompt('請輸入圖片URL:');
        if (url) {
            this.insertImage(url);
        }
    }
    
    /**
     * 顯示連結對話框
     */
    showLinkDialog() {
        const url = prompt('請輸入連結URL:');
        if (url) {
            const text = prompt('請輸入連結文字:', url);
            if (text) {
                const linkHTML = `<a href="${url}" target="_blank">${text}</a>`;
                document.execCommand('insertHTML', false, linkHTML);
            }
        }
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
        img.alt = alt;
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
        const modal = new bootstrap.Modal(document.getElementById('handwritingModal'));
        modal.show();
    }
    
    /**
     * 處理鍵盤事件
     */
    handleKeydown(e) {
        // Tab鍵接受Ghost建議
        if (e.key === 'Tab' && this.ghostText) {
            e.preventDefault();
            this.acceptGhost();
            return;
        }
        
        // Esc鍵清除Ghost
        if (e.key === 'Escape' && this.ghostText) {
            this.clearGhost();
            return;
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
    }
    
    /**
     * HTML轉Markdown（改進版）
     */
    htmlToMarkdown(html) {
        if (window.markdownConverter) {
            return window.markdownConverter.htmlToMarkdown(html);
        }
        
        // 簡化版轉換（備用）
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        
        // 基本的HTML到Markdown轉換
        let markdown = html;
        
        // 標題
        markdown = markdown.replace(/<h([1-6])>(.*?)<\/h[1-6]>/gi, (match, level, content) => {
            const hashes = '#'.repeat(parseInt(level));
            return `${hashes} ${content.trim()}\n\n`;
        });
        
        // 粗體和斜體
        markdown = markdown.replace(/<strong>(.*?)<\/strong>/gi, '**$1**');
        markdown = markdown.replace(/<b>(.*?)<\/b>/gi, '**$1**');
        markdown = markdown.replace(/<em>(.*?)<\/em>/gi, '*$1*');
        markdown = markdown.replace(/<i>(.*?)<\/i>/gi, '*$1*');
        
        // 移除HTML標籤
        markdown = markdown.replace(/<[^>]*>/g, '');
        
        return markdown.trim();
    }
    
    /**
     * Markdown轉HTML（改進版）
     */
    markdownToHtml(markdown) {
        if (window.markdownConverter) {
            return window.markdownConverter.markdownToHtml(markdown);
        }
        
        // 如果有marked.js，使用它
        if (window.marked) {
            return window.marked.parse(markdown);
        }
        
        // 簡化版轉換（備用）
        let html = markdown;
        
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
        
        return html;
    }
    
    /**
     * 上傳圖片
     */
    async uploadImage(file) {
        const formData = new FormData();
        formData.append('image', file);
        
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
        const response = await fetch('/notes/upload-image-dataurl', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ image: dataUrl })
        });
        
        if (!response.ok) {
            throw new Error('圖片上傳失敗');
        }
        
        const data = await response.json();
        return data.url;
    }
    
    /**
     * 手寫轉文字
     */
    async convertHandwritingToText(dataUrl) {
        const response = await fetch('/notes/handwriting-to-text', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ image: dataUrl })
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
        if (!this.lspEnabled) return;
        
        try {
            // 連接LSP WebSocket
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/lsp`;
            
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
            
            // 請求Ghost建議
            const suggestion = await this.requestGhostSuggestion(context);
            
            if (suggestion && suggestion.trim()) {
                this.displayGhost(suggestion);
            }
            
        } catch (error) {
            console.error('Ghost更新失敗:', error);
        }
    }
    
    /**
     * 請求Ghost建議
     */
    async requestGhostSuggestion(context) {
        const response = await fetch('/notes/ai/ghost-suggestion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                context: context,
                mode: 'supplement'
            })
        });
        
        if (!response.ok) {
            throw new Error('Ghost請求失敗');
        }
        
        const data = await response.json();
        return data.suggestion;
    }
    
    /**
     * 顯示Ghost文字
     */
    displayGhost(text) {
        this.ghostText = text;
        
        if (this.ghostOverlay) {
            this.ghostOverlay.textContent = text;
            this.ghostOverlay.style.display = 'block';
            this.ghostOverlay.style.opacity = '0.5';
            this.ghostOverlay.style.color = '#999';
            this.ghostOverlay.style.fontStyle = 'italic';
        }
    }
    
    /**
     * 接受Ghost建議
     */
    acceptGhost() {
        if (!this.ghostText) return;
        
        this.insertText(this.ghostText);
        this.clearGhost();
    }
    
    /**
     * 清除Ghost
     */
    clearGhost() {
        this.ghostText = '';
        if (this.ghostOverlay) {
            this.ghostOverlay.style.display = 'none';
            this.ghostOverlay.textContent = '';
        }
    }
    
    /**
     * 切換Ghost模式
     */
    toggleGhost() {
        this.ghostEnabled = !this.ghostEnabled;
        
        const btn = this.toolbar.querySelector('[data-command="toggleGhost"]');
        if (btn) {
            btn.classList.toggle('active', this.ghostEnabled);
        }
        
        if (!this.ghostEnabled) {
            this.clearGhost();
        }
        
        this.updateGhostStatus(this.ghostEnabled ? 'enabled' : 'disabled');
    }
    
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
}

// 全域暴露
window.WYSIWYGEditor = WYSIWYGEditor;

// 自動初始化（如果有指定的容器）
document.addEventListener('DOMContentLoaded', () => {
    const editorContainer = document.getElementById('wysiwyg-editor-container');
    if (editorContainer) {
        window.wysiwygEditor = new WYSIWYGEditor('wysiwyg-editor-container');
    }
});
