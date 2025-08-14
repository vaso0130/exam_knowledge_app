/**
 * WYSIWYG編輯器的Markdown轉換工具
 * 提供HTML與Markdown之間的雙向轉換
 */

class MarkdownConverter {
    constructor() {
        // 初始化轉換器
        this.htmlToMarkdownRules = this.setupHtmlToMarkdownRules();
        this.markdownToHtmlRules = this.setupMarkdownToHtmlRules();
    }
    
    /**
     * 設置HTML到Markdown的轉換規則
     */
    setupHtmlToMarkdownRules() {
        return {
            // 標題
            h1: (node) => `# ${this.getTextContent(node)}\n\n`,
            h2: (node) => `## ${this.getTextContent(node)}\n\n`,
            h3: (node) => `### ${this.getTextContent(node)}\n\n`,
            h4: (node) => `#### ${this.getTextContent(node)}\n\n`,
            h5: (node) => `##### ${this.getTextContent(node)}\n\n`,
            h6: (node) => `###### ${this.getTextContent(node)}\n\n`,
            
            // 段落
            p: (node) => `${this.processInlineElements(node)}\n\n`,
            
            // 格式化
            strong: (node) => `**${this.getTextContent(node)}**`,
            b: (node) => `**${this.getTextContent(node)}**`,
            em: (node) => `*${this.getTextContent(node)}*`,
            i: (node) => `*${this.getTextContent(node)}*`,
            u: (node) => `<u>${this.getTextContent(node)}</u>`,
            del: (node) => `~~${this.getTextContent(node)}~~`,
            s: (node) => `~~${this.getTextContent(node)}~~`,
            
            // 程式碼
            code: (node) => `\`${this.getTextContent(node)}\``,
            pre: (node) => {
                const code = node.querySelector('code');
                if (code) {
                    const language = this.extractLanguage(code);
                    const content = this.getTextContent(code);
                    return `\`\`\`${language}\n${content}\n\`\`\`\n\n`;
                }
                return `\`\`\`\n${this.getTextContent(node)}\n\`\`\`\n\n`;
            },
            
            // 連結
            a: (node) => {
                const href = node.getAttribute('href') || '';
                const text = this.getTextContent(node);
                return `[${text}](${href})`;
            },
            
            // 圖片
            img: (node) => {
                const src = node.getAttribute('src') || '';
                const alt = node.getAttribute('alt') || '';
                const title = node.getAttribute('title') || '';
                if (title) {
                    return `![${alt}](${src} "${title}")`;
                }
                return `![${alt}](${src})`;
            },
            
            // 清單
            ul: (node) => this.processListItems(node, '-') + '\n',
            ol: (node) => this.processListItems(node, '1.') + '\n',
            li: (node) => '', // 由父元素處理
            
            // 引用
            blockquote: (node) => {
                const content = this.processChildren(node);
                return content.split('\n').map(line => 
                    line.trim() ? `> ${line}` : '>'
                ).join('\n') + '\n\n';
            },
            
            // 水平線
            hr: () => '---\n\n',
            
            // 表格
            table: (node) => this.processTable(node),
            
            // 換行
            br: () => '  \n',
            
            // 分隔符
            div: (node) => this.processChildren(node) + '\n',
            span: (node) => {
                // 檢查是否有顏色樣式
                const style = node.getAttribute('style');
                if (style && (style.includes('color') || style.includes('background'))) {
                    // 保留帶有顏色樣式的 span 標籤
                    const content = this.processInlineElements(node);
                    return `<span style="${style}">${content}</span>`;
                }
                // 沒有顏色樣式的 span 只處理內容
                return this.processInlineElements(node);
            }
        };
    }
    
    /**
     * 設置Markdown到HTML的轉換規則（如果不使用marked.js）
     */
    setupMarkdownToHtmlRules() {
        return {
            // 基本的Markdown到HTML轉換
            // 實際應用中建議使用marked.js或其他成熟的Markdown解析器
        };
    }
    
    /**
     * HTML轉Markdown
     */
    htmlToMarkdown(html) {
        if (!html || typeof html !== 'string') return '';
        
        // 創建臨時DOM
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        
        return this.processNode(tempDiv);
    }
    
    /**
     * Markdown轉HTML
     */
    markdownToHtml(markdown) {
        if (!markdown || typeof markdown !== 'string') return '';
        
        // 如果有marked.js，使用它
        if (window.marked) {
            return window.marked.parse(markdown);
        }
        
        // 否則使用簡化版轉換
        return this.simpleMarkdownToHtml(markdown);
    }
    
    /**
     * 處理DOM節點
     */
    processNode(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            return node.textContent || '';
        }
        
        if (node.nodeType !== Node.ELEMENT_NODE) {
            return '';
        }
        
        const tagName = node.tagName.toLowerCase();
        const rule = this.htmlToMarkdownRules[tagName];
        
        if (rule) {
            return rule(node);
        }
        
        // 預設：處理子元素
        return this.processChildren(node);
    }
    
    /**
     * 處理子元素
     */
    processChildren(node) {
        let result = '';
        for (let child of node.childNodes) {
            result += this.processNode(child);
        }
        return result;
    }
    
    /**
     * 處理行內元素
     */
    processInlineElements(node) {
        let result = '';
        
        for (let child of node.childNodes) {
            if (child.nodeType === Node.TEXT_NODE) {
                result += child.textContent || '';
            } else if (child.nodeType === Node.ELEMENT_NODE) {
                const tagName = child.tagName.toLowerCase();
                const rule = this.htmlToMarkdownRules[tagName];
                
                if (rule) {
                    result += rule(child);
                } else {
                    result += this.processInlineElements(child);
                }
            }
        }
        
        return result;
    }
    
    /**
     * 取得純文字內容
     */
    getTextContent(node) {
        return (node.textContent || '').trim();
    }
    
    /**
     * 處理清單項目
     */
    processListItems(listNode, marker) {
        let result = '';
        let counter = 1;
        
        for (let li of listNode.children) {
            if (li.tagName.toLowerCase() === 'li') {
                const content = this.processChildren(li).trim();
                const actualMarker = marker === '1.' ? `${counter}.` : marker;
                result += `${actualMarker} ${content}\n`;
                counter++;
            }
        }
        
        return result;
    }
    
    /**
     * 處理表格
     */
    processTable(tableNode) {
        let result = '';
        const rows = Array.from(tableNode.querySelectorAll('tr'));
        
        if (rows.length === 0) return '';
        
        // 處理標題行
        const headerRow = rows[0];
        const headerCells = Array.from(headerRow.children);
        const headers = headerCells.map(cell => this.getTextContent(cell));
        
        result += '| ' + headers.join(' | ') + ' |\n';
        result += '|' + headers.map(() => ' --- ').join('|') + '|\n';
        
        // 處理資料行
        for (let i = 1; i < rows.length; i++) {
            const row = rows[i];
            const cells = Array.from(row.children);
            const cellContents = cells.map(cell => this.getTextContent(cell));
            result += '| ' + cellContents.join(' | ') + ' |\n';
        }
        
        return result + '\n';
    }
    
    /**
     * 提取程式碼語言
     */
    extractLanguage(codeElement) {
        const className = codeElement.className || '';
        const match = className.match(/language-(\w+)/);
        return match ? match[1] : '';
    }
    
    /**
     * 簡化版Markdown到HTML轉換
     */
    simpleMarkdownToHtml(markdown) {
        let html = markdown;
        
        // 標題
        html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
        html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
        
        // 粗體和斜體
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        // 程式碼
        html = html.replace(/`(.*?)`/g, '<code>$1</code>');
        
        // 連結
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
        
        // 圖片
        html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1">');
        
        // 段落
        html = html.replace(/\n\n/g, '</p><p>');
        html = '<p>' + html + '</p>';
        
        // 清理空段落
        html = html.replace(/<p><\/p>/g, '');
        
        return html;
    }
    
    /**
     * 清理HTML（移除不必要的標籤和屬性）
     */
    cleanHtml(html) {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        
        // 移除不必要的屬性
        const elementsWithAttributes = tempDiv.querySelectorAll('*');
        elementsWithAttributes.forEach(element => {
            const allowedAttributes = this.getAllowedAttributes(element.tagName.toLowerCase());
            const attributesToRemove = [];
            
            for (let attr of element.attributes) {
                if (!allowedAttributes.includes(attr.name)) {
                    attributesToRemove.push(attr.name);
                }
            }
            
            attributesToRemove.forEach(attrName => {
                element.removeAttribute(attrName);
            });
        });
        
        return tempDiv.innerHTML;
    }
    
    /**
     * 取得允許的屬性列表
     */
    getAllowedAttributes(tagName) {
        const commonAttributes = ['id', 'class'];
        const specificAttributes = {
            'a': ['href', 'title', 'target'],
            'img': ['src', 'alt', 'title', 'width', 'height'],
            'code': ['class'], // for language highlighting
            'pre': ['class'],
            'table': ['border', 'cellpadding', 'cellspacing'],
            'td': ['colspan', 'rowspan', 'align'],
            'th': ['colspan', 'rowspan', 'align'],
        };
        
        return commonAttributes.concat(specificAttributes[tagName] || []);
    }
    
    /**
     * 格式化Markdown輸出
     */
    formatMarkdown(markdown) {
        // 移除多餘的空行
        markdown = markdown.replace(/\n{3,}/g, '\n\n');
        
        // 確保在標題前有空行
        markdown = markdown.replace(/([^\n])\n(#{1,6} )/g, '$1\n\n$2');
        
        // 確保在清單前有空行
        markdown = markdown.replace(/([^\n])\n([*\-+] )/g, '$1\n\n$2');
        markdown = markdown.replace(/([^\n])\n(\d+\. )/g, '$1\n\n$2');
        
        // 確保在引用塊前有空行
        markdown = markdown.replace(/([^\n])\n(> )/g, '$1\n\n$2');
        
        // 確保在程式碼塊前有空行
        markdown = markdown.replace(/([^\n])\n(```)/g, '$1\n\n$2');
        
        // 移除開頭和結尾的空行
        markdown = markdown.trim();
        
        return markdown;
    }
}

// 全域暴露
window.MarkdownConverter = MarkdownConverter;

// 建立全域實例
if (!window.markdownConverter) {
    window.markdownConverter = new MarkdownConverter();
}
