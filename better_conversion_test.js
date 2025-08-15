// 更好的 HTML 到 Markdown 轉換器
function betterHtmlToMarkdown(html) {
    if (!html || typeof html !== 'string') return '';
    
    // 創建臨時DOM來解析HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    
    return processNode(tempDiv).trim();
}

function processNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
        return node.textContent || '';
    }
    
    if (node.nodeType !== Node.ELEMENT_NODE) {
        return '';
    }
    
    const tagName = node.tagName.toLowerCase();
    
    switch (tagName) {
        case 'h1': return `# ${getTextContent(node)}\n\n`;
        case 'h2': return `## ${getTextContent(node)}\n\n`;
        case 'h3': return `### ${getTextContent(node)}\n\n`;
        case 'h4': return `#### ${getTextContent(node)}\n\n`;
        case 'h5': return `##### ${getTextContent(node)}\n\n`;
        case 'h6': return `###### ${getTextContent(node)}\n\n`;
        
        case 'p':
            return processChildren(node) + '\n\n';
            
        case 'strong':
        case 'b':
            return `**${getTextContent(node)}**`;
            
        case 'em':
        case 'i':
            return `*${getTextContent(node)}*`;
            
        case 'br':
            return '\n';
            
        case 'ol':
            return processOrderedList(node) + '\n';
            
        case 'ul':
            return processUnorderedList(node) + '\n';
            
        case 'li':
            // 這個不應該被直接調用，因為列表處理會處理 li
            return processChildren(node);
            
        default:
            return processChildren(node);
    }
}

function processChildren(node) {
    let result = '';
    for (let child of node.childNodes) {
        result += processNode(child);
    }
    return result;
}

function getTextContent(node) {
    return (node.textContent || '').trim();
}

function processOrderedList(olNode, indent = '') {
    let result = '\n';
    let counter = 1;
    
    for (let child of olNode.children) {
        if (child.tagName.toLowerCase() === 'li') {
            result += processListItem(child, `${counter}.`, indent);
            counter++;
        }
    }
    
    return result;
}

function processUnorderedList(ulNode, indent = '') {
    let result = '\n';
    
    for (let child of ulNode.children) {
        if (child.tagName.toLowerCase() === 'li') {
            result += processListItem(child, '-', indent);
        }
    }
    
    return result;
}

function processListItem(liNode, marker, indent = '') {
    let content = '';
    let hasNestedContent = false;
    
    for (let child of liNode.childNodes) {
        if (child.nodeType === Node.TEXT_NODE) {
            content += child.textContent || '';
        } else if (child.nodeType === Node.ELEMENT_NODE) {
            const tagName = child.tagName.toLowerCase();
            
            if (tagName === 'ol') {
                hasNestedContent = true;
                content += processOrderedList(child, indent + '  ');
            } else if (tagName === 'ul') {
                hasNestedContent = true;
                content += processUnorderedList(child, indent + '  ');
            } else if (tagName === 'p') {
                // 段落在列表項目中
                const pContent = processChildren(child);
                if (content.trim()) {
                    content += '\n' + indent + '  ' + pContent.trim();
                } else {
                    content += pContent.trim();
                }
            } else if (tagName === 'br') {
                content += '\n' + indent + '  ';
            } else {
                content += processNode(child);
            }
        }
    }
    
    // 分割內容成行，並適當縮進
    const lines = content.split('\n');
    let result = `${indent}${marker} ${lines[0].trim()}\n`;
    
    for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (line) {
            if (line.startsWith(indent + '  ')) {
                // 這是嵌套內容，保持原樣
                result += line + '\n';
            } else if (line.match(/^\s*(\d+\.|-)/) && hasNestedContent) {
                // 這是嵌套列表項目
                result += line + '\n';
            } else if (line) {
                // 續行內容，需要縮進
                result += `${indent}  ${line}\n`;
            }
        }
    }
    
    return result;
}

// 測試函數
function testBetterConversion() {
    console.log('=== 測試改進的轉換器 ===');
    
    const testHTML = `
<h4>(二) 裝置安全與健康狀態監控（Device Security and Health Monitoring）</h4>

<p>在零信任環境中，任何嘗試連接資源的裝置都必須被視為潛在威脅，並經過嚴格的健康檢查。</p>

<ol>
<li><strong>裝置識別與註冊</strong>：
<ul>
<li>所有嘗試連接企業資源的裝置（筆電、手機、平板、IoT設備等）都必須被唯一識別、註冊並納入管理。這通常透過行動裝置管理（MDM）、統一端點管理（UEM）或端點偵測與回應（EDR）工具實現。</li>
</ul>
</li>
<li><strong>裝置健康狀態評估</strong>：
<ul>
<li>持續監控裝置的安全性狀態，包括：
<ul>
<li>作業系統和應用程式是否已安裝最新安全補丁。</li>
<li>防毒軟體或EDR代理程式是否正常運行且定義檔最新。</li>
<li>是否存在惡意軟體、配置錯誤或異常行為。</li>
<li>是否符合企業的安全策略（如：是否越獄/Root）。</li>
</ul>
</li>
<li>不符合安全標準的裝置將被自動隔離、限制存取權限，或引導至修復流程，直至其安全狀態恢復正常。</li>
</ul>
</li>
</ol>
    `;
    
    // 在瀏覽器環境中模擬 DOM
    if (typeof window === 'undefined') {
        // Node.js 環境，使用 jsdom
        try {
            const { JSDOM } = require('jsdom');
            const dom = new JSDOM();
            global.document = dom.window.document;
            global.Node = dom.window.Node;
        } catch (e) {
            console.log('需要安裝 jsdom 來在 Node.js 中運行此測試');
            console.log('npm install jsdom');
            return;
        }
    }
    
    const result = betterHtmlToMarkdown(testHTML);
    
    console.log('轉換結果:');
    console.log('='.repeat(50));
    console.log(result);
    console.log('='.repeat(50));
    
    // 驗證結果
    const lines = result.split('\n');
    const listItems = lines.filter(line => line.match(/^\d+\.\s/));
    const nestedItems = lines.filter(line => line.match(/^\s{2}-\s/));
    const deepNestedItems = lines.filter(line => line.match(/^\s{4}-\s/));
    
    console.log('驗證結果:');
    console.log(`- 總行數: ${lines.length}`);
    console.log(`- 主列表項目: ${listItems.length}`);
    console.log(`- 嵌套列表項目: ${nestedItems.length}`);
    console.log(`- 深層嵌套項目: ${deepNestedItems.length}`);
    
    return result;
}

if (typeof window !== 'undefined') {
    window.testBetterConversion = testBetterConversion;
    window.betterHtmlToMarkdown = betterHtmlToMarkdown;
} else {
    testBetterConversion();
}
