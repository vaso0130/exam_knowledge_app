import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import customtkinter as ctk
import platform
from typing import Dict, Any, List, Optional
import threading
import asyncio
import webbrowser
import urllib.parse
import os
import json
from datetime import datetime

# 導入 markdown 渲染器
from .markdown_renderer import MarkdownText

# 導入心智圖渲染器
from .mindmap_renderer import MindmapRenderer

# 移除圖表功能相關匯入
# try:
#     from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg as FigureCanvasTkinter
# except ImportError:
#     FigureCanvasTkinter = None
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

    def export_knowledge(self):
        """匯出整個知識庫到 JSON 檔案"""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="匯出知識庫"
            )
            if not file_path:
                return

            self.update_status("正在匯出知識庫...")
            
            # 獲取所有資料
            documents = self.db.get_all_documents()
            all_data = []

            for doc_tuple in documents:
                doc_id, title, content, doc_type, subject, file_path_db, created_at = doc_tuple
                doc_data = {
                    "id": doc_id,
                    "title": title,
                    "content": content,
                    "type": doc_type,
                    "subject": subject,
                    "file_path": file_path_db,
                    "created_at": created_at,
                    "questions": []
                }
                
                questions = self.db.get_questions_by_document(doc_id)
                for q_tuple in questions:
                    q_id, _, q_text, a_text, q_subject, q_created_at = q_tuple
                    doc_data["questions"].append({
                        "id": q_id,
                        "question_text": q_text,
                        "answer_text": a_text,
                        "subject": q_subject,
                        "created_at": q_created_at
                    })
                all_data.append(doc_data)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=4)

            self.update_status("知識庫匯出成功！")
            messagebox.showinfo("成功", f"知識庫已成功匯出到 {file_path}")

        except Exception as e:
            self.show_error(f"匯出知識庫失敗: {e}")
            self.update_status("匯出失敗。")

    def import_knowledge(self):
        """從 JSON 檔案匯入知識庫"""
        try:
            file_path = filedialog.askopenfilename(
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="匯入知識庫"
            )
            if not file_path:
                return

            if not messagebox.askyesno("確認", "這將會將檔案中的資料添加到現有知識庫中。確定要繼續嗎？"):
                return

            self.update_status("正在匯入知識庫...")

            with open(file_path, 'r', encoding='utf-8') as f:
                imported_data = json.load(f)

            # 為了避免主鍵衝突，我們將重新插入資料，讓資料庫分配新的 ID
            for doc_data in imported_data:
                # 插入文件
                new_doc_id = self.db.insert_document(
                    title=doc_data['title'],
                    content=doc_data['content'],
                    doc_type=doc_data['type'],
                    subject=doc_data['subject'],
                    file_path=doc_data.get('file_path')
                )
                
                # 插入相關問題
                for q_data in doc_data.get('questions', []):
                    self.db.insert_question(
                        document_id=new_doc_id,
                        question_text=q_data['question_text'],
                        answer_text=q_data['answer_text'],
                        subject=q_data.get('subject', doc_data['subject']) # 使用問題的科目，如果沒有則用文件的
                    )
            
            self.db.conn.commit()

            self.update_status("知識庫匯入成功！")
            messagebox.showinfo("成功", "知識庫已成功匯入。")
            
            # 刷新視圖
            self.refresh_view()

        except Exception as e:
            self.show_error(f"匯入知識庫失敗: {e}")
            self.update_status("匯入失敗。")

    def export_data(self):
        """匯出資料"""
        # 目前，這只會呼叫更具體的知識匯出
        self.export_knowledge()
    
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
        
        # 輸入模式切換按鈕和小型輸入框
        top_input_frame = ctk.CTkFrame(input_frame)
        top_input_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        # 切換按鈕
        self.expand_btn = ctk.CTkButton(
            top_input_frame,
            text="📝 展開輸入",
            command=self.toggle_input_mode,
            font=ctk.CTkFont(size=12),
            height=30,
            width=100
        )
        self.expand_btn.pack(side="left", padx=(0, 10))
        
        # URL/文字/搜尋輸入框
        self.input_entry = ctk.CTkEntry(
            top_input_frame,
            placeholder_text="拖放檔案、貼上網址、輸入文字或網路搜尋...",
            font=ctk.CTkFont(size=14),
            height=30
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        # 處理按鈕
        self.process_btn = ctk.CTkButton(
            top_input_frame,
            text="處理",
            command=self.process_input,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=30,
            width=80
        )
        self.process_btn.pack(side="left", padx=(0, 5))

        # 網路搜尋按鈕
        self.web_search_btn = ctk.CTkButton(
            top_input_frame,
            text="🔍 搜尋",
            command=self.perform_web_search,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=30,
            width=80,
            fg_color="green",
            hover_color="darkgreen"
        )
        self.web_search_btn.pack(side="right")
        
        # 大型輸入區域（可展開/收起）
        self.expanded_input_frame = ctk.CTkFrame(input_frame)
        self.expanded_input_visible = False
        
        # 大型文字輸入區域
        self.large_input_text = ctk.CTkTextbox(
            self.expanded_input_frame,
            height=200,
            font=ctk.CTkFont(size=14),
            wrap="word"
        )
        self.large_input_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 大型輸入區域的按鈕
        large_input_buttons = ctk.CTkFrame(self.expanded_input_frame)
        large_input_buttons.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkButton(
            large_input_buttons,
            text="處理文字內容",
            command=self.process_large_input,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=35
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            large_input_buttons,
            text="清空",
            command=lambda: self.large_input_text.delete("1.0", "end"),
            font=ctk.CTkFont(size=14),
            height=35,
            fg_color="gray",
            hover_color="darkgray"
        ).pack(side="left")
        
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
        """建立左側面板（可收起）"""
        # 左側面板容器
        self.left_panel_container = ctk.CTkFrame(parent)
        self.left_panel_container.pack(side="left", fill="y", padx=(0, 5))
        
        # 切換按鈕框架
        toggle_frame = ctk.CTkFrame(self.left_panel_container)
        toggle_frame.pack(fill="x", padx=2, pady=2)
        
        # 面板切換按鈕
        self.panel_toggle_btn = ctk.CTkButton(
            toggle_frame,
            text="◀ 收起",
            command=self.toggle_left_panel,
            font=ctk.CTkFont(size=12),
            height=30,
            width=80
        )
        self.panel_toggle_btn.pack(side="right", padx=5, pady=5)
        
        # 左側面板內容
        self.left_panel = ctk.CTkFrame(self.left_panel_container)
        self.left_panel.pack(fill="both", expand=True, padx=2, pady=(0, 2))
        self.left_panel.configure(width=300)
        self.left_panel_visible = True
        
        # 標題
        title_label = ctk.CTkLabel(
            self.left_panel,
            text="科目與篩選",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_label.pack(pady=(10, 5))
        
        # 科目選擇
        subject_frame = ctk.CTkFrame(self.left_panel)
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
        search_frame = ctk.CTkFrame(self.left_panel)
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
        kb_frame = ctk.CTkFrame(self.left_panel)
        kb_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            kb_frame,
            text="知識庫管理:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        # 知識庫操作按鈕
        kb_buttons_frame = ctk.CTkFrame(kb_frame)
        kb_buttons_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.kb_export_btn = ctk.CTkButton(
            kb_buttons_frame,
            text="📤 匯出",
            command=self.export_knowledge,
            height=30,
            font=ctk.CTkFont(size=10)
        )
        self.kb_export_btn.pack(side="left", padx=(0, 5), fill="x", expand=True)
        
        self.kb_import_btn = ctk.CTkButton(
            kb_buttons_frame,
            text="📥 匯入",
            command=self.import_knowledge,
            height=30,
            font=ctk.CTkFont(size=10)
        )
        self.kb_import_btn.pack(side="right", padx=(5, 0), fill="x", expand=True)
        
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
        tags_frame = ctk.CTkFrame(self.left_panel)
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
        stats_frame = ctk.CTkFrame(self.left_panel)
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
        
        # 移除圖表按鈕，保留心智圖按鈕
        # self.chart_btn = ctk.CTkButton(op_frame, text="📊 圖表", 
        #                              command=self.show_charts,
        #                              fg_color="green", hover_color="darkgreen")
        # self.chart_btn.pack(side='right', padx=5)
        
        self.mindmap_btn = ctk.CTkButton(op_frame, text="🧠 AI心智圖", 
                                        command=self.generate_ai_mindmap,
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
            # 獲取所有題目
            questions = self.db.get_all_questions_with_source()
            
            # 首先根據科目篩選
            if hasattr(self, 'current_subject') and self.current_subject and self.current_subject != "全部":
                filtered_by_subject = []
                for question in questions:
                    question_id, subject, question_text, answer_text, doc_title, created_at = question
                    if subject == self.current_subject:
                        filtered_by_subject.append(question)
                questions = filtered_by_subject
            
            # 然後根據選中的標籤篩選題目
            if self.selected_tags:
                filtered_questions = []
                for question in questions:
                    question_id, subject, question_text, answer_text, doc_title, created_at = question
                    
                    # 檢查題目內容是否包含選中的標籤
                    question_content = (question_text or "") + " " + (answer_text or "")
                    
                    # 如果任何一個標籤在題目內容中出現，就包含這個題目
                    if any(tag in question_content for tag in self.selected_tags):
                        filtered_questions.append(question)
                        
                questions = filtered_questions
            
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
        self.refresh_document_list()
        self.update_statistics()
        self.load_tags()
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
        
        # 表格顯示切換 (移除)
        # self.show_table_var = tk.BooleanVar(value=False)
        # self.table_toggle_btn = ctk.CTkButton(
        #     control_frame,
        #     text="顯示表格",
        #     command=self.toggle_table_visibility,
        #     font=ctk.CTkFont(size=12),
        #     state="disabled" # 初始為禁用
        # )
        # self.table_toggle_btn.pack(side="left", padx=10, pady=5)
        
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
        
        # --- Markdown 預覽標籤頁 ---
        self.markdown_tab_frame = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(self.markdown_tab_frame, text="📄 預覽")
        
        # 使用自定義的 MarkdownText 組件
        try:
            font_family = "Courier New" if platform.system() == "Windows" else "Menlo"
        except:
            font_family = "monospace"
        
        self.markdown_text = MarkdownText(
            self.markdown_tab_frame,
            font=(font_family, 11),
            height=15,
            table_callback=self.display_table_in_new_tab # 改為在新分頁顯示
        )
        self.markdown_text.pack(fill="both", expand=True)
        
        # --- 詳細資訊標籤頁 ---
        self.detail_frame = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(self.detail_frame, text="ℹ️ 詳細資訊")
        
        self.detail_text = scrolledtext.ScrolledText(
            self.detail_frame,
            wrap=tk.WORD,
            font=(font_family, 11),
            height=15
        )
        self.detail_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # --- 心智圖標籤頁 ---
        self.mindmap_frame = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(self.mindmap_frame, text="🧠 心智圖")
        
        # 使用新的心智圖渲染器
        self.mindmap_renderer = MindmapRenderer(self.mindmap_frame)
        self.mindmap_renderer.pack(fill="both", expand=True)
        
        self.current_preview_data = None
        self.table_tabs = [] # 用於追蹤表格分頁

    def display_table_in_new_tab(self, headers: list, rows: list):
        """在新的分頁中顯示表格"""
        if not headers and not rows:
            return

        # 創建一個新的分頁來顯示表格
        tab_title = f"📊 表格 ({headers[0]})"
        table_tab = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(table_tab, text=tab_title)
        self.table_tabs.append(table_tab)

        # 設定 Treeview 樣式
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#ffffff",
                        foreground="#333333",
                        rowheight=25,
                        fieldbackground="#ffffff")
        style.map('Treeview', background=[('selected', '#0078d4')])

        treeview = ttk.Treeview(table_tab, columns=headers, show="headings", style="Treeview")
        
        # 設定欄位
        for header in headers:
            treeview.heading(header, text=header, anchor='w')
            treeview.column(header, anchor="w", width=120, stretch=True)

        # 插入資料
        for row in rows:
            display_row = row[:len(headers)]
            while len(display_row) < len(headers):
                display_row.append("")
            treeview.insert("", "end", values=display_row)

        # 滾動條
        yscroll = ttk.Scrollbar(table_tab, orient="vertical", command=treeview.yview)
        xscroll = ttk.Scrollbar(table_tab, orient="horizontal", command=treeview.xview)
        treeview.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        treeview.pack(side="left", fill="both", expand=True)
        
        # 自動切換到新建立的分頁
        self.preview_notebook.select(table_tab)

    def clear_existing_table_tabs(self):
        """清除所有已存在的表格分頁"""
        for tab in self.table_tabs:
            if tab.winfo_exists():
                self.preview_notebook.forget(tab)
        self.table_tabs.clear()
        
    def create_web_search_tab(self, parent):
        """建立網路搜尋結果的顯示介面"""
        # 主框架
        search_frame = ctk.CTkFrame(parent)
        search_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 搜尋摘要區
        summary_frame = ctk.CTkFrame(search_frame)
        summary_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(summary_frame, text="搜尋摘要", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        self.web_search_summary = ctk.CTkTextbox(
            summary_frame,
            height=100,
            wrap="word",
            font=ctk.CTkFont(size=12)
        )
        self.web_search_summary.pack(fill="x", expand=True, padx=10, pady=(0, 10))
        self.web_search_summary.insert("1.0", "請在上方輸入框輸入搜尋查詢...")

        # 搜尋來源區
        sources_frame = ctk.CTkFrame(search_frame)
        sources_frame.pack(fill="both", expand=True)
        
        ctk.CTkLabel(sources_frame, text="參考來源", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        # 使用 Treeview 顯示來源
        source_columns = ("title", "url")
        self.web_search_tree = ttk.Treeview(
            sources_frame,
            columns=source_columns,
            show="headings",
            height=5
        )
        self.web_search_tree.heading("title", text="標題")
        self.web_search_tree.heading("url", text="網址")
        self.web_search_tree.column("title", width=300)
        self.web_search_tree.column("url", width=400)
        
        # 滾動條
        tree_scroll = ttk.Scrollbar(sources_frame, orient="vertical", command=self.web_search_tree.yview)
        self.web_search_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.web_search_tree.pack(side="left", fill="both", expand=True, padx=10, pady=(0, 10))
        tree_scroll.pack(side="right", fill="y", pady=(0, 10))
        
        # 綁定雙擊事件以開啟網頁
        self.web_search_tree.bind("<Double-1>", self.on_source_double_click)

    def on_source_double_click(self, event):
        """處理來源雙擊事件，在瀏覽器中開啟連結"""
        selection = self.web_search_tree.selection()
        if selection:
            item = self.web_search_tree.item(selection[0])
            url = item['values'][1]
            if url and url.startswith("http"):
                try:
                    webbrowser.open(url, new=2)
                except Exception as e:
                    self.show_error(f"無法開啟連結: {e}")

    def toggle_table_visibility(self):
        """切換表格 Treeview 的可見性"""
        if self.preview_pane.paneconfig(self.table_container, "hide") == '0':
            # 目前是可見的，將其隱藏
            self.preview_pane.paneconfig(self.table_container, height=0, hide=True)
            self.table_toggle_btn.configure(text="顯示表格")
        else:
            # 目前是隱藏的，將其顯示
            self.preview_pane.paneconfig(self.table_container, height=200, hide=False)
            self.table_toggle_btn.configure(text="隱藏表格")

    def display_table_in_treeview(self, headers: list, rows: list):
        """在 Treeview 中顯示表格"""
        # 清空舊表格
        for item in self.table_treeview.get_children():
            self.table_treeview.delete(item)
        self.table_treeview["columns"] = []

        if not headers and not rows:
            # 如果沒有資料，隱藏表格視圖並禁用按鈕
            self.preview_pane.paneconfig(self.table_container, height=0, hide=True)
            self.table_toggle_btn.configure(state="disabled", text="顯示表格")
            return

        # 有資料，啟用按鈕但預設不顯示
        self.table_toggle_btn.configure(state="normal")
        self.preview_pane.paneconfig(self.table_container, height=0, hide=True)
        self.table_toggle_btn.configure(text="顯示表格")

        # 設定欄位
        self.table_treeview["columns"] = headers
        for header in headers:
            self.table_treeview.heading(header, text=header, anchor='w')
            self.table_treeview.column(header, anchor="w", width=120, stretch=True)

        for row in rows:
            display_row = row[:len(headers)]
            while len(display_row) < len(headers):
                display_row.append("")
            self.table_treeview.insert("", "end", values=display_row)
    
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
    
    def toggle_input_mode(self):
        """切換輸入模式"""
        if self.expanded_input_visible:
            # 收起大型輸入區域
            self.expanded_input_frame.pack_forget()
            self.expand_btn.configure(text="📝 展開輸入")
            self.expanded_input_visible = False
        else:
            # 展開大型輸入區域
            self.expanded_input_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
            self.expand_btn.configure(text="🔼 收起輸入")
            self.expanded_input_visible = True
    
    def toggle_left_panel(self):
        """切換左側面板顯示/隱藏"""
        if self.left_panel_visible:
            # 隱藏左側面板
            self.left_panel.pack_forget()
            self.panel_toggle_btn.configure(text="▶ 展開")
            self.left_panel_visible = False
            # 設定最小寬度
            self.left_panel_container.configure(width=100)
        else:
            # 顯示左側面板
            self.left_panel.pack(fill="both", expand=True, padx=2, pady=(0, 2))
            self.panel_toggle_btn.configure(text="◀ 收起")
            self.left_panel_visible = True
            # 恢復正常寬度
            self.left_panel_container.configure(width=300)
    
    def process_large_input(self):
        """處理大型輸入區域的內容"""
        input_text = self.large_input_text.get("1.0", "end-1c").strip()
        if not input_text:
            messagebox.showwarning("警告", "請輸入內容")
            return
        
        # 禁用處理按鈕，顯示進度
        self.process_btn.configure(state="disabled", text="處理中...")
        self.progress_bar.set(0.1)
        self.update_status("正在處理大型輸入內容...")
        
        # 在後台執行處理
        threading.Thread(target=self._process_input_background, args=(input_text,)).start()

    def perform_web_search(self):
        """執行網路搜尋"""
        query = self.input_entry.get().strip()
        if not query:
            messagebox.showwarning("警告", "請輸入要搜尋的關鍵字")
            return

        # 切換到網路搜尋分頁
        self.preview_notebook.select(3) # 假設網路搜尋是第4個分頁

        # 更新狀態並禁用按鈕
        self.update_status(f"正在進行網路搜尋: {query}...")
        self.web_search_btn.configure(state="disabled", text="搜尋中...")
        self.web_search_summary.delete("1.0", tk.END)
        self.web_search_summary.insert("1.0", f"正在搜尋「{query}」，請稍候...")
        for item in self.web_search_tree.get_children():
            self.web_search_tree.delete(item)

        # 在背景執行緒中執行搜尋
        threading.Thread(target=self._perform_web_search_background, args=(query,)).start()

    def _perform_web_search_background(self, query: str):
        """在背景執行緒中執行網路搜尋"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            search_results = loop.run_until_complete(
                self.content_processor.gemini_client.web_search(query)
            )
            
            # 在主執行緒中更新 UI
            self.root.after(0, self._on_web_search_complete, search_results)
            
        except Exception as e:
            error_msg = f"網路搜尋失敗: {str(e)}"
            self.root.after(0, self._on_web_search_error, error_msg)
        finally:
            loop.close()

    def _on_web_search_complete(self, results: Dict[str, Any]):
        """網路搜尋完成後的回調"""
        self.web_search_btn.configure(state="normal", text="🔍 搜尋")
        self.update_status("網路搜尋完成")

        # 更新摘要
        self.web_search_summary.delete("1.0", tk.END)
        self.web_search_summary.insert("1.0", results.get("summary", "沒有找到摘要。"))

        # 更新來源列表
        for item in self.web_search_tree.get_children():
            self.web_search_tree.delete(item)
        
        for source in results.get("sources", []):
            self.web_search_tree.insert("", "end", values=(
                source.get("title", "無標題"),
                source.get("url", "")
            ))

    def _on_web_search_error(self, error_msg: str):
        """網路搜尋失敗的回調"""
        self.web_search_btn.configure(state="normal", text="🔍 搜尋")
        self.update_status(error_msg)
        self.web_search_summary.delete("1.0", tk.END)
        self.web_search_summary.insert("1.0", error_msg)
        self.show_error(error_msg)
        
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
        if self.current_view == "documents":
            self.refresh_document_list()
        else:
            self.refresh_question_list()
    
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
        # 清除舊的表格分頁和心智圖
        self.clear_existing_table_tabs()
        self.mindmap_renderer.clear()
        
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
            
            # 處理不同的 values 格式
            question_id = None
            
            if isinstance(values, (list, tuple)) and len(values) > 0:
                question_id_str = values[0]  # 格式: "Q123"
                if isinstance(question_id_str, str) and question_id_str.startswith('Q'):
                    try:
                        question_id = int(question_id_str[1:])
                    except ValueError:
                        raise ValueError(f"無法從 '{question_id_str}' 解析問題ID")
                elif isinstance(question_id_str, str):
                    # 嘗試直接轉換字符串為整數
                    try:
                        question_id = int(question_id_str)
                    except ValueError:
                        raise ValueError(f"無法將 '{question_id_str}' 轉換為整數")
                elif isinstance(question_id_str, int):
                    question_id = question_id_str
                else:
                    raise ValueError(f"無法處理的問題ID格式: {type(question_id_str)} - {question_id_str}")
            elif isinstance(values, int):
                question_id = values
            else:
                raise ValueError(f"無法解析問題ID，未知格式: {type(values)} - {values}")
            
            if question_id is None:
                raise ValueError("問題ID為空")
            
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
                
            else:
                raise ValueError("未找到對應的問題資料")
            
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
        """載入標籤資料（基於內容關鍵詞）"""
        try:
            # 清除現有標籤
            for widget in self.tags_scrollable.winfo_children():
                widget.destroy()
            self.tag_vars.clear()
            
            # 從文件內容和題目中提取關鍵詞作為標籤
            cursor = self.db.cursor
            
            # 獲取所有文件標題和內容
            cursor.execute('''
                SELECT title, content FROM documents 
                WHERE title IS NOT NULL AND title != ""
            ''')
            documents = cursor.fetchall()
            
            # 獲取所有題目
            cursor.execute('''
                SELECT question_text FROM questions 
                WHERE question_text IS NOT NULL AND question_text != ""
            ''')
            questions = cursor.fetchall()
            
            # 提取關鍵詞
            keywords = set()
            
            # 從標題中提取關鍵詞
            for title, content in documents:
                if title:
                    # 提取標題中的關鍵詞（長度3-8的中文詞彙）
                    import re
                    words = re.findall(r'[\u4e00-\u9fff]{3,8}', title)
                    keywords.update(words)
            
            # 添加一些常見的技術標籤
            common_tags = [
                "資料結構", "演算法", "資料庫", "網路安全", "程式設計",
                "系統分析", "專案管理", "資訊系統", "軟體工程", "資料庫設計",
                "網路協定", "資訊安全", "系統設計", "軟體測試", "需求分析"
            ]
            
            # 檢查哪些常見標籤在內容中出現
            all_content = " ".join([doc[1] or "" for doc in documents])
            all_content += " ".join([q[0] or "" for q in questions])
            
            relevant_tags = []
            for tag in common_tags:
                if tag in all_content:
                    relevant_tags.append(tag)
            
            # 也添加從標題提取的關鍵詞
            relevant_tags.extend(list(keywords)[:10])  # 限制數量
            
            # 創建標籤複選框
            for tag in relevant_tags[:15]:  # 最多15個標籤
                var = ctk.BooleanVar()
                checkbox = ctk.CTkCheckBox(
                    self.tags_scrollable,
                    text=tag,
                    variable=var,
                    command=self.on_tag_filter_changed
                )
                checkbox.pack(anchor="w", padx=5, pady=2)
                self.tag_vars[tag] = var
                
        except Exception as e:
            print(f"載入標籤失敗: {e}")
    
    def on_tag_filter_changed(self):
        """標籤篩選變更時的回調"""
        selected_tags = [tag for tag, var in self.tag_vars.items() if var.get()]
        self.selected_tags = selected_tags
        
        # 根據當前視圖決定刷新哪個列表
        if self.current_view == "documents":
            self.refresh_document_list()
        else:
            self.refresh_question_list()
    
    def refresh_document_list(self):
        """刷新文件列表"""
        self.file_tree.delete(*self.file_tree.get_children())
        
        try:
            # 更新列標題
            self.setup_tree_columns()
            
            # 獲取文件
            documents = self.db.get_all_documents()
            
            # 首先根據科目篩選
            if hasattr(self, 'current_subject') and self.current_subject and self.current_subject != "全部":
                filtered_by_subject = []
                for doc in documents:
                    doc_id, title, content, doc_type, subject, file_path, created_at = doc
                    if subject == self.current_subject:
                        filtered_by_subject.append(doc)
                documents = filtered_by_subject
            
            # 然後根據選中的標籤篩選文件
            if self.selected_tags:
                filtered_documents = []
                for doc in documents:
                    doc_id, title, content, doc_type, subject, file_path, created_at = doc
                    
                    # 檢查標題和內容是否包含選中的標籤
                    doc_text = (title or "") + " " + (content or "")
                    
                    # 如果任何一個標籤在文件內容中出現，就包含這個文件
                    if any(tag in doc_text for tag in self.selected_tags):
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
    
    # 舊的心智圖相關方法已被新的渲染器取代
    # copy_mermaid_code 和 open_mermaid_preview 已內建於 MindmapRenderer
    
    def regenerate_mindmap(self):
        """重新生成心智圖（忽略已儲存的版本）"""
        try:
            # 確保有選中項目
            selection = self.file_tree.selection()
            if not selection:
                self.show_error("請先在列表中選擇一個文件或問題。")
                return
            
            # 切換到心智圖標籤頁
            self.preview_notebook.select(2)
            
            # 顯示正在生成的提示
            self.mindmap_renderer.status_label.configure(text="🧠 正在重新生成 AI 心智圖，請稍候...")
            self.root.update_idletasks()

            # 在背景執行緒中強制重新生成心智圖
            threading.Thread(target=self._force_regenerate_mindmap_background, args=(selection[0],)).start()
                
        except Exception as e:
            self.show_error(f"重新生成心智圖時發生錯誤: {str(e)}")

    def _force_regenerate_mindmap_background(self, selected_item):
        """強制重新生成心智圖（不檢查已儲存的版本）"""
        try:
            item_values = self.file_tree.item(selected_item)['values']
            
            # 獲取用於生成心智圖的文本
            if self.current_view == "documents":
                doc_id = item_values[0]
                document = self.db.get_document_by_id(doc_id)
                text_to_summarize = document.get('content', '')
            else: # questions
                question_id_str = item_values[0]
                question_id = int(question_id_str[1:])
                question_data = self.db.get_question_by_id(question_id)
                text_to_summarize = f"題目：{question_data.get('question_text', '')}\n答案：{question_data.get('answer_text', '')}"
                doc_id = None

            if not text_to_summarize.strip():
                mermaid_code = "mindmap\n  root((內容為空))\n    無法生成心智圖"
            else:
                # 呼叫 Gemini API 生成心智圖
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                mermaid_code = loop.run_until_complete(
                    self.content_processor.gemini_client.generate_mindmap(text_to_summarize)
                )
                loop.close()
                
                # 如果是文件，更新資料庫中的心智圖
                if self.current_view == "documents" and doc_id:
                    self.db.update_document_mindmap(doc_id, mermaid_code)

            # 在主執行緒更新 UI
            self.root.after(0, self.update_mindmap_display, mermaid_code)

        except Exception as e:
            error_message = f"mindmap\n  root((重新生成失敗))\n    錯誤: {str(e)}"
            self.root.after(0, self.update_mindmap_display, error_message)

    # open_mermaid_preview 方法已內建於 MindmapRenderer
    
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
    
    def update_quick_stats(self):
        """更新快速統計標籤"""
        try:
            stats = self.db.get_statistics()
            doc_count = stats.get('total_documents', 0)
            q_count = stats.get('total_questions', 0)
            self.quick_stats_label.configure(text=f"📚 文件: {doc_count} | 📝 題目: {q_count}")
        except Exception as e:
            self.quick_stats_label.configure(text="統計載入失敗")
            print(f"更新快速統計失敗: {e}")

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
                
            else:
                raise ValueError("未找到對應的文件資料")
            
        except Exception as e:
            self.show_error(f"預覽文件失敗: {str(e)}")
            # 顯示錯誤訊息
            error_content = f"# 預覽失敗\n\n無法載入文件內容: {str(e)}"
            self.markdown_text.set_markdown(error_content)
    
    def show_document_detail(self, document_info):
        """顯示文件詳情"""
        # 實作詳情顯示邏輯
        pass

    def export_knowledge(self):
        """匯出整個知識庫到 JSON 檔案"""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="匯出知識庫"
            )
            if not file_path:
                return

            self.update_status("正在匯出知識庫...")
            
            # 獲取所有資料
            documents = self.db.get_all_documents()
            all_data = []

            for doc_tuple in documents:
                doc_id, title, content, doc_type, subject, file_path_db, created_at = doc_tuple
                doc_data = {
                    "id": doc_id,
                    "title": title,
                    "content": content,
                    "type": doc_type,
                    "subject": subject,
                    "file_path": file_path_db,
                    "created_at": created_at,
                    "questions": []
                }
                
                questions = self.db.get_questions_by_document(doc_id)
                for q_tuple in questions:
                    q_id, _, q_text, a_text, q_subject, q_created_at = q_tuple
                    doc_data["questions"].append({
                        "id": q_id,
                        "question_text": q_text,
                        "answer_text": a_text,
                        "subject": q_subject,
                        "created_at": q_created_at
                    })
                all_data.append(doc_data)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=4)

            self.update_status("知識庫匯出成功！")
            messagebox.showinfo("成功", f"知識庫已成功匯出到 {file_path}")

        except Exception as e:
            self.show_error(f"匯出知識庫失敗: {e}")
            self.update_status("匯出失敗。")

    def import_knowledge(self):
        """從 JSON 檔案匯入知識庫"""
        try:
            file_path = filedialog.askopenfilename(
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="匯入知識庫"
            )
            if not file_path:
                return

            if not messagebox.askyesno("確認", "這將會將檔案中的資料添加到現有知識庫中。確定要繼續嗎？"):
                return

            self.update_status("正在匯入知識庫...")

            with open(file_path, 'r', encoding='utf-8') as f:
                imported_data = json.load(f)

            # 為了避免主鍵衝突，我們將重新插入資料，讓資料庫分配新的 ID
            for doc_data in imported_data:
                # 插入文件
                new_doc_id = self.db.insert_document(
                    title=doc_data['title'],
                    content=doc_data['content'],
                    doc_type=doc_data['type'],
                    subject=doc_data['subject'],
                    file_path=doc_data.get('file_path')
                )
                
                # 插入相關問題
                for q_data in doc_data.get('questions', []):
                    self.db.insert_question(
                        document_id=new_doc_id,
                        question_text=q_data['question_text'],
                        answer_text=q_data['answer_text'],
                        subject=q_data.get('subject', doc_data['subject']) # 使用問題的科目，如果沒有則用文件的
                    )
            
            self.db.conn.commit()

            self.update_status("知識庫匯入成功！")
            messagebox.showinfo("成功", "知識庫已成功匯入。")
            
            # 刷新視圖
            self.refresh_view()

        except Exception as e:
            self.show_error(f"匯入知識庫失敗: {e}")
            self.update_status("匯入失敗。")

    def export_data(self):
        """匯出資料"""
        # 目前，這只會呼叫更具體的知識匯出
        self.export_knowledge()
    
    def show_statistics(self):
        """顯示統計資料"""
        try:
            stats = self.db.get_statistics()
            
            stats_text = f"""
📊 知識庫統計資訊

📚 文件統計：
   總文件數：{stats.get('total_documents', 0)}
   考試題目：{stats.get('exam_documents', 0)}
   參考資料：{stats.get('info_documents', 0)}

📝 題目統計：
   總題目數：{stats.get('total_questions', 0)}

📋 科目分布：
"""
            
            # 添加科目統計
            cursor = self.db.cursor
            cursor.execute('''
                SELECT subject, COUNT(*) as count
                FROM documents 
                WHERE subject IS NOT NULL AND subject != ""
                GROUP BY subject
                ORDER BY count DESC
            ''')
            
            for subject, count in cursor.fetchall():
                stats_text += f"   {subject}：{count} 項\n"
            
            messagebox.showinfo("📊 統計資料", stats_text)
            
        except Exception as e:
            messagebox.showerror("錯誤", f"載入統計資料失敗: {str(e)}")
    
    def show_error(self, message):
        """顯示錯誤訊息"""
        messagebox.showerror("錯誤", message)
    
    def show_success(self, message):
        """顯示成功訊息"""
        messagebox.showinfo("成功", message)
    
    def show_charts(self):
        """顯示統計資訊（移除圖表功能）"""
        try:
            self.show_statistics()
        except Exception as e:
            self.show_error(f"顯示統計失敗: {str(e)}")
    
    def show_mindmap(self):
        """顯示當前選中文件的 Mermaid 心智圖"""
        try:
            # 確保有選中項目
            selection = self.file_tree.selection()
            if not selection:
                self.show_error("請先在列表中選擇一個文件或問題。")
                return
            
            # 切換到心智圖標籤頁
            self.preview_notebook.select(2) # 假設心智圖是第3個標籤頁
            
            # 顯示正在生成的提示
            self.mindmap_renderer.status_label.configure(text="🧠 正在生成 AI 心智圖，請稍候...")
            self.root.update_idletasks()

            # 在背景執行緒中生成心智圖
            threading.Thread(target=self._generate_mindmap_background, args=(selection[0],)).start()
                
        except Exception as e:
            self.show_error(f"顯示心智圖時發生錯誤: {str(e)}")
    
    def _generate_mindmap_background(self, selected_item):
        """在背景執行緒中生成並顯示心智圖"""
        try:
            item_values = self.file_tree.item(selected_item)['values']
            
            if self.current_view == "questions":
                # 處理題庫心智圖（有快取）
                question_id_str = item_values[0]
                question_id = int(question_id_str[1:])
                question_data = self.db.get_question_by_id(question_id)
                
                # 檢查是否已有儲存的心智圖
                existing_mindmap = question_data.get('mindmap_code')
                if existing_mindmap and existing_mindmap.strip():
                    self.root.after(0, self.update_mindmap_display, existing_mindmap)
                    return
                
                # 沒有快取，生成新的心智圖
                text_to_summarize = f"題目：{question_data.get('question_text', '')}\n答案：{question_data.get('answer_text', '')}"
                
                if not text_to_summarize.strip():
                    mermaid_code = "mindmap\n  root((內容為空))\n    無法生成心智圖"
                else:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    mermaid_code = loop.run_until_complete(
                        self.content_processor.gemini_client.generate_mindmap(text_to_summarize)
                    )
                    loop.close()
                    
                    # 將生成的心智圖儲存到資料庫
                    self.db.update_question_mindmap(question_id, mermaid_code)
                
                self.root.after(0, self.update_mindmap_display, mermaid_code)

            else: # documents view
                # 處理文件心智圖（無快取，總是重新生成）
                doc_id = item_values[0]
                document = self.db.get_document_by_id(doc_id)
                text_to_summarize = document.get('content', '')

                if not text_to_summarize.strip():
                    mermaid_code = "mindmap\n  root((內容為空))\n    無法生成心智圖"
                else:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    mermaid_code = loop.run_until_complete(
                        self.content_processor.gemini_client.generate_mindmap(text_to_summarize)
                    )
                    loop.close()
                
                # 不儲存文件的心智圖，直接顯示
                self.root.after(0, self.update_mindmap_display, mermaid_code)

        except Exception as e:
            error_message = f"mindmap\n  root((生成失敗))\n    錯誤: {str(e)}"
            self.root.after(0, self.update_mindmap_display, error_message)

    def update_mindmap_display(self, mermaid_code: str):
        """在主執行緒中更新心智圖顯示"""
        # 使用新的心智圖渲染器
        self.mindmap_renderer.set_mermaid_code(mermaid_code)

    def generate_document_mindmap(self, document_info):
        """為選中的文件生成心智圖"""
        try:
            doc_id = document_info[0]
            document = self.db.get_document_by_id(doc_id)
            questions = self.db.get_questions_by_document(doc_id)
            
            # 使用舊的靜態生成邏輯作為備用
            mermaid_code = self.generate_mermaid_mindmap(document, questions)
            
            # 使用新的心智圖渲染器
            self.mindmap_renderer.set_mermaid_code(mermaid_code)
            
            # 切換到心智圖標籤頁
            self.preview_notebook.select(2) # 假設心智圖是第3個標籤頁
                
        except Exception as e:
            self.show_error(f"生成文件心智圖失敗: {str(e)}")
    
    def generate_ai_mindmap(self):
        """AI生成知識心智圖"""
        # 這個方法現在由 show_mindmap 取代
        self.show_mindmap()
    
    def show_chart_window(self, viz_manager, stats):
        pass

    def run(self):
        """啟動 GUI 主迴圈"""
        self.root.mainloop()