import tkinter as tk
import customtkinter as ctk
import random
from typing import List, Dict, Any

# 導入 markdown 渲染器
from .markdown_renderer import MarkdownText

class Reviewer:
    def __init__(self, master: ctk.CTkToplevel, questions: List[Dict[str, Any]], main_app_instance):
        self.master = master
        self.questions = questions
        self.main_app = main_app_instance  # 儲存主應用實例
        self.current_question_index = 0
        
        # 隨機排列問題順序
        random.shuffle(self.questions)
        
        self.setup_ui()
        self.load_question()

    def setup_ui(self):
        """設定複習視窗的 UI"""
        self.master.grid_columnconfigure(0, weight=1)
        self.master.grid_rowconfigure(1, weight=1)

        # 1. 頂部資訊列
        top_frame = ctk.CTkFrame(self.master)
        top_frame.grid(row=0, column=0, padx=20, pady=10, sticky="ew")
        
        self.progress_label = ctk.CTkLabel(top_frame, text="進度: 1/10", font=ctk.CTkFont(size=14))
        self.progress_label.pack(side="left", padx=10)
        
        self.subject_label = ctk.CTkLabel(top_frame, text="科目: 未知", font=ctk.CTkFont(size=14))
        self.subject_label.pack(side="left", padx=10)
        
        self.source_label = ctk.CTkLabel(top_frame, text="來源: 未知", font=ctk.CTkFont(size=12))
        self.source_label.pack(side="right", padx=10)

        # 2. 問題顯示區
        question_frame = ctk.CTkFrame(self.master)
        question_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        question_frame.grid_rowconfigure(0, weight=1)
        question_frame.grid_columnconfigure(0, weight=1)

        self.question_text = ctk.CTkTextbox(
            question_frame,
            wrap="word",
            font=ctk.CTkFont(size=16),
            state="disabled"
        )
        self.question_text.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # 3. 答案顯示區 (使用 MarkdownText)
        self.answer_frame = ctk.CTkFrame(self.master, fg_color="transparent")
        self.answer_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.answer_frame.grid_columnconfigure(0, weight=1)
        
        self.answer_text = MarkdownText(
            self.answer_frame,
            height=10,
            font=("Arial", 12),
            state="disabled"
        )
        # 初始隱藏答案
        # self.answer_text.grid(row=0, column=0, sticky="ew")
        # self.answer_text.grid_remove()

        # 4. 控制按鈕區
        button_frame = ctk.CTkFrame(self.master)
        button_frame.grid(row=3, column=0, padx=20, pady=20, sticky="ew")
        button_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.show_answer_btn = ctk.CTkButton(
            button_frame,
            text="顯示答案",
            command=self.show_answer,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40
        )
        self.show_answer_btn.grid(row=0, column=1, padx=10, pady=5)

        self.prev_btn = ctk.CTkButton(
            button_frame,
            text="上一題",
            command=self.prev_question,
            font=ctk.CTkFont(size=14),
            height=40
        )
        self.prev_btn.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        self.next_btn = ctk.CTkButton(
            button_frame,
            text="下一題",
            command=self.next_question,
            font=ctk.CTkFont(size=14),
            height=40
        )
        self.next_btn.grid(row=0, column=2, padx=10, pady=5, sticky="ew")

    def load_question(self):
        """載入當前問題"""
        if not self.questions:
            self.question_text.configure(state="normal")
            self.question_text.delete("1.0", "end")
            self.question_text.insert("1.0", "沒有可複習的問題。")
            self.question_text.configure(state="disabled")
            return

        q_data = self.questions[self.current_question_index]
        
        # 更新資訊
        self.progress_label.configure(text=f"進度: {self.current_question_index + 1}/{len(self.questions)}")
        self.subject_label.configure(text=f"科目: {q_data.get('subject', 'N/A')}")
        self.source_label.configure(text=f"來源: {q_data.get('doc_title', 'N/A')}")
        
        # 顯示問題
        self.question_text.configure(state="normal")
        self.question_text.delete("1.0", "end")
        self.question_text.insert("1.0", q_data.get('question_text', ''))
        self.question_text.configure(state="disabled")
        
        # 隱藏答案並重置按鈕
        self.answer_text.grid_remove()
        self.show_answer_btn.configure(text="顯示答案", state="normal")
        
        # 更新按鈕狀態
        self.prev_btn.configure(state="normal" if self.current_question_index > 0 else "disabled")
        self.next_btn.configure(state="normal" if self.current_question_index < len(self.questions) - 1 else "disabled")

    def show_answer(self):
        """顯示答案"""
        q_data = self.questions[self.current_question_index]
        
        self.answer_text.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.answer_text.set_content(q_data.get('answer_text', '沒有提供答案。'))
        
        self.show_answer_btn.configure(text="答案已顯示", state="disabled")

    def next_question(self):
        """切換到下一題"""
        if self.current_question_index < len(self.questions) - 1:
            self.current_question_index += 1
            self.load_question()

    def prev_question(self):
        """切換到上一題"""
        if self.current_question_index > 0:
            self.current_question_index -= 1
            self.load_question()
