import tkinter as tk
from tkinter import font as tkFont, scrolledtext
import re
from typing import Optional, Callable, List
import platform


class MarkdownText(tk.Frame):
    """
    混合式 Markdown 渲染器：
    - 將 Markdown 表格數據傳遞給回呼函式，由外部元件（如 Treeview）渲染
    - 渲染非表格內容
    - 保持文字可選取和複製功能
    """
    
    def __init__(self, parent, table_callback: Optional[Callable[[List[str], List[List[str]]], None]] = None, **kwargs):
        # 從 kwargs 中提取字體設定
        font_config = kwargs.pop('font', None)
        height = kwargs.pop('height', None)
        
        super().__init__(parent, **kwargs)
        
        self.table_callback = table_callback
        
        # 設定預設字體
        if font_config is None:
            default_font = tkFont.nametofont("TkDefaultFont")
            font_config = (default_font.cget("family"), 11)
        
        # 創建可選取的文字框
        text_kwargs = {
            'wrap': tk.WORD,
            'font': font_config,
            'bg': "white",
            'fg': "black",
            'padx': 10,
            'pady': 10,
            'selectbackground': '#0078d4',
            'selectforeground': 'white',
            'borderwidth': 0,
            'highlightthickness': 0
        }
        
        if height is not None:
            text_kwargs['height'] = height
            
        self.text_widget = scrolledtext.ScrolledText(self, **text_kwargs)
        self.text_widget.pack(fill=tk.BOTH, expand=True)
        
        # 設定文字標籤樣式
        self.setup_text_tags()
        
        # 禁用編輯，但保留選取功能
        self.text_widget.config(state=tk.DISABLED)
    
    def setup_text_tags(self):
        """設定文字標籤樣式"""
        # 獲取預設字體
        default_font = tkFont.nametofont("TkDefaultFont")
        default_size = default_font.cget("size")
        default_family = default_font.cget("family")
        
        # 標題樣式
        self.text_widget.tag_configure("h1", font=(default_family, 20, "bold"), foreground="#1e3a8a", spacing1=10, spacing3=10)
        self.text_widget.tag_configure("h2", font=(default_family, 18, "bold"), foreground="#2563eb", spacing1=8, spacing3=8)
        self.text_widget.tag_configure("h3", font=(default_family, 16, "bold"), foreground="#3b82f6", spacing1=6, spacing3=6)
        self.text_widget.tag_configure("h4", font=(default_family, 14, "bold"), foreground="#60a5fa", spacing1=4, spacing3=4)
        
        # 文字格式
        self.text_widget.tag_configure("bold", font=(default_family, default_size, "bold"))
        self.text_widget.tag_configure("italic", font=(default_family, default_size, "italic"))
        
        # 程式碼樣式
        code_font_family = "Menlo" if platform.system() == "Darwin" else "Consolas" if platform.system() == "Windows" else "monospace"
        code_font = (code_font_family, default_size)
        self.text_widget.tag_configure("code", font=code_font, background="#f3f4f6", foreground="#374151", relief="solid", borderwidth=1)
        self.text_widget.tag_configure("code_block", font=code_font, background="#f9fafb", foreground="#374151", lmargin1=20, lmargin2=20, spacing1=5, spacing3=5, relief="solid", borderwidth=1)
        
        # 引用樣式
        self.text_widget.tag_configure("blockquote", lmargin1=20, lmargin2=20, foreground="#6b7280", background="#f9fafb", relief="solid", borderwidth=1, spacing1=5, spacing3=5)
        
        # 列表樣式
        self.text_widget.tag_configure("list", lmargin1=20, lmargin2=40)
        
        # 分隔線樣式
        self.text_widget.tag_configure("hr", overstrike=True, foreground="#e5e7eb", spacing1=10, spacing3=10)

    def set_markdown(self, markdown_text: str):
        """設定 Markdown 內容"""
        try:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.delete("1.0", tk.END)
            
            # 總是在開始時清除外部表格
            if self.table_callback:
                self.table_callback([], [])
            
            # 檢查是否包含表格
            if '|' in markdown_text and self._has_table(markdown_text):
                self._render_content_with_tables(markdown_text)
            else:
                self._render_simple_markdown(markdown_text)
            
            self.text_widget.config(state=tk.DISABLED)
            
        except Exception as e:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.delete("1.0", tk.END)
            self.text_widget.insert("1.0", f"渲染錯誤: {str(e)}\n\n原始內容:\n{markdown_text}")
            self.text_widget.config(state=tk.DISABLED)
    
    def _has_table(self, text: str) -> bool:
        """檢查文字是否包含 Markdown 表格"""
        lines = text.split('\n')
        # 檢查是否有 `|---|` 樣式的分隔線
        has_separator = any(re.match(r'^\s*\|?(\s*:?-+:?\s*\|)+', line) for line in lines)
        # 檢查是否有帶 `|` 的內容行
        has_content_row = any(line.count('|') >= 2 for line in lines)
        return has_separator and has_content_row
    
    def _render_content_with_tables(self, markdown_text: str):
        """渲染包含表格的 Markdown"""
        lines = markdown_text.split('\n')
        
        in_code_block, code_block_content = False, []
        in_table, table_lines = False, []
        
        for line in lines:
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                if not in_code_block and code_block_content:
                    self._insert_code_block('\n'.join(code_block_content))
                    code_block_content = []
                continue
            
            if in_code_block:
                code_block_content.append(line)
                continue
            
            is_table_line = '|' in line
            
            if is_table_line and not in_table:
                # 可能是表格的開始
                in_table = True
                table_lines.append(line)
            elif is_table_line and in_table:
                table_lines.append(line)
            elif not is_table_line and in_table:
                # 表格結束
                self._process_table(table_lines)
                table_lines = []
                in_table = False
                self._render_line(line)
            else:
                self._render_line(line)
        
        if in_table and table_lines:
            self._process_table(table_lines)

    def _process_table(self, table_lines: list):
        """解析表格並透過回呼傳遞數據"""
        if not self.table_callback:
            self.text_widget.insert(tk.END, "[偵測到表格，但未設定渲染器]\n\n", "italic")
            return

        headers, data_rows = [], []
        separator_found = False
        
        for line in table_lines:
            stripped_line = line.strip()
            if not stripped_line: continue

            if re.match(r'^\s*\|?(\s*:?-+:?\s*\|)+', stripped_line):
                separator_found = True
                continue

            if stripped_line.startswith('|'):
                stripped_line = stripped_line[1:]
            if stripped_line.endswith('|'):
                stripped_line = stripped_line[:-1]
            
            cells = [cell.strip() for cell in stripped_line.split('|')]

            if not separator_found:
                headers = cells
            else:
                data_rows.append(cells)
        
        if headers or data_rows:
            self.table_callback(headers, data_rows)
            if data_rows:
                placeholder = f"[表格呈現在下方，共 {len(data_rows)} 筆資料]\n"
                self.text_widget.insert(tk.END, placeholder, ("italic", "blockquote"))
                self.text_widget.insert(tk.END, "\n")

    def _render_simple_markdown(self, markdown_text: str):
        """渲染簡單的 Markdown（不包含表格）"""
        lines = markdown_text.split('\n')
        in_code_block, code_block_content = False, []
        
        for line in lines:
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                if not in_code_block and code_block_content:
                    self._insert_code_block('\n'.join(code_block_content))
                    code_block_content = []
                continue
            
            if in_code_block:
                code_block_content.append(line)
                continue
            
            self._render_line(line)
    
    def _render_line(self, line: str):
        """渲染單行內容"""
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            title_text = line[level:].strip() + '\n'
            self.text_widget.insert(tk.END, title_text, f"h{min(level, 4)}")
        elif line.startswith('>'):
            self.text_widget.insert(tk.END, line[1:].strip() + '\n', "blockquote")
        elif line.strip() in ('---', '***', '___'):
            self.text_widget.insert(tk.END, ' ' * 80 + '\n', "hr")
        elif re.match(r'^\s*([-*+]|\d+\.)\s+', line):
            self._render_list_item(line)
        else:
            self._render_inline_formatting(line.strip())
            self.text_widget.insert(tk.END, '\n')

    def _render_list_item(self, line: str):
        """渲染列表項目"""
        match = re.match(r'^(\s*)([-*+]|\d+\.)\s+(.*)', line)
        if not match: return
        
        indent, bullet, content = match.groups()
        
        self.text_widget.insert(tk.END, indent + bullet + " ", "list")
        self._render_inline_formatting(content)
        self.text_widget.insert(tk.END, '\n')
    
    def _render_inline_formatting(self, text: str):
        """處理行內格式（粗體、斜體、程式碼）"""
        parts = re.split(r'(\*\*.*?\*\*|`.*?`)', text)
        for part in filter(None, parts):
            if part.startswith('**') and part.endswith('**'):
                self.text_widget.insert(tk.END, part[2:-2], "bold")
            elif part.startswith('`') and part.endswith('`'):
                self.text_widget.insert(tk.END, part[1:-1], "code")
            else:
                self.text_widget.insert(tk.END, part)
    
    def _insert_code_block(self, code_text: str):
        """插入程式碼區塊"""
        self.text_widget.insert(tk.END, code_text + '\n\n', "code_block")

    def clear(self):
        """清空內容"""
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.config(state=tk.DISABLED)
        if self.table_callback:
            self.table_callback([], [])
