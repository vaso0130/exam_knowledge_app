import tkinter as tk
from tkinter import font as tkFont
import markdown
import re
from typing import Dict, List, Any
from html import unescape

class MarkdownRenderer:
    """Markdown 渲染器，將 Markdown 文本轉換為 Tkinter Text widget 中的格式化內容"""
    
    def __init__(self, text_widget: tk.Text):
        self.text_widget = text_widget
        self.setup_tags()
    
    def setup_tags(self):
        """設定文字標籤樣式"""
        # 基礎字體
        default_font = tkFont.nametofont("TkDefaultFont")
        
        # 標題字體
        self.text_widget.tag_configure("h1", font=(default_font.cget("family"), 20, "bold"), foreground="#1e3a8a")
        self.text_widget.tag_configure("h2", font=(default_font.cget("family"), 18, "bold"), foreground="#2563eb")
        self.text_widget.tag_configure("h3", font=(default_font.cget("family"), 16, "bold"), foreground="#3b82f6")
        self.text_widget.tag_configure("h4", font=(default_font.cget("family"), 14, "bold"), foreground="#60a5fa")
        
        # 強調文字
        self.text_widget.tag_configure("bold", font=(default_font.cget("family"), default_font.cget("size"), "bold"))
        self.text_widget.tag_configure("italic", font=(default_font.cget("family"), default_font.cget("size"), "italic"))
        
        # 程式碼
        code_font = ("Courier New", default_font.cget("size"))
        self.text_widget.tag_configure("code", font=code_font, background="#f3f4f6", foreground="#374151")
        self.text_widget.tag_configure("code_block", font=code_font, background="#f9fafb", foreground="#374151", lmargin1=20, lmargin2=20)
        
        # 引用
        self.text_widget.tag_configure("blockquote", lmargin1=20, lmargin2=20, foreground="#6b7280", background="#f9fafb")
        
        # 列表
        self.text_widget.tag_configure("list", lmargin1=20, lmargin2=40)
        
        # 分隔線
        self.text_widget.tag_configure("hr", background="#e5e7eb", relief="sunken", borderwidth=1)
        
        # 表格
        self.text_widget.tag_configure("table_header", 
                                      font=(default_font.cget("family"), default_font.cget("size"), "bold"), 
                                      background="#4a90e2",
                                      foreground="white",
                                      lmargin1=10, lmargin2=10)
        self.text_widget.tag_configure("table_cell", 
                                      background="#f8f9fa",
                                      foreground="#333333",
                                      lmargin1=10, lmargin2=10,
                                      font=(default_font.cget("family"), default_font.cget("size")))
        
        # 標籤
        self.text_widget.tag_configure("tag", font=code_font, background="#dbeafe", foreground="#1e40af")
        
        # 狀態指示器
        self.text_widget.tag_configure("status_completed", foreground="#059669")
        self.text_widget.tag_configure("status_pending", foreground="#d97706")
    
    def render_markdown(self, markdown_text: str):
        """渲染 Markdown 文本到 Text widget"""
        # 清空現有內容
        self.text_widget.delete("1.0", tk.END)
        
        # 分行處理
        lines = markdown_text.split('\n')
        
        current_pos = "1.0"
        in_code_block = False
        code_block_content = []
        
        for line in lines:
            if line.strip().startswith('```'):
                if in_code_block:
                    # 結束程式碼區塊
                    if code_block_content:
                        code_text = '\n'.join(code_block_content) + '\n'
                        self.text_widget.insert(tk.END, code_text, "code_block")
                    code_block_content = []
                    in_code_block = False
                else:
                    # 開始程式碼區塊
                    in_code_block = True
                continue
            
            if in_code_block:
                code_block_content.append(line)
                continue
            
            # 處理標題
            if line.startswith('#'):
                level = 0
                for char in line:
                    if char == '#':
                        level += 1
                    else:
                        break
                
                title_text = line[level:].strip() + '\n'
                if level <= 4:
                    self.text_widget.insert(tk.END, title_text, f"h{level}")
                else:
                    self.text_widget.insert(tk.END, title_text, "bold")
            
            # 處理引用
            elif line.startswith('>'):
                quote_text = line[1:].strip() + '\n'
                self.text_widget.insert(tk.END, quote_text, "blockquote")
            
            # 處理分隔線
            elif line.strip() == '---':
                self.text_widget.insert(tk.END, '─' * 50 + '\n', "hr")
            
            # 處理列表（改進版本，正確處理格式）
            elif (line.strip().startswith(('- ', '* ', '+ ')) or 
                  re.match(r'^\d+\.\s+', line.strip()) or
                  re.match(r'^\*\s+', line.strip())):
                self._render_list_item(line)
            
            # 處理表格 - 改進檢測邏輯
            elif ('|' in line and 
                  line.count('|') >= 2 and
                  (line.strip().startswith('|') or '|' in line.strip())):
                self._render_table_row(line)
            
            # 處理普通段落
            else:
                self._render_paragraph(line)
            
            # 如果不是列表項目，添加換行
            if not (line.strip().startswith(('- ', '* ', '+ ')) or 
                    re.match(r'^\d+\.\s+', line.strip()) or
                    re.match(r'^\*\s+', line.strip())):
                pass  # 換行已在各處理函數中添加
    
    def _render_list_item(self, line: str):
        """渲染列表項目，正確處理格式"""
        stripped = line.strip()
        indent_level = (len(line) - len(line.lstrip())) // 4  # 修正縮排計算
        
        # 提取列表標記和內容
        if stripped.startswith('*   '):
            # 特殊處理：*   開頭的項目（多空格）
            content = stripped[4:]  # 移除 "*   "
            bullet = "• "
        elif re.match(r'^\*\s+', stripped):
            # 一般的 * 開頭
            content = re.sub(r'^\*\s+', '', stripped)
            bullet = "• "
        elif re.match(r'^[\-\+]\s+', stripped):
            # - 或 + 開頭
            content = re.sub(r'^[\-\+]\s+', '', stripped)
            bullet = "• "
        elif re.match(r'^\d+\.\s+', stripped):
            # 數字列表
            match = re.match(r'^(\d+\.)\s+', stripped)
            bullet = match.group(1) + " "
            content = re.sub(r'^\d+\.\s+', '', stripped)
        else:
            content = stripped
            bullet = "• "
        
        # 插入縮排和項目標記
        indent = "    " * indent_level  # 使用 4 個空格縮排
        self.text_widget.insert(tk.END, indent + bullet, "list")
        
        # 處理內容中的格式
        self._render_inline_formatting(content)
        self.text_widget.insert(tk.END, '\n')
    
    def _render_inline_formatting(self, text: str):
        """處理行內格式（粗體、斜體等）"""
        if not text:
            return
        
        # 先處理粗體 **text**，避免與列表的 * 衝突
        current_pos = 0
        bold_pattern = r'\*\*([^*]+?)\*\*'
        
        for match in re.finditer(bold_pattern, text):
            # 插入前面的普通文字
            if match.start() > current_pos:
                plain_text = text[current_pos:match.start()]
                self._render_simple_text(plain_text)
            
            # 插入粗體文字
            bold_text = match.group(1)
            self.text_widget.insert(tk.END, bold_text, "bold")
            current_pos = match.end()
        
        # 插入剩餘的文字
        if current_pos < len(text):
            remaining_text = text[current_pos:]
            self._render_simple_text(remaining_text)
    
    def _render_simple_text(self, text: str):
        """處理簡單文字格式"""
        if not text:
            return
        
        # 處理行內程式碼 `code`
        current_pos = 0
        code_pattern = r'`([^`]+?)`'
        
        for match in re.finditer(code_pattern, text):
            # 插入前面的普通文字
            if match.start() > current_pos:
                self.text_widget.insert(tk.END, text[current_pos:match.start()])
            
            # 插入程式碼
            code_text = match.group(1)
            self.text_widget.insert(tk.END, code_text, "code")
            current_pos = match.end()
        
        # 插入剩餘的普通文字
        if current_pos < len(text):
            self.text_widget.insert(tk.END, text[current_pos:])
    
    def _render_paragraph(self, line: str):
        """渲染段落"""
        if line.strip():
            self._render_inline_formatting(line)
            self.text_widget.insert(tk.END, '\n')
        else:
            # 空行
            self.text_widget.insert(tk.END, '\n')
    
    def _render_table_row(self, line: str):
        """渲染表格行（處理各種表格格式）"""
        stripped_line = line.strip()
        
        # 處理各種表格格式
        if stripped_line.startswith('|') and stripped_line.endswith('|'):
            # 標準格式: |cell1|cell2|cell3|
            cells = [cell.strip() for cell in stripped_line[1:-1].split('|')]
        elif stripped_line.startswith('|'):
            # 格式: |cell1|cell2|cell3
            cells = [cell.strip() for cell in stripped_line[1:].split('|')]
        elif stripped_line.endswith('|'):
            # 格式: cell1|cell2|cell3|
            cells = [cell.strip() for cell in stripped_line[:-1].split('|')]
        elif '|' in stripped_line:
            # 格式: cell1|cell2|cell3
            cells = [cell.strip() for cell in stripped_line.split('|')]
        else:
            return  # 不是表格格式
        
        # 過濾空單元格
        cells = [cell for cell in cells if cell.strip()]
        
        if not cells:
            return
        
        # 檢查是否為表格分隔線（如 |---|---|）
        if all(cell.replace('-', '').replace(':', '').replace(' ', '').strip() == '' for cell in cells):
            # 這是表格分隔線，繪製一條分隔線
            self.text_widget.insert(tk.END, '═' * 80 + '\n', "hr")
            return
        
        # 確定單元格寬度（根據內容動態調整）
        max_cell_len = max(len(cell) for cell in cells) if cells else 10
        cell_width = max(12, min(25, max_cell_len + 4))  # 限制寬度範圍
        
        # 檢查是否為表頭
        current_content = self.text_widget.get("1.0", "end-1c")
        lines = current_content.split('\n')
        
        # 如果這是第一個表格行，或者前面沒有表格行，就當作表頭
        is_header = not any('│' in line for line in lines[-3:])  # 檢查最近3行
        
        # 構建表格行
        row_parts = []
        for cell in cells:
            # 填充單元格到固定寬度，確保對齊
            if len(cell) > cell_width - 2:
                # 如果內容太長，截斷並加省略號
                padded_cell = cell[:cell_width - 5] + "..."
            else:
                padded_cell = cell.ljust(cell_width - 2)
            row_parts.append(f" {padded_cell} ")
        
        # 組合完整行
        row_text = "│" + "│".join(row_parts) + "│"
        
        # 插入行內容並設定樣式
        if is_header:
            self.text_widget.insert(tk.END, row_text + '\n', "table_header")
            # 為表頭添加下劃線
            separator_parts = ['─' * cell_width for _ in cells]
            separator_line = "┼".join(separator_parts)
            self.text_widget.insert(tk.END, f"├{separator_line}┤\n", "hr")
        else:
            self.text_widget.insert(tk.END, row_text + '\n', "table_cell")


class MarkdownText(tk.Frame):
    """包含 Markdown 渲染功能的文字框組件"""
    
    def __init__(self, parent, **kwargs):
        # 從 kwargs 中提取字體設定，避免傳遞給 Frame
        font_config = kwargs.pop('font', None)
        height = kwargs.pop('height', None)  # 也提取 height 參數
        
        # 初始化 Frame
        super().__init__(parent, **kwargs)
        
        # 設定預設字體
        if font_config is None:
            # 使用系統預設字體
            default_font = tkFont.nametofont("TkDefaultFont")
            font_config = (default_font.cget("family"), 11)
        
        # 創建滾動文字框
        text_kwargs = {
            'wrap': tk.WORD,
            'font': font_config,
            'bg': "white",
            'fg': "black",
            'padx': 10,
            'pady': 10
        }
        
        if height is not None:
            text_kwargs['height'] = height
            
        self.text_widget = tk.Text(self, **text_kwargs)
        
        scrollbar = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)
        
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 創建渲染器
        self.renderer = MarkdownRenderer(self.text_widget)
        
        # 禁用編輯
        self.text_widget.config(state=tk.DISABLED)
    
    def set_markdown(self, markdown_text: str):
        """設定 Markdown 內容"""
        self.text_widget.config(state=tk.NORMAL)
        self.renderer.render_markdown(markdown_text)
        self.text_widget.config(state=tk.DISABLED)
    
    def clear(self):
        """清空內容"""
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.config(state=tk.DISABLED)
