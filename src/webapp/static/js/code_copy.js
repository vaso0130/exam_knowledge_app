/**
 * 全域程式碼複製功能
 * 為所有頁面的程式碼區塊添加複製按鈕
 */

class CodeCopyManager {
    constructor() {
        this.init();
    }

    init() {
        // 等待 DOM 載入完成
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.bindAllCodeBlocks());
        } else {
            this.bindAllCodeBlocks();
        }
    }

    /**
     * 為所有程式碼區塊添加複製按鈕
     */
    bindAllCodeBlocks() {
        // 尋找所有的程式碼區塊
        const codeBlocks = document.querySelectorAll('pre code, .code-block, pre');
        
        codeBlocks.forEach(block => {
            // 避免重複添加複製按鈕
            if (block.parentElement.querySelector('.code-copy-btn')) {
                return;
            }

            // 只為有實際程式碼內容的區塊添加複製按鈕
            const codeText = this.getCodeText(block);
            if (codeText.trim().length === 0) {
                return;
            }

            this.addCopyButton(block);
        });
    }

    /**
     * 獲取程式碼區塊的文字內容
     */
    getCodeText(block) {
        // 如果是 code 標籤在 pre 內，使用 code 的內容
        if (block.tagName === 'CODE' && block.parentElement.tagName === 'PRE') {
            return block.textContent || block.innerText;
        }
        // 如果是 pre 標籤，檢查是否有 code 子元素
        else if (block.tagName === 'PRE') {
            const codeElement = block.querySelector('code');
            if (codeElement) {
                return codeElement.textContent || codeElement.innerText;
            }
            return block.textContent || block.innerText;
        }
        // 其他情況
        return block.textContent || block.innerText;
    }

    /**
     * 為程式碼區塊添加複製按鈕
     */
    addCopyButton(block) {
        // 確定容器元素（通常是 pre 標籤）
        let container = block;
        if (block.tagName === 'CODE' && block.parentElement.tagName === 'PRE') {
            container = block.parentElement;
        }

        // 確保容器有相對定位
        const containerStyles = window.getComputedStyle(container);
        if (containerStyles.position === 'static') {
            container.style.position = 'relative';
        }

        // 創建複製按鈕
        const copyBtn = document.createElement('button');
        copyBtn.className = 'code-copy-btn';
        copyBtn.innerHTML = '複製';
        copyBtn.title = '複製程式碼';
        
        // 設定按鈕樣式
        this.setCopyButtonStyles(copyBtn);

        // 添加點擊事件
        copyBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.copyCode(block, copyBtn);
        });

        // 將按鈕添加到容器
        container.appendChild(copyBtn);
    }

    /**
     * 設定複製按鈕的樣式
     */
    setCopyButtonStyles(button) {
        button.style.position = 'absolute';
        button.style.top = '8px';
        button.style.right = '8px';
        button.style.padding = '4px 8px';
        button.style.fontSize = '12px';
        button.style.backgroundColor = '#6c757d';
        button.style.color = 'white';
        button.style.border = 'none';
        button.style.borderRadius = '4px';
        button.style.cursor = 'pointer';
        button.style.zIndex = '1000';
        button.style.opacity = '0.7';
        button.style.transition = 'opacity 0.2s';

        // 懸停效果
        button.addEventListener('mouseenter', () => {
            button.style.opacity = '1';
            button.style.backgroundColor = '#5a6268';
        });

        button.addEventListener('mouseleave', () => {
            button.style.opacity = '0.7';
            button.style.backgroundColor = '#6c757d';
        });
    }

    /**
     * 複製程式碼到剪貼簿
     */
    async copyCode(block, button) {
        const codeText = this.getCodeText(block);
        
        try {
            // 使用現代 Clipboard API
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(codeText);
            } else {
                // 備用方法：使用 textarea
                this.fallbackCopyMethod(codeText);
            }

            // 顯示成功反饋
            this.showCopySuccess(button);
        } catch (error) {
            console.error('複製失敗:', error);
            // 嘗試備用方法
            try {
                this.fallbackCopyMethod(codeText);
                this.showCopySuccess(button);
            } catch (fallbackError) {
                console.error('備用複製方法也失敗:', fallbackError);
                this.showCopyError(button);
            }
        }
    }

    /**
     * 備用複製方法（適用於舊瀏覽器）
     */
    fallbackCopyMethod(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.left = '-999999px';
        textarea.style.top = '-999999px';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        
        const result = document.execCommand('copy');
        document.body.removeChild(textarea);
        
        if (!result) {
            throw new Error('execCommand copy failed');
        }
    }

    /**
     * 顯示複製成功的反饋
     */
    showCopySuccess(button) {
        const originalText = button.innerHTML;
        button.innerHTML = '已複製!';
        button.style.backgroundColor = '#28a745';
        
        setTimeout(() => {
            button.innerHTML = originalText;
            button.style.backgroundColor = '#6c757d';
        }, 2000);
    }

    /**
     * 顯示複製錯誤的反饋
     */
    showCopyError(button) {
        const originalText = button.innerHTML;
        button.innerHTML = '複製失敗';
        button.style.backgroundColor = '#dc3545';
        
        setTimeout(() => {
            button.innerHTML = originalText;
            button.style.backgroundColor = '#6c757d';
        }, 2000);
    }

    /**
     * 手動綁定新添加的程式碼區塊
     * 當動態添加程式碼時調用此方法
     */
    bindNewCodeBlocks() {
        this.bindAllCodeBlocks();
    }
}

// 自動初始化
const codeCopyManager = new CodeCopyManager();

// 全域暴露，讓其他腳本可以手動觸發綁定
window.CodeCopyManager = codeCopyManager;
