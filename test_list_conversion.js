// 獨立測試腳本
function testListConversion() {
    console.log('=== 開始測試列表轉換修復 ===');
    
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
    
    // 修復後的轉換函數
    function improvedHtmlToMarkdown(html) {
        let markdown = html;
        
        // 處理標題
        markdown = markdown.replace(/<h([1-6])[^>]*>(.*?)<\/h[1-6]>/gi, (match, level, content) => {
            const hashes = '#'.repeat(parseInt(level));
            return `\n${hashes} ${content.trim()}\n\n`;
        });
        
        // 處理粗體
        markdown = markdown.replace(/<strong[^>]*>(.*?)<\/strong>/gis, '**$1**');
        markdown = markdown.replace(/<b[^>]*>(.*?)<\/b>/gis, '**$1**');
        
        // 處理有序列表（修復版）
        markdown = markdown.replace(/<ol[^>]*>(.*?)<\/ol>/gis, (match, content) => {
            let counter = 1;
            return '\n' + content.replace(/<li[^>]*>(.*?)<\/li>/gi, (liMatch, liContent) => {
                // 處理列表項目內容，保留換行符
                let processedContent = liContent;
                
                // 處理嵌套的列表項目中的段落，轉換為換行
                processedContent = processedContent.replace(/<p[^>]*>(.*?)<\/p>/gis, '$1\n');
                
                // 處理 br 標籤
                processedContent = processedContent.replace(/<br[^>]*\/?>/gi, '\n');
                
                // 處理嵌套的無序列表
                processedContent = processedContent.replace(/<ul[^>]*>(.*?)<\/ul>/gis, (ulMatch, ulContent) => {
                    return '\n' + ulContent.replace(/<li[^>]*>(.*?)<\/li>/gi, (nestedLi, nestedContent) => {
                        let nestedProcessed = nestedContent.replace(/<p[^>]*>(.*?)<\/p>/gis, '$1\n');
                        nestedProcessed = nestedProcessed.replace(/<br[^>]*\/?>/gi, '\n');
                        
                        // 處理更深層的嵌套列表
                        nestedProcessed = nestedProcessed.replace(/<ul[^>]*>(.*?)<\/ul>/gis, (deepUlMatch, deepUlContent) => {
                            return '\n' + deepUlContent.replace(/<li[^>]*>(.*?)<\/li>/gi, (deepLi, deepContent) => {
                                let deepProcessed = deepContent.replace(/<p[^>]*>(.*?)<\/p>/gis, '$1\n');
                                deepProcessed = deepProcessed.replace(/<br[^>]*\/?>/gi, '\n');
                                return `    - ${deepProcessed.trim()}\n`;
                            });
                        });
                        
                        return `  - ${nestedProcessed.trim()}\n`;
                    });
                });
                
                const currentNumber = counter++;
                return `${currentNumber}. ${processedContent.trim()}\n`;
            }) + '\n';
        });
        
        // 處理段落
        markdown = markdown.replace(/<p[^>]*>(.*?)<\/p>/gis, (match, content) => {
            // 檢查這個段落是否在列表項目中（已經被處理過）
            if (content.trim().match(/^(\d+\.|-)/) || content.includes('  -') || content.includes('  1.')) {
                return content; // 保持不變，避免重複處理
            }
            return content.trim() + '\n\n';
        });
        
        // 移除其他HTML標籤
        markdown = markdown.replace(/<[^>]*>/g, '');
        
        // 清理多餘空行
        markdown = markdown.replace(/\n{3,}/g, '\n\n');
        markdown = markdown.trim();
        
        return markdown;
    }
    
    const result = improvedHtmlToMarkdown(testHTML);
    
    console.log('轉換結果:');
    console.log('='.repeat(50));
    console.log(result);
    console.log('='.repeat(50));
    
    // 驗證結果
    const lines = result.split('\n');
    const listItems = lines.filter(line => line.match(/^\d+\.\s/));
    const nestedItems = lines.filter(line => line.match(/^\s{2,}-\s/));
    const deepNestedItems = lines.filter(line => line.match(/^\s{4,}-\s/));
    
    console.log('驗證結果:');
    console.log(`- 總行數: ${lines.length}`);
    console.log(`- 主列表項目: ${listItems.length}`);
    console.log(`- 嵌套列表項目: ${nestedItems.length}`);
    console.log(`- 深層嵌套項目: ${deepNestedItems.length}`);
    
    // 檢查是否有適當的縮進
    const hasProperIndentation = nestedItems.every(item => item.startsWith('  -'));
    const hasDeepIndentation = deepNestedItems.every(item => item.startsWith('    -'));
    
    console.log(`- 縮進正確: ${hasProperIndentation}`);
    console.log(`- 深層縮進正確: ${hasDeepIndentation}`);
    
    // 檢查換行符是否保留
    const expectedContent = [
        '#### (二) 裝置安全與健康狀態監控',
        '1. **裝置識別與註冊**',
        '  - 所有嘗試連接企業資源的裝置',
        '2. **裝置健康狀態評估**',
        '  - 持續監控裝置的安全性狀態',
        '    - 作業系統和應用程式',
        '    - 防毒軟體或EDR代理程式',
        '    - 是否存在惡意軟體',
        '    - 是否符合企業的安全策略',
        '  - 不符合安全標準的裝置'
    ];
    
    const allExpectedFound = expectedContent.every(expected => 
        result.includes(expected.substring(0, 20))
    );
    
    console.log(`- 關鍵內容保留: ${allExpectedFound}`);
    
    if (hasProperIndentation && hasDeepIndentation && allExpectedFound) {
        console.log('✅ 測試通過！列表換行修復成功！');
        return true;
    } else {
        console.log('❌ 測試失敗！需要進一步調整。');
        return false;
    }
}

// 在瀏覽器控制台中運行測試
if (typeof window !== 'undefined') {
    window.testListConversion = testListConversion;
    console.log('測試函數已載入，請在控制台運行: testListConversion()');
} else {
    // Node.js 環境
    testListConversion();
}
