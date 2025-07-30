import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import customtkinter as ctk
from typing import Dict, Any, List, Optional
import threading
import asyncio
import os
import json
from datetime import datetime

# 導入 markdown 渲染器
from .markdown_renderer import MarkdownText

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg as FigureCanvasTkinter
except ImportError:
    FigureCanvasTkinter = None

# 設定 CustomTkinter 主題
ctk.set_appearance_mode("light")  # "system", "light", "dark"
ctk.set_default_color_theme("blue")  # "blue", "green", "dark-blue"

class ModernGUI:
    def __init__(self, content_processor, db_manager):
        self.content_processor = content_processor
        self.db_manager = db_manager
        self.db = db_manager  # 別名，方便使用
        
        # 建立主視窗
        self.root = ctk.CTk()
        self.root.title("考題/知識整理系統")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)
        
        # 設定視窗圖示（如果有的話）
        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass
        
        # 初始化變數
        self.current_documents = []
        self.current_questions = []  # 新增：當前題庫
        self.current_subject = "全部"
        self.selected_tags = []
        self.current_view = "documents"  # 當前檢視：documents 或 questions
        self.current_preview_data = None  # 用於重新載入預覽
        
        # 建立介面
        self.create_widgets()
        self.load_initial_data()
        
        # 設定拖放功能
        self.setup_drag_drop()
    
    def create_widgets(self):
        """建立所有介面元件"""
        
        # 主要容器
        self.main_container = ctk.CTkFrame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 建立頂部工具列
        self.create_toolbar()
        
        # 建立主要內容區域
        self.create_main_content()
        
        # 建立狀態列
        self.create_status_bar()
    
    def create_toolbar(self):
        """建立頂部工具列"""
        toolbar = ctk.CTkFrame(self.main_container)
        toolbar.pack(fill="x", padx=5, pady=(5, 10))
        
        # 輸入區域
        input_frame = ctk.CTkFrame(toolbar)
        input_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        # URL/文字輸入框
        self.input_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="拖放檔案、貼上網址或輸入文字內容...",
            font=ctk.CTkFont(size=14),
            height=40
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        
        # 處理按鈕
        self.process_btn = ctk.CTkButton(
            input_frame,
            text="處理",
            command=self.process_input,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            width=100
        )
        self.process_btn.pack(side="right", padx=10, pady=10)
        
        # 右側按鈕組
        button_frame = ctk.CTkFrame(toolbar)
        button_frame.pack(side="right")
        
        # 選擇檔案按鈕
        self.file_btn = ctk.CTkButton(
            button_frame,
            text="選擇檔案",
            command=self.select_file,
            font=ctk.CTkFont(size=12),
            height=35,
            width=100
        )
        self.file_btn.pack(side="left", padx=5, pady=10)
        
        # 匯出按鈕
        self.export_btn = ctk.CTkButton(
            button_frame,
            text="匯出資料",
            command=self.export_data,
            font=ctk.CTkFont(size=12),
            height=35,
            width=100
        )
        self.export_btn.pack(side="left", padx=5, pady=10)
        
        # 統計按鈕
        self.stats_btn = ctk.CTkButton(
            button_frame,
            text="統計資料",
            command=self.show_statistics,
            font=ctk.CTkFont(size=12),
            height=35,
            width=100
        )
        self.stats_btn.pack(side="left", padx=5, pady=10)
        
        # 檢視切換按鈕
        self.view_switch_btn = ctk.CTkButton(
            button_frame,
            text="切換到題庫",
            command=self.switch_view,
            font=ctk.CTkFont(size=12),
            height=35,
            width=100
        )
        self.view_switch_btn.pack(side="left", padx=5, pady=10)
    
    def create_main_content(self):
        """建立主要內容區域"""
        # 主要內容框架
        content_frame = ctk.CTkFrame(self.main_container)
        content_frame.pack(fill="both", expand=True, padx=5)
        
        # 左側面板（科目樹和篩選）
        self.create_left_panel(content_frame)
        
        # 右側面板（文件列表和預覽）
        self.create_right_panel(content_frame)
    
    def create_left_panel(self, parent):
        """建立左側面板"""
        left_panel = ctk.CTkFrame(parent)
        left_panel.pack(side="left", fill="y", padx=(0, 5))
        left_panel.configure(width=300)
        
        # 標題
        title_label = ctk.CTkLabel(
            left_panel,
            text="科目與篩選",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_label.pack(pady=(10, 5))
        
        # 科目選擇
        subject_frame = ctk.CTkFrame(left_panel)
        subject_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            subject_frame,
            text="科目:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.subject_var = tk.StringVar(value="全部")
        self.subject_combo = ctk.CTkComboBox(
            subject_frame,
            variable=self.subject_var,
            values=["全部", "資料結構", "資訊管理", "資通網路與資訊安全", "資料庫應用"],
            command=self.on_subject_change,
            font=ctk.CTkFont(size=12)
        )
        self.subject_combo.pack(fill="x", padx=10, pady=(0, 10))
        
        # 搜尋區域
        search_frame = ctk.CTkFrame(left_panel)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            search_frame,
            text="搜尋:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            placeholder_text="輸入關鍵字搜尋...",
            font=ctk.CTkFont(size=12)
        )
        self.search_entry.pack(fill="x", padx=10, pady=(0, 5))
        self.search_entry.bind("<KeyRelease>", self.on_search_change)
        
        self.search_btn = ctk.CTkButton(
            search_frame,
            text="搜尋",
            command=self.search_documents,
            height=30,
            font=ctk.CTkFont(size=11)
        )
        self.search_btn.pack(fill="x", padx=10, pady=(0, 10))
        
        # 知識庫管理區域
        kb_frame = ctk.CTkFrame(left_panel)
        kb_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            kb_frame,
            text="知識庫管理:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        # 知識庫操作按鈕
        kb_buttons_frame = ctk.CTkFrame(kb_frame)
        kb_buttons_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.export_btn = ctk.CTkButton(
            kb_buttons_frame,
            text="📤 匯出",
            command=self.export_knowledge,
            height=30,
            font=ctk.CTkFont(size=10)
        )
        self.export_btn.pack(side="left", padx=(0, 5), fill="x", expand=True)
        
        self.import_btn = ctk.CTkButton(
            kb_buttons_frame,
            text="📥 匯入",
            command=self.import_knowledge,
            height=30,
            font=ctk.CTkFont(size=10)
        )
        self.import_btn.pack(side="right", padx=(5, 0), fill="x", expand=True)
        
        # 快速統計
        quick_stats_frame = ctk.CTkFrame(kb_frame)
        quick_stats_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.quick_stats_label = ctk.CTkLabel(
            quick_stats_frame,
            text="📚 文件: 0 | 📝 題目: 0",
            font=ctk.CTkFont(size=10)
        )
        self.quick_stats_label.pack(pady=5)
        
        # 標籤篩選區域
        tags_frame = ctk.CTkFrame(left_panel)
        tags_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkLabel(
            tags_frame,
            text="標籤篩選:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        # 標籤列表（使用 Scrollable Frame）
        self.tags_scrollable = ctk.CTkScrollableFrame(tags_frame, height=200)
        self.tags_scrollable.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.tag_vars = {}  # 儲存標籤選擇狀態
        
        # 統計資訊
        stats_frame = ctk.CTkFrame(left_panel)
        stats_frame.pack(fill="x", padx=10, pady=(5, 10))
        
        ctk.CTkLabel(
            stats_frame,
            text="統計資訊",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(pady=(10, 5))
        
        self.stats_label = ctk.CTkLabel(
            stats_frame,
            text="載入中...",
            font=ctk.CTkFont(size=10),
            justify="left"
        )
        self.stats_label.pack(pady=(0, 10), padx=10)
    
    def create_right_panel(self, parent):
        """建立右側面板"""
        right_panel = ctk.CTkFrame(parent)
        right_panel.pack(side="right", fill="both", expand=True)
        
        # 右側面板分為上下兩部分
        # 上部：文件列表
        list_frame = ctk.CTkFrame(right_panel)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        
        # 文件列表標題
        list_title = ctk.CTkLabel(
            list_frame,
            text="文件列表",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        list_title.pack(pady=(10, 5))
        
        # 文件列表
        self.create_document_list(list_frame)
        
        # 添加操作按鈕
        self.create_action_buttons(list_frame)
        
        # 下部：預覽區域
        preview_frame = ctk.CTkFrame(right_panel)
        preview_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        preview_frame.configure(height=500)  # 增加預覽區域高度
        
        # 預覽標題
        preview_title = ctk.CTkLabel(
            preview_frame,
            text="文件預覽",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        preview_title.pack(pady=(10, 5))
        
        # 預覽內容
        self.create_preview_area(preview_frame)
    
    def create_action_buttons(self, parent):
        """創建操作按鈕"""
        button_frame = ctk.CTkFrame(parent)
        button_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        # 視圖切換按鈕
        view_frame = ctk.CTkFrame(button_frame)
        view_frame.pack(side='left', padx=(10, 0), pady=10)
        
        ctk.CTkLabel(view_frame, text="視圖:").pack(side='left', padx=(5, 5))
        
        self.view_var = ctk.StringVar(value="documents")
        
        doc_btn = ctk.CTkRadioButton(view_frame, text="文件", 
                                    variable=self.view_var, value="documents",
                                    command=self.switch_view)
        doc_btn.pack(side='left', padx=5)
        
        q_btn = ctk.CTkRadioButton(view_frame, text="題庫", 
                                  variable=self.view_var, value="questions",
                                  command=self.switch_view)
        q_btn.pack(side='left', padx=5)
        
        # 操作按鈕
        op_frame = ctk.CTkFrame(button_frame)
        op_frame.pack(side='right', padx=(0, 10), pady=10)
        
        # 可視化按鈕
        self.chart_btn = ctk.CTkButton(op_frame, text="📊 圖表", 
                                      command=self.show_charts,
                                      fg_color="green", hover_color="darkgreen")
        self.chart_btn.pack(side='right', padx=5)
        
        self.mindmap_btn = ctk.CTkButton(op_frame, text="🧠 心智圖", 
                                        command=self.show_mindmap,
                                        fg_color="purple", hover_color="darkviolet")
        self.mindmap_btn.pack(side='right', padx=5)
        
        self.delete_btn = ctk.CTkButton(op_frame, text="🗑️ 刪除選中", 
                                       command=self.delete_selected,
                                       fg_color="red", hover_color="darkred")
        self.delete_btn.pack(side='right', padx=5)
        
        self.refresh_btn = ctk.CTkButton(op_frame, text="刷新", 
                                        command=self.refresh_view)
        self.refresh_btn.pack(side='right', padx=5)

    def switch_view(self):
        """切換視圖"""
        view = self.view_var.get()
        self.current_view = view
        
        if view == "documents":
            self.refresh_document_list()
        else:
            self.refresh_question_list()
    
    def refresh_question_list(self):
        """刷新題庫列表"""
        self.file_tree.delete(*self.file_tree.get_children())
        
        try:
            questions = self.db.get_all_questions_with_source()
            
            for question in questions:
                question_id, subject, question_text, answer_text, doc_title, created_at = question
                
                # 顯示前50個字符的題目
                display_text = question_text[:50] + "..." if len(question_text) > 50 else question_text
                
                self.file_tree.insert("", "end", 
                                     values=(
                                         f"Q{question_id}",
                                         subject or "未分類",
                                         display_text,
                                         doc_title or "未知來源",
                                         created_at
                                     ))
        except Exception as e:
            self.show_error(f"刷新題庫失敗: {str(e)}")
    
    def delete_selected(self):
        """刪除選中項目"""
        selected = self.file_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "請先選擇要刪除的項目")
            return
            
        # 確認刪除
        if messagebox.askyesno("確認", f"確定要刪除選中的 {len(selected)} 個項目嗎？"):
            try:
                for item in selected:
                    values = self.file_tree.item(item)['values']
                    
                    if self.current_view == "documents":
                        # 刪除文件及相關問題
                        doc_id = values[0]
                        self.db.delete_document_and_questions(doc_id)
                    else:
                        # 刪除問題
                        question_id_str = values[0]  # 格式: "Q123"
                        question_id = int(question_id_str[1:])
                        self.db.cursor.execute("DELETE FROM questions WHERE id = ?", (question_id,))
                        self.db.conn.commit()
                
                # 刷新視圖
                if self.current_view == "documents":
                    self.refresh_document_list()
                else:
                    self.refresh_question_list()
                
                # 重要：更新統計資料
                self.update_statistics()
                    
                messagebox.showinfo("成功", "刪除完成")
                
            except Exception as e:
                self.show_error(f"刪除失敗: {str(e)}")
    
    def refresh_view(self):
        """刷新當前視圖"""
    def create_document_list(self, parent):
        """創建文件列表"""
        """建立文件列表"""
        # 使用 Treeview 顯示文件列表
        list_container = ctk.CTkFrame(parent)
        list_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # 建立 Treeview (統一的文件/題庫顯示)
        columns = ("id", "subject", "title", "source", "date")
        self.file_tree = ttk.Treeview(
            list_container,
            columns=columns,
            show="headings",
            height=10
        )
        
        # 設定欄位標題 (會根據視圖動態調整)
        self.setup_tree_columns()
        
        # 滾動條
        tree_scroll = ttk.Scrollbar(list_container, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=tree_scroll.set)
        
        # 打包
        self.file_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        
        # 綁定選擇事件
        self.file_tree.bind("<<TreeviewSelect>>", self.on_item_select)
        self.file_tree.bind("<Double-1>", self.on_item_double_click)
    
    def setup_tree_columns(self):
        """根據當前視圖設置TreeView列"""
        if self.current_view == "documents":
            self.file_tree.heading("id", text="ID")
            self.file_tree.heading("subject", text="科目")
            self.file_tree.heading("title", text="標題")
            self.file_tree.heading("source", text="類型")
            self.file_tree.heading("date", text="建立時間")
            
            self.file_tree.column("id", width=60)
            self.file_tree.column("subject", width=100)
            self.file_tree.column("title", width=300)
            self.file_tree.column("source", width=80)
            self.file_tree.column("date", width=150)
        else:  # questions view
            self.file_tree.heading("id", text="題號")
            self.file_tree.heading("subject", text="科目")
            self.file_tree.heading("title", text="題目")
            self.file_tree.heading("source", text="來源文件")
            self.file_tree.heading("date", text="建立時間")
            
            self.file_tree.column("id", width=80)
            self.file_tree.column("subject", width=100)
            self.file_tree.column("title", width=350)
            self.file_tree.column("source", width=200)
            self.file_tree.column("date", width=150)
    
    def create_preview_area(self, parent):
        """建立預覽區域"""
        # 預覽容器
        preview_container = ctk.CTkFrame(parent)
        preview_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # 預覽控制列
        control_frame = ctk.CTkFrame(preview_container)
        control_frame.pack(fill="x", padx=5, pady=(5, 0))
        
        # 答案顯示切換
        self.show_answers = tk.BooleanVar(value=True)  # 預設顯示答案
        self.answer_toggle = ctk.CTkCheckBox(
            control_frame,
            text="顯示答案",
            variable=self.show_answers,
            command=self.toggle_answers,
            font=ctk.CTkFont(size=12)
        )
        self.answer_toggle.pack(side="left", padx=10, pady=5)
        
        # 重新載入按鈕
        self.reload_btn = ctk.CTkButton(
            control_frame,
            text="🔄 重新載入",
            command=self.reload_current_preview,
            font=ctk.CTkFont(size=11),
            height=25,
            width=80
        )
        self.reload_btn.pack(side="right", padx=10, pady=5)
        
        # 標籤頁
        self.preview_notebook = ttk.Notebook(preview_container)
        self.preview_notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Markdown 預覽標籤頁
        self.markdown_frame = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(self.markdown_frame, text="Markdown 預覽")
        
        # 使用自定義的 MarkdownText 組件
        # 使用系統預設字體，避免跨平台字體問題
        try:
            # 嘗試使用常見的中文字體
            import tkinter.font as tkFont
            default_font = tkFont.nametofont("TkDefaultFont")
            font_family = default_font.cget("family")
            
            # 在 macOS 上嘗試使用 PingFang SC
            import platform
            if platform.system() == "Darwin":  # macOS
                font_family = "PingFang SC"
            elif platform.system() == "Windows":
                font_family = "Microsoft JhengHei"
                
        except:
            font_family = "TkDefaultFont"
        
        self.markdown_text = MarkdownText(
            self.markdown_frame,
            font=(font_family, 11),
            height=15
        )
        self.markdown_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 題目詳情標籤頁
        self.detail_frame = ttk.Frame(self.preview_notebook)  
        self.preview_notebook.add(self.detail_frame, text="詳細資訊")
        
        self.detail_text = scrolledtext.ScrolledText(
            self.detail_frame,
            wrap=tk.WORD,
            font=(font_family, 11),
            height=15
        )
        self.detail_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 心智圖標籤頁（改為 Mermaid 圖表）
        self.mindmap_frame = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(self.mindmap_frame, text="心智圖")
        
        # 創建 CustomTkinter 的滾動框架在 ttk.Frame 內
        self.mindmap_scrollable = ctk.CTkScrollableFrame(self.mindmap_frame)
        self.mindmap_scrollable.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 心智圖文字框
        self.mindmap_text = ctk.CTkTextbox(
            self.mindmap_scrollable,
            font=ctk.CTkFont(family="Courier", size=12),
            height=400
        )
        self.mindmap_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 心智圖工具列
        mindmap_toolbar = ctk.CTkFrame(self.mindmap_scrollable)
        mindmap_toolbar.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(
            mindmap_toolbar,
            text="複製 Mermaid 代碼",
            command=self.copy_mermaid_code,
            height=30
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            mindmap_toolbar,
            text="在線預覽",
            command=self.open_mermaid_preview,
            height=30
        ).pack(side="left", padx=5)
        
        # 儲存當前預覽的內容（用於重新載入）
        self.current_preview_data = None
    
    def create_status_bar(self):
        """建立狀態列"""
        self.status_frame = ctk.CTkFrame(self.main_container)
        self.status_frame.pack(fill="x", side="bottom", padx=5, pady=(0, 5))
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="就緒",
            font=ctk.CTkFont(size=11)
        )
        self.status_label.pack(side="left", padx=10, pady=5)
        
        # 進度條
        self.progress_bar = ctk.CTkProgressBar(self.status_frame)
        self.progress_bar.pack(side="right", padx=10, pady=5)
        self.progress_bar.set(0)
    
    def setup_drag_drop(self):
        """設定拖放功能"""
        # 暫時禁用拖放功能避免依賴問題
        # TODO: 在需要時可以重新啟用
        pass
    
    def on_drop(self, event):
        """處理拖放事件"""
        # 暫時禁用拖放功能
        pass
    
    def select_file(self):
        """選擇檔案"""
        file_types = [
            ("所有支援的檔案", "*.txt;*.pdf;*.docx;*.html;*.htm"),
            ("文字檔", "*.txt"),
            ("PDF檔", "*.pdf"),
            ("Word檔", "*.docx"),
            ("HTML檔", "*.html;*.htm"),
            ("所有檔案", "*.*")
        ]
        
        file_path = filedialog.askopenfilename(
            title="選擇要處理的檔案",
            filetypes=file_types
        )
        
        if file_path:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, file_path)
            self.process_input()
        
    def process_input(self):
        """處理輸入內容"""
        input_text = self.input_entry.get().strip()
        if not input_text:
            messagebox.showwarning("警告", "請輸入內容或選擇檔案")
            return
        
        # 禁用處理按鈕，顯示進度
        self.process_btn.configure(state="disabled", text="處理中...")
        self.progress_bar.set(0.1)
        self.update_status("正在處理輸入內容...")
        
        # 在後台執行處理
        threading.Thread(target=self._process_input_background, args=(input_text,)).start()
    
    def _process_input_background(self, input_text: str):
        """後台處理輸入內容"""
        try:
            # 建立新的事件迴圈
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 處理內容
            result = loop.run_until_complete(
                self.content_processor.process_content(input_text)
            )
            
            # 在主執行緒中更新 UI
            self.root.after(0, self._on_process_complete, result)
            
        except Exception as e:
            error_msg = f"處理失敗: {str(e)}"
            self.root.after(0, self._on_process_error, error_msg)
        finally:
            loop.close()
    
    def _on_process_complete(self, result: Dict[str, Any]):
        """處理完成回調"""
        # 重置 UI
        self.process_btn.configure(state="normal", text="處理")
        self.progress_bar.set(1.0)
        
        if result.get('success'):
            self.update_status(f"處理完成 - {result.get('type', '')} 類型")
            
            # 構建詳細的成功訊息
            success_msg = f"內容處理完成！\n類型: {result.get('type', '')}\n科目: {result.get('subject', '')}"
            
            # 如果是學習資料類型，顯示生成的模擬題數量
            if result.get('type') == 'info' and result.get('question_ids'):
                question_count = len(result.get('question_ids', []))
                success_msg += f"\n📝 已自動生成 {question_count} 道申論題並加入題庫"
            
            # 如果是考題類型，顯示題目數量
            elif result.get('type') == 'exam' and result.get('question_ids'):
                question_count = len(result.get('question_ids', []))
                success_msg += f"\n📋 已解析 {question_count} 道考題"
            
            messagebox.showinfo("成功", success_msg)
            
            # 清空輸入框
            self.input_entry.delete(0, tk.END)
            
            # 重新載入資料
            self.refresh_view()  # 使用新的刷新方法
            self.update_statistics()
            
        else:
            error_msg = result.get('error', '未知錯誤')
            self.update_status(f"處理失敗: {error_msg}")
            messagebox.showerror("錯誤", f"處理失敗: {error_msg}")
        
        # 重置進度條
        self.root.after(2000, lambda: self.progress_bar.set(0))
    
    def _on_process_error(self, error_msg: str):
        """處理錯誤回調"""
        self.process_btn.configure(state="normal", text="處理")
        self.progress_bar.set(0)
        self.update_status(error_msg)
        messagebox.showerror("錯誤", error_msg)
    
    def update_status(self, message: str):
        """更新狀態列"""
        self.status_label.configure(text=f"{datetime.now().strftime('%H:%M:%S')} - {message}")
    
    def on_subject_change(self, value):
        """科目變更事件"""
        self.current_subject = value
        self.load_documents()
    
    def on_search_change(self, event):
        """搜尋變更事件"""
        # 延遲搜尋避免頻繁查詢
        self.root.after(500, self.search_documents)
    
    def search_documents(self):
        """搜尋文件和題目"""
        query = self.search_var.get().strip()
        if query:
            self.update_status(f"搜尋: {query}")
            
            if self.current_view == "documents":
                # 搜尋文件
                documents = self.db.search_documents(query)
                self.display_search_results_documents(documents)
            else:
                # 搜尋題目
                questions = self.db.search_questions(query)
                self.display_search_results_questions(questions)
        else:
            # 清空搜尋，顯示所有內容
            self.refresh_view()
    
    def display_search_results_documents(self, documents):
        """顯示文件搜尋結果"""
        self.file_tree.delete(*self.file_tree.get_children())
        
        for doc in documents:
            doc_id, title, content, doc_type, subject, file_path, created_at = doc
            type_display = "考題" if doc_type == "exam" else "資料"
            
            self.file_tree.insert("", "end", 
                                 values=(
                                     doc_id,
                                     subject or "未分類",
                                     title or "無標題",
                                     type_display,
                                     created_at
                                 ))
    
    def display_search_results_questions(self, questions):
        """顯示題目搜尋結果"""
        self.file_tree.delete(*self.file_tree.get_children())
        
        for question in questions:
            question_id, subject, question_text, answer_text, doc_title, created_at = question
            display_text = question_text[:50] + "..." if len(question_text) > 50 else question_text
            
            self.file_tree.insert("", "end", 
                                 values=(
                                     f"Q{question_id}",
                                     subject or "未分類",
                                     display_text,
                                     doc_title or "未知來源",
                                     created_at
                                 ))
    
    def on_item_select(self, event):
        """項目選擇事件"""
        selection = self.file_tree.selection()
        if selection:
            item = self.file_tree.item(selection[0])
            if self.current_view == "documents":
                self.preview_document(item['values'])
            else:
                self.preview_question(item['values'])
    
    def on_item_double_click(self, event):
        """項目雙擊事件"""
        selection = self.file_tree.selection()
        if selection:
            item = self.file_tree.item(selection[0])
            if self.current_view == "documents":
                self.show_document_detail(item['values'])
            else:
                self.show_question_detail(item['values'])
    
    def preview_question(self, values):
        """預覽問題"""
        try:
            # 儲存預覽資料供重新載入使用
            self.current_preview_data = {
                'type': 'question',
                'data': values
            }
            
            question_id_str = values[0]  # 格式: "Q123"
            question_id = int(question_id_str[1:])
            
            # 從資料庫獲取完整問題資訊
            cursor = self.db.cursor
            cursor.execute("""
                SELECT q.question_text, q.answer_text, q.subject, d.title 
                FROM questions q 
                LEFT JOIN documents d ON q.document_id = d.id 
                WHERE q.id = ?
            """, (question_id,))
            
            result = cursor.fetchone()
            if result:
                question_text, answer_text, subject, doc_title = result
                
                # 生成 Markdown 格式的內容
                markdown_content = f"""# 📚 題目預覽

> **科目**: {subject or '未分類'}  
> **來源**: {doc_title or '未知'}

## 📋 題目

{question_text}

## ✅ 參考答案

{answer_text or '無答案'}
"""
                
                # 根據答案顯示設定過濾內容
                filtered_content = self.filter_content_for_answers(markdown_content)
                self.markdown_text.set_markdown(filtered_content)
                
                # 更新詳細資訊
                detail_content = f"""題目ID: Q{question_id}
科目: {subject or '未分類'}
來源文件: {doc_title or '未知'}

題目內容:
{question_text}

答案內容:
{answer_text or '無答案'}
"""
                self.detail_text.delete("1.0", tk.END)
                self.detail_text.insert("1.0", detail_content)
                
        except Exception as e:
            self.show_error(f"預覽問題失敗: {str(e)}")
            error_content = f"# 預覽失敗\n\n無法載入問題內容: {str(e)}"
            self.markdown_text.set_markdown(error_content)
    
    def show_question_detail(self, values):
        """顯示問題詳細資訊"""
        try:
            question_id_str = values[0]  # 格式: "Q123"
            question_id = int(question_id_str[1:])
            
            # 這裡可以實作問題詳細檢視視窗
            messagebox.showinfo("問題詳情", f"顯示問題 {question_id} 的詳細資訊")
            
        except Exception as e:
            self.show_error(f"顯示問題詳情失敗: {str(e)}")
    
    def load_initial_data(self):
        """載入初始資料"""
        self.refresh_document_list()  # 使用新的刷新方法
        self.update_statistics()
        self.load_tags()
    
    def load_tags(self):
        """載入標籤資料"""
        try:
            # 從資料庫獲取所有不重複的標籤
            cursor = self.db.cursor
            cursor.execute('''
                SELECT DISTINCT subject FROM documents 
                WHERE subject IS NOT NULL AND subject != ""
                ORDER BY subject
            ''')
            subjects = [row[0] for row in cursor.fetchall()]
            
            # 清除現有標籤
            for widget in self.tags_scrollable.winfo_children():
                widget.destroy()
            self.tag_vars.clear()
            
            # 添加科目標籤
            for subject in subjects:
                var = ctk.BooleanVar()
                checkbox = ctk.CTkCheckBox(
                    self.tags_scrollable,
                    text=subject,
                    variable=var,
                    command=self.on_tag_filter_changed
                )
                checkbox.pack(anchor="w", padx=5, pady=2)
                self.tag_vars[subject] = var
                
        except Exception as e:
            print(f"載入標籤失敗: {e}")
    
    def on_tag_filter_changed(self):
        """標籤篩選變更時的回調"""
        selected_tags = [tag for tag, var in self.tag_vars.items() if var.get()]
        self.selected_tags = selected_tags
        self.refresh_document_list()  # 重新整理文件列表
    
    def refresh_document_list(self):
        """刷新文件列表"""
        self.file_tree.delete(*self.file_tree.get_children())
        
        try:
            # 更新列標題
            self.setup_tree_columns()
            
            # 獲取文件
            documents = self.db.get_all_documents()
            
            # 根據選中的標籤篩選文件
            if self.selected_tags:
                filtered_documents = []
                for doc in documents:
                    doc_id, title, content, doc_type, subject, file_path, created_at = doc
                    if subject in self.selected_tags:
                        filtered_documents.append(doc)
                documents = filtered_documents
            
            for doc in documents:
                doc_id, title, content, doc_type, subject, file_path, created_at = doc
                
                # 確定類型顯示
                type_display = "考題" if doc_type == "exam" else "資料"
                
                self.file_tree.insert("", "end", 
                                     values=(
                                         doc_id,
                                         subject or "未分類",
                                         title or "無標題",
                                         type_display,
                                         created_at
                                     ))
        except Exception as e:
            self.show_error(f"刷新文件列表失敗: {str(e)}")
    
    def copy_mermaid_code(self):
        """複製 Mermaid 代碼到剪貼簿"""
        try:
            import tkinter as tk
            content = self.mindmap_text.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.show_success("Mermaid 代碼已複製到剪貼簿")
        except Exception as e:
            self.show_error(f"複製失敗: {str(e)}")
    
    def open_mermaid_preview(self):
        """在瀏覽器中開啟 Mermaid 在線預覽"""
        try:
            import webbrowser
            import urllib.parse
            
            content = self.mindmap_text.get("1.0", "end-1c")
            encoded_content = urllib.parse.quote(content)
            url = f"https://mermaid.live/edit#{encoded_content}"
            webbrowser.open(url)
        except Exception as e:
            self.show_error(f"開啟預覽失敗: {str(e)}")
    
    def generate_mermaid_mindmap(self, document, questions):
        """生成 Mermaid 心智圖代碼"""
        try:
            subject = document.get('subject', '未分類')
            title = document.get('title', '文件')
            
            mermaid_code = f"""mindmap
  root({subject})
    {title}
"""
            
            # 添加題目節點
            for i, question in enumerate(questions[:8], 1):  # 最多顯示8個題目
                q_text = question.get('question_text', '')[:30]
                if len(q_text) > 30:
                    q_text = q_text[:27] + "..."
                # 清理特殊字元
                q_text = q_text.replace('"', '').replace('(', '').replace(')', '')
                mermaid_code += f"      題目{i}\n        {q_text}\n"
            
            # 添加科目相關概念
            concepts = ['核心概念', '重要原理', '應用實例', '相關技術']
            for concept in concepts:
                mermaid_code += f"    {concept}\n"
                # 為每個概念添加子節點
                for j in range(2):
                    mermaid_code += f"      詳細內容{j+1}\n"
            
            return mermaid_code
            
        except Exception as e:
            return f"生成心智圖時發生錯誤: {str(e)}"

    def load_documents(self):
        """載入文件列表"""
        try:
            if self.current_subject == "全部":
                # 載入所有文件
                all_documents = []
                for subject in ["資料結構", "資訊管理", "資通網路與資訊安全", "資料庫應用"]:
                    documents = self.db_manager.get_documents_by_subject(subject)
                    all_documents.extend(documents)
                self.current_documents = all_documents
            else:
                self.current_documents = self.db_manager.get_documents_by_subject(self.current_subject)
            
            self.display_documents(self.current_documents)
            
        except Exception as e:
            self.update_status(f"載入文件失敗: {str(e)}")
    
    def display_documents(self, documents: List[Dict[str, Any]]):
        """顯示文件列表"""
        # 清空現有項目
        for item in self.document_tree.get_children():
            self.document_tree.delete(item)
        
        # 添加文件項目
        for doc in documents:
            doc_type = "考題" if doc.get('is_exam') else "資料"
            title = doc.get('summary', '')[:50] + "..." if len(doc.get('summary', '')) > 50 else doc.get('summary', '')
            created_at = doc.get('created_at', '')
            
            # 獲取文件標籤（從關聯的題目中獲取）
            questions = self.db_manager.get_questions_by_document(doc['id'])
            all_tags = []
            for q in questions:
                if q.get('tags'):
                    all_tags.extend(q['tags'])
            tags_str = ', '.join(list(set(all_tags))[:3])  # 最多顯示3個標籤
            
            self.document_tree.insert("", "end", values=(
                doc_type,
                doc.get('subject', ''),
                title,
                created_at,
                tags_str
            ))
    
    def update_statistics(self):
        """更新統計資訊"""
        try:
            stats = self.db.get_statistics()
            stats_text = f"""文件總數: {stats['total_documents']}
考題: {stats['exam_documents']}
資料: {stats['info_documents']}
題目總數: {stats['total_questions']}"""
            
            self.stats_label.configure(text=stats_text)
            self.update_quick_stats()  # 同時更新快速統計
            
        except Exception as e:
            self.stats_label.configure(text=f"統計載入失敗: {str(e)}")
    
    def toggle_answers(self):
        """切換答案顯示"""
        # 重新載入當前預覽內容
        self.reload_current_preview()
    
    def reload_current_preview(self):
        """重新載入當前預覽內容"""
        if self.current_preview_data:
            if self.current_preview_data['type'] == 'document':
                self.preview_document(self.current_preview_data['data'])
            elif self.current_preview_data['type'] == 'question':
                self.preview_question(self.current_preview_data['data'])
    
    def filter_content_for_answers(self, markdown_content: str) -> str:
        """根據答案顯示設定過濾內容"""
        if self.show_answers.get():
            return markdown_content
        
        # 隱藏答案部分
        lines = markdown_content.split('\n')
        filtered_lines = []
        skip_section = False
        
        for line in lines:
            # 檢查是否為答案區段的開始
            if any(keyword in line for keyword in ['✅ 標準答案', '✅ 參考答案', '## ✅']):
                skip_section = True
                filtered_lines.append(line)
                filtered_lines.append("*[答案已隱藏，請切換「顯示答案」來檢視]*\n")
                continue
            
            # 檢查是否為新區段的開始（結束答案隱藏）
            if skip_section and (line.startswith('#') or line.strip() == '---'):
                skip_section = False
            
            # 如果不在答案區段中，則保留這行
            if not skip_section:
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def preview_document(self, document_info):
        """預覽文件"""
        try:
            # 儲存預覽資料供重新載入使用
            self.current_preview_data = {
                'type': 'document',
                'data': document_info
            }
            
            # document_info 包含: [doc_id, subject, title, type_display, created_at]
            doc_id = document_info[0]
            
            # 從資料庫獲取完整文件資訊
            cursor = self.db.cursor
            cursor.execute("""
                SELECT title, content, type, subject, file_path, created_at 
                FROM documents 
                WHERE id = ?
            """, (doc_id,))
            
            result = cursor.fetchone()
            if result:
                title, content, doc_type, subject, file_path, created_at = result
                
                # 如果有對應的 Markdown 檔案，優先顯示
                if file_path and os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        markdown_content = f.read()
                else:
                    # 否則顯示基本資訊
                    markdown_content = f"""# {title}

> **科目**: {subject or '未分類'}  
> **類型**: {doc_type}  
> **建立時間**: {created_at}

## 內容

{content}
"""
                
                # 根據答案顯示設定過濾內容
                filtered_content = self.filter_content_for_answers(markdown_content)
                self.markdown_text.set_markdown(filtered_content)
                
                # 更新詳細資訊標籤頁
                detail_content = f"""文件ID: {doc_id}
標題: {title}
科目: {subject or '未分類'}
類型: {doc_type}
檔案路徑: {file_path or '無'}
建立時間: {created_at}

原始內容:
{content}
"""
                self.detail_text.delete("1.0", tk.END)
                self.detail_text.insert("1.0", detail_content)
                
        except Exception as e:
            self.show_error(f"預覽文件失敗: {str(e)}")
            # 顯示錯誤訊息
            error_content = f"# 預覽失敗\n\n無法載入文件內容: {str(e)}"
            self.markdown_text.set_markdown(error_content)
    
    def show_document_detail(self, document_info):
        """顯示文件詳情"""
        # 實作詳情顯示邏輯
        pass
    
    def export_data(self):
        """匯出資料"""
        # 實作資料匯出邏輯
        messagebox.showinfo("匯出", "匯出功能開發中...")
    
    def show_statistics(self):
        """顯示統計資料"""
        # 實作統計資料顯示邏輯
        messagebox.showinfo("統計", "統計視窗開發中...")
    
    def show_error(self, message):
        """顯示錯誤訊息"""
        messagebox.showerror("錯誤", message)
    
    def show_success(self, message):
        """顯示成功訊息"""
        messagebox.showinfo("成功", message)
    
    def show_charts(self):
        """顯示AI生成的學習統計圖表"""
        if FigureCanvasTkinter is None:
            self.show_error("matplotlib 套件未安裝，無法顯示圖表")
            return
            
        try:
            # 啟動AI圖表生成
            self.generate_ai_charts()
            
        except Exception as e:
            self.show_error(f"顯示圖表失敗: {str(e)}")
    
    def show_mindmap(self):
        """顯示當前選中文件的 Mermaid 心智圖"""
        try:
            # 切換到心智圖標籤頁
            self.preview_notebook.select(2)  # 心智圖是第3個標籤頁（索引2）
            
            # 如果有當前預覽的資料，生成心智圖
            if self.current_preview_data:
                if self.current_preview_data['type'] == 'document':
                    self.generate_document_mindmap(self.current_preview_data['data'])
                elif self.current_preview_data['type'] == 'question':
                    self.show_success("請選擇文件來查看心智圖，單個題目無法生成心智圖")
            else:
                self.mindmap_text.delete("1.0", "end")
                self.mindmap_text.insert("1.0", "請先選擇一個文件來生成心智圖")
                
        except Exception as e:
            self.show_error(f"顯示心智圖失敗: {str(e)}")
    
    def generate_document_mindmap(self, document_info):
        """為選中的文件生成心智圖"""
        try:
            doc_id = document_info[0]
            
            # 從資料庫獲取文件和相關問題
            cursor = self.db.cursor
            cursor.execute("""
                SELECT title, subject FROM documents WHERE id = ?
            """, (doc_id,))
            doc_result = cursor.fetchone()
            
            cursor.execute("""
                SELECT question_text FROM questions WHERE document_id = ?
            """, (doc_id,))
            questions = cursor.fetchall()
            
            if doc_result:
                title, subject = doc_result
                
                # 生成 Mermaid 心智圖代碼
                mermaid_code = self.generate_mermaid_mindmap({
                    'title': title,
                    'subject': subject or '未分類'
                }, [{'question_text': q[0]} for q in questions])
                
                # 顯示在心智圖文字框中
                self.mindmap_text.delete("1.0", "end")
                self.mindmap_text.insert("1.0", mermaid_code)
                
        except Exception as e:
            self.show_error(f"生成心智圖失敗: {str(e)}")
    
    def show_charts(self):
        """顯示統計資訊"""
        try:
            self.show_statistics()
        except Exception as e:
            self.show_error(f"顯示統計失敗: {str(e)}")
        # 顯示進度對話框
        progress_window = tk.Toplevel(self.root)
        progress_window.title("🤖 AI 正在分析您的學習資料...")
        progress_window.geometry("400x150")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        ctk.CTkLabel(progress_window, 
                    text="🧠 AI 正在分析您的學習資料",
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=20)
        
        progress_bar = ctk.CTkProgressBar(progress_window)
        progress_bar.pack(pady=10, padx=20, fill="x")
        progress_bar.set(0.1)
        
        status_label = ctk.CTkLabel(progress_window, text="正在收集資料...")
        status_label.pack(pady=10)
        
        # 在後台執行AI分析
        threading.Thread(target=self._generate_ai_charts_background, 
                        args=(progress_window, progress_bar, status_label)).start()
    
    def generate_ai_mindmap(self):
        """AI生成知識心智圖"""
        # 顯示進度對話框
        progress_window = tk.Toplevel(self.root)
        progress_window.title("🤖 AI 正在建構知識心智圖...")
        progress_window.geometry("400x150")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        ctk.CTkLabel(progress_window, 
                    text="🧠 AI 正在建構知識關聯圖",
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=20)
        
        progress_bar = ctk.CTkProgressBar(progress_window)
        progress_bar.pack(pady=10, padx=20, fill="x")
        progress_bar.set(0.1)
        
        status_label = ctk.CTkLabel(progress_window, text="正在分析知識結構...")
        status_label.pack(pady=10)
        
        # 在後台執行AI分析
        threading.Thread(target=self._generate_ai_mindmap_background, 
                        args=(progress_window, progress_bar, status_label)).start()
    
    def show_chart_window(self, viz_manager, stats):
        """顯示圖表視窗"""
        chart_window = tk.Toplevel(self.root)
        chart_window.title("📊 統計圖表")
        chart_window.geometry("800x600")
        
        # 創建筆記本控件來顯示多個圖表
        notebook = ttk.Notebook(chart_window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 科目分布圓餅圖
        pie_frame = ttk.Frame(notebook)
        notebook.add(pie_frame, text="科目分布")
        
        pie_fig = viz_manager.create_subject_pie_chart(stats)
        pie_canvas = FigureCanvasTkinter(pie_fig, pie_frame)
        pie_canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # 文件類型分布條狀圖
        bar_frame = ttk.Frame(notebook)
        notebook.add(bar_frame, text="文件類型")
        
        bar_fig = viz_manager.create_document_type_bar_chart(stats)
        bar_canvas = FigureCanvasTkinter(bar_fig, bar_frame)
        bar_canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # 學習進度圖
        progress_frame = ttk.Frame(notebook)
        notebook.add(progress_frame, text="學習進度")
        
        progress_fig = viz_manager.create_learning_progress_chart(stats)
        progress_canvas = FigureCanvasTkinter(progress_fig, progress_frame)
        progress_canvas.get_tk_widget().pack(fill="both", expand=True)
    
    def show_mindmap_window(self, viz_manager, documents, questions):
        """顯示心智圖視窗"""
        mindmap_window = tk.Toplevel(self.root)
        mindmap_window.title("🧠 知識心智圖")
        mindmap_window.geometry("1000x700")
        
        # 創建筆記本控件來顯示不同類型的心智圖
        notebook = ttk.Notebook(mindmap_window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 科目關聯圖
        subject_frame = ttk.Frame(notebook)
        notebook.add(subject_frame, text="科目關聯")
        
        subject_fig = viz_manager.create_subject_relationship_graph(documents, questions)
        subject_canvas = FigureCanvasTkinter(subject_fig, subject_frame)
        subject_canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # 知識點網絡圖
        knowledge_frame = ttk.Frame(notebook)
        notebook.add(knowledge_frame, text="知識網絡")
        
        knowledge_fig = viz_manager.create_knowledge_network_graph(questions)
        knowledge_canvas = FigureCanvasTkinter(knowledge_fig, knowledge_frame)
        knowledge_canvas.get_tk_widget().pack(fill="both", expand=True)
    
    def export_knowledge(self):
        """匯出知識庫"""
        try:
            # 選擇匯出路徑
            export_path = filedialog.asksaveasfilename(
                title="匯出知識庫",
                defaultextension=".json",
                filetypes=[
                    ("JSON檔案", "*.json"),
                    ("所有檔案", "*.*")
                ]
            )
            
            if export_path:
                # 獲取所有資料
                documents = self.db.get_all_documents()
                questions = self.db.get_all_questions_with_source()
                
                # 組織匯出資料
                export_data = {
                    "export_date": datetime.now().isoformat(),
                    "documents": [
                        {
                            "id": doc[0],
                            "title": doc[1],
                            "content": doc[2],
                            "type": doc[3],
                            "subject": doc[4],
                            "file_path": doc[5],
                            "created_at": doc[6]
                        } for doc in documents
                    ],
                    "questions": [
                        {
                            "id": q[0],
                            "subject": q[1],
                            "question_text": q[2],
                            "answer_text": q[3],
                            "source_title": q[4],
                            "created_at": q[5]
                        } for q in questions
                    ]
                }
                
                # 寫入檔案
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                
                messagebox.showinfo("成功", f"知識庫已匯出至: {export_path}")
                
        except Exception as e:
            self.show_error(f"匯出失敗: {str(e)}")
    
    def import_knowledge(self):
        """匯入知識庫"""
        try:
            # 選擇匯入檔案
            import_path = filedialog.askopenfilename(
                title="匯入知識庫",
                filetypes=[
                    ("JSON檔案", "*.json"),
                    ("所有檔案", "*.*")
                ]
            )
            
            if import_path:
                # 確認匯入
                if not messagebox.askyesno("確認", "匯入會添加新資料，是否繼續？"):
                    return
                
                # 讀取檔案
                with open(import_path, 'r', encoding='utf-8') as f:
                    import_data = json.load(f)
                
                imported_docs = 0
                imported_questions = 0
                
                # 匯入文件
                for doc_data in import_data.get("documents", []):
                    doc_id = self.db.insert_document(
                        title=doc_data.get("title", ""),
                        content=doc_data.get("content", ""),
                        doc_type=doc_data.get("type", "info"),
                        subject=doc_data.get("subject"),
                        file_path=doc_data.get("file_path")
                    )
                    imported_docs += 1
                
                # 匯入題目（需要重新關聯到新的文件ID）
                for q_data in import_data.get("questions", []):
                    # 創建匿名文件來存放匯入的題目
                    temp_doc_id = self.db.insert_document(
                        title=f"匯入題目 - {q_data.get('source_title', '未知')}",
                        content=q_data.get("question_text", ""),
                        doc_type="exam",
                        subject=q_data.get("subject")
                    )
                    
                    self.db.insert_question(
                        document_id=temp_doc_id,
                        question_text=q_data.get("question_text", ""),
                        answer_text=q_data.get("answer_text", ""),
                        subject=q_data.get("subject")
                    )
                    imported_questions += 1
                
                # 刷新界面
                self.refresh_view()
                self.update_statistics()
                
                messagebox.showinfo("成功", 
                    f"匯入完成！\n文件: {imported_docs} 筆\n題目: {imported_questions} 筆")
                
        except Exception as e:
            self.show_error(f"匯入失敗: {str(e)}")
    
    def update_quick_stats(self):
        """更新快速統計"""
        try:
            stats = self.db.get_statistics()
            total_docs = stats.get('total_documents', 0)
            total_questions = stats.get('total_questions', 0)
            
            self.quick_stats_label.configure(
                text=f"📚 文件: {total_docs} | 📝 題目: {total_questions}"
            )
        except Exception as e:
            self.quick_stats_label.configure(text="統計載入失敗")
    
    def _generate_ai_charts_background(self, progress_window, progress_bar, status_label):
        """後台生成AI圖表"""
        try:
            # 建立新的事件迴圈
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 更新進度
            self.root.after(0, lambda: progress_bar.set(0.2))
            self.root.after(0, lambda: status_label.configure(text="正在分析學習內容..."))
            
            # 獲取資料
            documents = self.db.get_all_documents()
            questions = self.db.get_all_questions_with_source()
            
            if not documents and not questions:
                self.root.after(0, lambda: messagebox.showinfo("提示", "目前沒有資料可以分析，請先添加一些考題或知識內容。"))
                self.root.after(0, progress_window.destroy)
                return
            
            # 更新進度
            self.root.after(0, lambda: progress_bar.set(0.4))
            self.root.after(0, lambda: status_label.configure(text="AI正在生成學習分析..."))
            
            # 生成AI分析
            analysis_result = loop.run_until_complete(self._generate_learning_analysis(documents, questions))
            
            # 更新進度
            self.root.after(0, lambda: progress_bar.set(0.8))
            self.root.after(0, lambda: status_label.configure(text="正在生成圖表..."))
            
            # 在主執行緒中顯示結果
            self.root.after(0, lambda: self._show_ai_chart_results(analysis_result, progress_window))
            
        except Exception as e:
            self.root.after(0, lambda: self.show_error(f"AI圖表生成失敗: {str(e)}"))
            self.root.after(0, progress_window.destroy)
        finally:
            loop.close()
    
    def _generate_ai_mindmap_background(self, progress_window, progress_bar, status_label):
        """後台生成AI心智圖"""
        try:
            # 建立新的事件迴圈
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 更新進度
            self.root.after(0, lambda: progress_bar.set(0.2))
            self.root.after(0, lambda: status_label.configure(text="正在分析知識結構..."))
            
            # 獲取資料
            documents = self.db.get_all_documents()
            questions = self.db.get_all_questions_with_source()
            
            if not documents and not questions:
                self.root.after(0, lambda: messagebox.showinfo("提示", "目前沒有資料可以分析，請先添加一些考題或知識內容。"))
                self.root.after(0, progress_window.destroy)
                return
            
            # 更新進度
            self.root.after(0, lambda: progress_bar.set(0.4))
            self.root.after(0, lambda: status_label.configure(text="AI正在建構知識關聯..."))
            
            # 生成AI心智圖分析
            mindmap_result = loop.run_until_complete(self._generate_knowledge_structure(documents, questions))
            
            # 更新進度
            self.root.after(0, lambda: progress_bar.set(0.8))
            self.root.after(0, lambda: status_label.configure(text="正在繪製心智圖..."))
            
            # 在主執行緒中顯示結果
            self.root.after(0, lambda: self._show_ai_mindmap_results(mindmap_result, progress_window))
            
        except Exception as e:
            self.root.after(0, lambda: self.show_error(f"AI心智圖生成失敗: {str(e)}"))
            self.root.after(0, progress_window.destroy)
        finally:
            loop.close()
    
    async def _generate_learning_analysis(self, documents, questions):
        """生成學習分析"""
        # 整合所有內容
        all_content = []
        for doc in documents:
            if len(doc) > 2:
                all_content.append(f"文件：{doc[1] or ''}\\n內容：{doc[2] or ''}")
        
        for q in questions:
            if len(q) > 2:
                all_content.append(f"題目：{q[2] or ''}\\n答案：{q[3] or ''}")
        
        content_summary = "\\n\\n".join(all_content[:5])  # 限制內容量
        
        prompt = f"""
基於以下學習資料，請生成學習分析報告：

{content_summary}

請分析並生成以下學習圖表資料（JSON格式）：
{{
    "knowledge_gaps": [
        {{"topic": "知識點名稱", "gap_level": 1-5, "recommendation": "學習建議"}}
    ],
    "subject_mastery": [
        {{"subject": "科目名稱", "mastery_level": 1-10, "weak_areas": ["弱點1", "弱點2"]}}
    ],
    "study_priorities": [
        {{"priority": 1, "topic": "最需要加強的主題", "reason": "需要加強的原因"}}
    ],
    "learning_progress": [
        {{"week": "第1週", "topics_covered": 3, "questions_solved": 15, "understanding_level": 7}}
    ]
}}
"""
        
        return await self.content_processor.gemini._generate_with_json_parsing(prompt)
    
    async def _generate_knowledge_structure(self, documents, questions):
        """生成知識結構分析"""
        # 整合所有內容
        all_content = []
        for doc in documents:
            if len(doc) > 2:
                all_content.append(f"文件：{doc[1] or ''}\\n內容：{doc[2] or ''}")
        
        for q in questions:
            if len(q) > 2:
                all_content.append(f"題目：{q[2] or ''}\\n答案：{q[3] or ''}")
        
        content_summary = "\\n\\n".join(all_content[:5])  # 限制內容量
        
        prompt = f"""
基於以下學習資料，請分析知識結構並生成心智圖資料：

{content_summary}

請生成知識心智圖的結構資料（JSON格式）：
{{
    "central_topic": "核心主題",
    "main_branches": [
        {{
            "name": "主要分支1",
            "sub_branches": [
                {{"name": "子分支1.1", "details": ["細節1", "細節2"]}},
                {{"name": "子分支1.2", "details": ["細節3", "細節4"]}}
            ]
        }},
        {{
            "name": "主要分支2", 
            "sub_branches": [
                {{"name": "子分支2.1", "details": ["細節5", "細節6"]}}
            ]
        }}
    ],
    "connections": [
        {{"from": "概念A", "to": "概念B", "relationship": "關聯性描述"}}
    ],
    "key_concepts": ["重要概念1", "重要概念2", "重要概念3"]
}}
"""
        
        return await self.content_processor.gemini._generate_with_json_parsing(prompt)
    
    def _show_ai_chart_results(self, analysis_result, progress_window):
        """顯示AI圖表分析結果"""
        progress_window.destroy()
        
        if not analysis_result:
            messagebox.showwarning("警告", "AI分析沒有返回有效結果，請稍後再試。")
            return
        
        # 創建圖表視窗
        chart_window = tk.Toplevel(self.root)
        chart_window.title("🤖 AI 學習分析圖表")
        chart_window.geometry("1000x700")
        
        # 創建筆記本控件
        notebook = ttk.Notebook(chart_window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 知識缺口分析
        if 'knowledge_gaps' in analysis_result:
            self._create_knowledge_gaps_chart(notebook, analysis_result['knowledge_gaps'])
        
        # 科目掌握度分析
        if 'subject_mastery' in analysis_result:
            self._create_subject_mastery_chart(notebook, analysis_result['subject_mastery'])
        
        # 學習優先順序
        if 'study_priorities' in analysis_result:
            self._create_study_priorities_chart(notebook, analysis_result['study_priorities'])
        
        # 學習進度追蹤
        if 'learning_progress' in analysis_result:
            self._create_learning_progress_chart(notebook, analysis_result['learning_progress'])
    
    def _show_ai_mindmap_results(self, mindmap_result, progress_window):
        """顯示AI心智圖結果"""
        progress_window.destroy()
        
        if not mindmap_result:
            messagebox.showwarning("警告", "AI心智圖分析沒有返回有效結果，請稍後再試。")
            return
        
        # 創建心智圖視窗
        mindmap_window = tk.Toplevel(self.root)
        mindmap_window.title("🧠 AI 知識心智圖")
        mindmap_window.geometry("1200x800")
        
        # 創建筆記本控件
        notebook = ttk.Notebook(mindmap_window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 知識結構圖
        if 'main_branches' in mindmap_result:
            self._create_knowledge_structure_mindmap(notebook, mindmap_result)
        
        # 概念關聯圖
        if 'connections' in mindmap_result:
            self._create_concept_relationship_graph(notebook, mindmap_result)
    
    def _create_knowledge_gaps_chart(self, parent, gaps_data):
        """創建知識缺口圖表"""
        frame = ttk.Frame(parent)
        parent.add(frame, text="📊 知識缺口分析")
        
        try:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 6))
            
            if gaps_data:
                topics = [gap.get('topic', '未知') for gap in gaps_data]
                levels = [gap.get('gap_level', 0) for gap in gaps_data]
                
                bars = ax.bar(topics, levels, color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#F7DC6F'])
                ax.set_title('知識缺口分析 - AI智能評估', fontsize=16, fontweight='bold')
                ax.set_ylabel('缺口程度 (1-5)', fontsize=12)
                ax.set_xlabel('知識點', fontsize=12)
                
                # 添加數值標籤
                for bar, gap in zip(bars, gaps_data):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                           f'{int(height)}', ha='center', va='bottom')
                
                plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
                plt.tight_layout()
            else:
                ax.text(0.5, 0.5, '暫無知識缺口資料', ha='center', va='center', fontsize=16)
            
            canvas = FigureCanvasTkinter(fig, frame)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
        except Exception as e:
            error_label = tk.Label(frame, text=f"圖表生成失敗: {str(e)}")
            error_label.pack(expand=True)
    
    def _create_subject_mastery_chart(self, parent, mastery_data):
        """創建科目掌握度圖表"""
        frame = ttk.Frame(parent)
        parent.add(frame, text="📈 科目掌握度")
        
        try:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 6))
            
            if mastery_data:
                subjects = [item.get('subject', '未知') for item in mastery_data]
                mastery_levels = [item.get('mastery_level', 0) for item in mastery_data]
                
                bars = ax.bar(subjects, mastery_levels, color=['#3498DB', '#2ECC71', '#F39C12', '#E74C3C'])
                ax.set_title('科目掌握度評估 - AI智能分析', fontsize=16, fontweight='bold')
                ax.set_ylabel('掌握程度 (1-10)', fontsize=12)
                ax.set_xlabel('科目', fontsize=12)
                ax.set_ylim(0, 10)
                
                # 添加數值標籤
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                           f'{int(height)}/10', ha='center', va='bottom')
                
                plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
                plt.tight_layout()
            else:
                ax.text(0.5, 0.5, '暫無科目掌握度資料', ha='center', va='center', fontsize=16)
            
            canvas = FigureCanvasTkinter(fig, frame)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
        except Exception as e:
            error_label = tk.Label(frame, text=f"圖表生成失敗: {str(e)}")
            error_label.pack(expand=True)
    
    def _create_study_priorities_chart(self, parent, priorities_data):
        """創建學習優先順序圖表"""
        frame = ttk.Frame(parent)
        parent.add(frame, text="🎯 學習優先順序")
        
        # 創建文字顯示區域
        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Arial', 12))
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        
        if priorities_data:
            text_widget.insert(tk.END, "🎯 AI推薦的學習優先順序：\n\n")
            for i, priority in enumerate(priorities_data, 1):
                text_widget.insert(tk.END, f"優先級 {priority.get('priority', i)}：{priority.get('topic', '未知主題')}\n")
                text_widget.insert(tk.END, f"原因：{priority.get('reason', '無說明')}\n\n")
        else:
            text_widget.insert(tk.END, "暫無學習優先順序資料")
        
        text_widget.configure(state="disabled")
    
    def _create_learning_progress_chart(self, parent, progress_data):
        """創建學習進度圖表"""
        frame = ttk.Frame(parent)
        parent.add(frame, text="📚 學習進度追蹤")
        
        try:
            import matplotlib.pyplot as plt
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
            
            if progress_data:
                weeks = [item.get('week', f'第{i}週') for i, item in enumerate(progress_data, 1)]
                topics = [item.get('topics_covered', 0) for item in progress_data]
                questions = [item.get('questions_solved', 0) for item in progress_data]
                
                # 主題學習進度
                ax1.plot(weeks, topics, marker='o', linewidth=2, color='#3498DB')
                ax1.set_title('主題學習進度', fontsize=14, fontweight='bold')
                ax1.set_ylabel('已學習主題數', fontsize=12)
                ax1.grid(True, alpha=0.3)
                
                # 題目練習進度
                ax2.bar(weeks, questions, color='#2ECC71', alpha=0.7)
                ax2.set_title('題目練習進度', fontsize=14, fontweight='bold')
                ax2.set_ylabel('已解題數', fontsize=12)
                ax2.set_xlabel('時間', fontsize=12)
                
                plt.setp(ax2.get_xticklabels(), rotation=45, ha='right')
                plt.tight_layout()
            else:
                ax1.text(0.5, 0.5, '暫無學習進度資料', ha='center', va='center', fontsize=16)
                ax2.remove()
            
            canvas = FigureCanvasTkinter(fig, frame)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
        except Exception as e:
            error_label = tk.Label(frame, text=f"圖表生成失敗: {str(e)}")
            error_label.pack(expand=True)
    
    def _create_knowledge_structure_mindmap(self, parent, mindmap_data):
        """創建知識結構心智圖"""
        frame = ttk.Frame(parent)
        parent.add(frame, text="🧠 知識結構圖")
        
        try:
            import matplotlib.pyplot as plt
            import networkx as nx
            
            fig, ax = plt.subplots(figsize=(12, 8))
            
            # 創建網絡圖
            G = nx.Graph()
            
            # 添加中心節點
            central_topic = mindmap_data.get('central_topic', '核心知識')
            G.add_node(central_topic, node_type='central')
            
            # 添加主要分支
            for branch in mindmap_data.get('main_branches', []):
                branch_name = branch.get('name', '分支')
                G.add_node(branch_name, node_type='main')
                G.add_edge(central_topic, branch_name)
                
                # 添加子分支
                for sub_branch in branch.get('sub_branches', []):
                    sub_name = sub_branch.get('name', '子分支')
                    G.add_node(sub_name, node_type='sub')
                    G.add_edge(branch_name, sub_name)
            
            # 設置布局
            pos = nx.spring_layout(G, k=2, iterations=50)
            
            # 繪製節點
            node_colors = {'central': '#E74C3C', 'main': '#3498DB', 'sub': '#2ECC71'}
            node_sizes = {'central': 3000, 'main': 2000, 'sub': 1000}
            
            for node_type in ['central', 'main', 'sub']:
                nodes = [n for n, attr in G.nodes(data=True) if attr.get('node_type') == node_type]
                if nodes:
                    nx.draw_networkx_nodes(G, pos, nodelist=nodes, 
                                         node_color=node_colors[node_type],
                                         node_size=node_sizes[node_type],
                                         alpha=0.8, ax=ax)
            
            # 繪製邊
            nx.draw_networkx_edges(G, pos, alpha=0.6, width=2, ax=ax)
            
            # 繪製標籤
            nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', ax=ax)
            
            ax.set_title('知識結構心智圖 - AI智能生成', fontsize=16, fontweight='bold')
            ax.axis('off')
            
            canvas = FigureCanvasTkinter(fig, frame)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
        except Exception as e:
            error_label = tk.Label(frame, text=f"心智圖生成失敗: {str(e)}")
            error_label.pack(expand=True)
    
    def _create_concept_relationship_graph(self, parent, mindmap_data):
        """創建概念關聯圖"""
        frame = ttk.Frame(parent)
        parent.add(frame, text="🔗 概念關聯圖")
        
        # 創建文字顯示區域顯示關聯資訊
        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Arial', 12))
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        
        text_widget.insert(tk.END, "🔗 AI分析的概念關聯：\n\n")
        
        # 顯示重要概念
        key_concepts = mindmap_data.get('key_concepts', [])
        if key_concepts:
            text_widget.insert(tk.END, "🎯 重要概念：\n")
            for concept in key_concepts:
                text_widget.insert(tk.END, f"• {concept}\n")
            text_widget.insert(tk.END, "\n")
        
        # 顯示概念連接
        connections = mindmap_data.get('connections', [])
        if connections:
            text_widget.insert(tk.END, "🔗 概念關聯：\n")
            for conn in connections:
                from_concept = conn.get('from', '概念A')
                to_concept = conn.get('to', '概念B')
                relationship = conn.get('relationship', '相關')
                text_widget.insert(tk.END, f"• {from_concept} ➜ {to_concept}\n")
                text_widget.insert(tk.END, f"  關係：{relationship}\n\n")
        
        text_widget.configure(state="disabled")
    
    def run(self):
        """啟動GUI"""
        self.root.mainloop()
