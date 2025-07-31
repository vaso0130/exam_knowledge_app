"""
Playwright 網頁爬取器
用於取代原有的 fetch_webpage 功能，提供更強大的網頁內容擷取能力
"""

import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from typing import Dict, List, Optional, Any
import re
import json
import logging

logger = logging.getLogger(__name__)

class PlaywrightScraper:
    """使用 Playwright 的進階網頁爬取器"""
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        初始化爬取器
        
        Args:
            headless: 是否使用無頭瀏覽器模式
            timeout: 頁面載入超時時間（毫秒）
        """
        self.headless = headless
        self.timeout = timeout
        self.browser = None
        self.context = None
        
    async def __aenter__(self):
        """異步上下文管理器進入"""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器退出"""
        await self.close()
        
    async def start(self):
        """啟動瀏覽器"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            logger.info("Playwright 瀏覽器已啟動")
        except Exception as e:
            logger.error(f"啟動 Playwright 瀏覽器失敗: {e}")
            raise
            
    async def close(self):
        """關閉瀏覽器"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
            logger.info("Playwright 瀏覽器已關閉")
        except Exception as e:
            logger.error(f"關閉 Playwright 瀏覽器失敗: {e}")
    
    async def scrape_webpage(self, url: str, query: str = "") -> Dict[str, Any]:
        """
        爬取網頁內容
        
        Args:
            url: 要爬取的網址
            query: 搜尋查詢（用於相關性篩選）
            
        Returns:
            包含網頁內容的字典
        """
        if not self.context:
            await self.start()
            
        page = None
        try:
            page = await self.context.new_page()
            
            # 設置超時
            page.set_default_timeout(self.timeout)
            
            # 訪問頁面
            logger.info(f"正在載入頁面: {url}")
            response = await page.goto(url, wait_until='domcontentloaded')
            
            if not response or response.status >= 400:
                raise Exception(f"頁面載入失敗，狀態碼: {response.status if response else 'None'}")
            
            # 等待頁面完全載入
            await page.wait_for_load_state('networkidle', timeout=10000)
            
            # 提取頁面資訊
            page_data = await self._extract_page_content(page)
            
            # 添加元資訊
            page_data.update({
                'url': url,
                'title': await page.title() or '',
                'query': query,
                'status': 'success'
            })
            
            logger.info(f"成功爬取頁面: {url}")
            return page_data
            
        except PlaywrightTimeoutError:
            logger.error(f"頁面載入超時: {url}")
            return {
                'url': url,
                'title': '',
                'content': '',
                'text_content': '',
                'tables': [],
                'images': [],
                'query': query,
                'status': 'timeout',
                'error': '頁面載入超時'
            }
        except Exception as e:
            logger.error(f"爬取頁面失敗 {url}: {e}")
            return {
                'url': url,
                'title': '',
                'content': '',
                'text_content': '',
                'tables': [],
                'images': [],
                'query': query,
                'status': 'error',
                'error': str(e)
            }
        finally:
            if page:
                await page.close()
    
    async def _extract_page_content(self, page) -> Dict[str, Any]:
        """提取頁面內容"""
        
        # 移除不需要的元素
        await self._remove_unwanted_elements(page)
        
        # 提取主要內容
        content = await self._extract_main_content(page)
        
        # 提取純文字內容
        text_content = await self._extract_text_content(page)
        
        # 提取表格
        tables = await self._extract_tables(page)
        
        # 提取圖片資訊
        images = await self._extract_images(page)
        
        return {
            'content': content,
            'text_content': text_content,
            'tables': tables,
            'images': images
        }
    
    async def _remove_unwanted_elements(self, page):
        """移除不需要的頁面元素"""
        unwanted_selectors = [
            'script',
            'style', 
            'noscript',
            '.advertisement',
            '.ads',
            '.ad',
            '.sidebar',
            '.footer',
            '.header-ads',
            '.popup',
            '.modal',
            '.cookie-notice',
            '[class*="ad-"]',
            '[id*="ad-"]',
            '[class*="ads-"]',
            '[id*="ads-"]'
        ]
        
        for selector in unwanted_selectors:
            try:
                await page.evaluate(f'''
                    document.querySelectorAll("{selector}").forEach(el => el.remove());
                ''')
            except:
                pass  # 忽略錯誤，繼續移除其他元素
    
    async def _extract_main_content(self, page) -> str:
        """提取主要內容（HTML 格式）"""
        
        # 嘗試常見的內容容器選擇器
        content_selectors = [
            'main',
            'article', 
            '.content',
            '.main-content',
            '.post-content',
            '.article-content',
            '.entry-content',
            '#content',
            '#main',
            '.container .row',  # Bootstrap 佈局
            '.content-wrapper'
        ]
        
        for selector in content_selectors:
            try:
                content = await page.evaluate(f'''
                    const element = document.querySelector("{selector}");
                    return element ? element.innerHTML : null;
                ''')
                if content and len(content.strip()) > 100:  # 確保內容不為空
                    return content
            except:
                continue
        
        # 如果沒有找到主要內容容器，提取 body 內容
        try:
            content = await page.evaluate('''
                const body = document.querySelector("body");
                return body ? body.innerHTML : "";
            ''')
            return content or ""
        except:
            return ""
    
    async def _extract_text_content(self, page) -> str:
        """提取純文字內容"""
        try:
            # 提取所有可見文字
            text_content = await page.evaluate('''
                () => {
                    // 移除不需要的元素
                    const unwantedElements = document.querySelectorAll('script, style, noscript, .ad, .ads, .advertisement');
                    unwantedElements.forEach(el => el.remove());
                    
                    // 提取主要內容區域的文字
                    const contentSelectors = ['main', 'article', '.content', '.main-content', '#content'];
                    for (const selector of contentSelectors) {
                        const element = document.querySelector(selector);
                        if (element) {
                            return element.innerText || element.textContent;
                        }
                    }
                    
                    // 回退到 body
                    return document.body.innerText || document.body.textContent || "";
                }
            ''')
            
            # 清理文字內容
            if text_content:
                # 移除多餘的空白和換行
                text_content = re.sub(r'\n\s*\n', '\n\n', text_content)
                text_content = re.sub(r'[ \t]+', ' ', text_content)
                return text_content.strip()
                
            return ""
        except Exception as e:
            logger.error(f"提取文字內容失敗: {e}")
            return ""
    
    async def _extract_tables(self, page) -> List[Dict[str, Any]]:
        """提取表格資訊"""
        try:
            tables_data = await page.evaluate('''
                () => {
                    const tables = Array.from(document.querySelectorAll('table'));
                    
                    function convertTableToMarkdown(headers, rows) {
                        if (!rows || rows.length === 0) return '';
                        
                        let markdown = '';
                        
                        // 如果有表頭
                        if (headers && headers.length > 0) {
                            markdown += '| ' + headers.join(' | ') + ' |\\n';
                            markdown += '| ' + headers.map(() => '---').join(' | ') + ' |\\n';
                        }
                        
                        // 表格內容
                        rows.forEach(row => {
                            if (row && row.length > 0) {
                                markdown += '| ' + row.join(' | ') + ' |\\n';
                            }
                        });
                        
                        return markdown;
                    }
                    
                    return tables.map((table, index) => {
                        const rows = Array.from(table.querySelectorAll('tr'));
                        const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent.trim());
                        const data = rows.map(row => {
                            const cells = Array.from(row.querySelectorAll('td, th'));
                            return cells.map(cell => cell.textContent.trim());
                        }).filter(row => row.length > 0);
                        
                        return {
                            index: index,
                            headers: headers,
                            rows: data,
                            markdown: convertTableToMarkdown(headers, data)
                        };
                    });
                }
            ''')
            
            return tables_data or []
        except Exception as e:
            logger.error(f"提取表格失敗: {e}")
            return []
    
    async def _extract_images(self, page) -> List[Dict[str, str]]:
        """提取圖片資訊"""
        try:
            images_data = await page.evaluate('''
                () => {
                    const images = Array.from(document.querySelectorAll('img'));
                    return images.map(img => ({
                        src: img.src || '',
                        alt: img.alt || '',
                        title: img.title || '',
                        width: img.naturalWidth || img.width || 0,
                        height: img.naturalHeight || img.height || 0
                    })).filter(img => img.src && !img.src.startsWith('data:'));
                }
            ''')
            
            return images_data or []
        except Exception as e:
            logger.error(f"提取圖片失敗: {e}")
            return []

# 便利函數
async def scrape_single_page(url: str, query: str = "", headless: bool = True) -> Dict[str, Any]:
    """
    爬取單一網頁的便利函數
    
    Args:
        url: 要爬取的網址
        query: 搜尋查詢
        headless: 是否使用無頭模式
        
    Returns:
        網頁內容字典
    """
    async with PlaywrightScraper(headless=headless) as scraper:
        return await scraper.scrape_webpage(url, query)

# 與現有 fetch_webpage 工具兼容的函數
async def fetch_webpage_playwright(urls: List[str], query: str = "") -> str:
    """
    與現有 fetch_webpage 工具兼容的函數
    
    Args:
        urls: 要爬取的網址列表
        query: 搜尋查詢
        
    Returns:
        格式化的網頁內容字串
    """
    results = []
    
    async with PlaywrightScraper() as scraper:
        for url in urls:
            try:
                page_data = await scraper.scrape_webpage(url, query)
                
                if page_data['status'] == 'success':
                    # 格式化輸出以匹配原有工具的格式
                    formatted_content = f"# {page_data['title']}\n\n"
                    
                    # 添加表格（如果有）
                    if page_data['tables']:
                        formatted_content += "## 表格資訊\n\n"
                        for i, table in enumerate(page_data['tables']):
                            if table['markdown']:
                                formatted_content += f"### 表格 {i+1}\n\n{table['markdown']}\n\n"
                    
                    # 添加主要內容
                    if page_data['text_content']:
                        formatted_content += page_data['text_content']
                    
                    # 添加圖片資訊（如果有）
                    if page_data['images']:
                        formatted_content += "\n\n## 圖片資訊\n\n"
                        for img in page_data['images']:
                            if img['alt'] or img['title']:
                                formatted_content += f"![{img['alt'] or img['title']}]({img['src']})\n"
                    
                    results.append(f"URL: {url}\n{formatted_content}")
                else:
                    results.append(f"URL: {url}\n錯誤: {page_data.get('error', '未知錯誤')}")
                    
            except Exception as e:
                results.append(f"URL: {url}\n錯誤: {str(e)}")
    
    return "\n\n" + "="*80 + "\n\n".join(results)

if __name__ == "__main__":
    # 測試用例
    async def test():
        url = "https://turingcerts.com/zh/information-security/"
        result = await scrape_single_page(url, "資訊安全 CIA 三要素")
        print(f"標題: {result['title']}")
        print(f"狀態: {result['status']}")
        print(f"表格數量: {len(result['tables'])}")
        print(f"圖片數量: {len(result['images'])}")
        if result['tables']:
            print("第一個表格:")
            print(result['tables'][0]['markdown'])
    
    # 執行測試
    # asyncio.run(test())
