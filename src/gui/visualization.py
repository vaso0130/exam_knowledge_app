import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_tkagg import FigureCanvasTkinter
import networkx as nx
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any, Tuple
import numpy as np
from datetime import datetime
import json

# 設定中文字體支援
import matplotlib
matplotlib.use('TkAgg')  # 設定後端
import matplotlib.pyplot as plt

# 嘗試設定多種中文字體，增加兼容性
try:
    # macOS 常用字體
    plt.rcParams['font.sans-serif'] = [
        'PingFang SC',      # macOS 預設中文字體
        'Microsoft JhengHei',  # Windows 繁體中文
        'SimHei',           # Windows 簡體中文
        'Arial Unicode MS', # macOS Unicode 字體
        'DejaVu Sans'       # 備用字體
    ]
    plt.rcParams['axes.unicode_minus'] = False
    print("✅ 中文字體設定完成")
except Exception as e:
    print(f"⚠️ 字體設定警告: {e}")

import matplotlib.patches as patches
from matplotlib.backends.backend_tkagg import FigureCanvasTkinter
import networkx as nx
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any, Tuple
import numpy as np
from datetime import datetime
import json

class VisualizationManager:
    """視覺化管理器"""
    
    def __init__(self):
        self.colors = {
            '資料結構': '#FF6B6B',
            '資訊管理': '#4ECDC4', 
            '資通網路與資訊安全': '#45B7D1',
            '資料庫應用': '#96CEB4'
        }
        
    def create_subject_pie_chart(self, stats: Dict[str, Any]) -> plt.Figure:
        """建立科目分布圓餅圖"""
        fig, ax = plt.subplots(figsize=(8, 6))
        
        subject_stats = stats.get('subject_statistics', {})
        if not subject_stats:
            ax.text(0.5, 0.5, '暫無資料', ha='center', va='center', fontsize=16)
            return fig
        
        subjects = list(subject_stats.keys())
        counts = list(subject_stats.values())
        colors = [self.colors.get(subject, '#95A5A6') for subject in subjects]
        
        wedges, texts, autotexts = ax.pie(
            counts, 
            labels=subjects,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            textprops={'fontsize': 12}
        )
        
        ax.set_title('各科目文件分布', fontsize=16, fontweight='bold', pad=20)
        
        # 美化文字
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        
        return fig
    
    def create_timeline_chart(self, documents: List[Dict[str, Any]]) -> plt.Figure:
        """建立時間線圖表"""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        if not documents:
            ax.text(0.5, 0.5, '暫無資料', ha='center', va='center', fontsize=16)
            return fig
        
        # 按日期分組統計
        date_counts = {}
        for doc in documents:
            created_at = doc.get('created_at', '')
            if created_at:
                date = created_at.split(' ')[0]  # 只取日期部分
                date_counts[date] = date_counts.get(date, 0) + 1
        
        if not date_counts:
            ax.text(0.5, 0.5, '日期資料不完整', ha='center', va='center', fontsize=16)
            return fig
        
        dates = sorted(date_counts.keys())
        counts = [date_counts[date] for date in dates]
        
        ax.plot(dates, counts, marker='o', linewidth=2, markersize=8, color='#3498db')
        ax.fill_between(dates, counts, alpha=0.3, color='#3498db')
        
        ax.set_title('文件建立時間線', fontsize=16, fontweight='bold')
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('文件數量', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # 旋轉x軸標籤避免重疊
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
        
        plt.tight_layout()
        return fig
    
    def create_tag_word_cloud_chart(self, documents: List[Dict[str, Any]]) -> plt.Figure:
        """建立標籤詞雲圖（簡化版）"""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 收集所有標籤
        tag_counts = {}
        for doc in documents:
            # 這裡需要從資料庫獲取相關的問題標籤
            # 簡化處理，直接用假資料示範
            pass
        
        # 簡化版：顯示標籤統計長條圖
        sample_tags = ['演算法', '資料庫設計', '網路安全', '系統分析', '資料結構', '專案管理']
        counts = np.random.randint(1, 20, len(sample_tags))
        
        bars = ax.bar(sample_tags, counts, color=[self.colors.get('資料結構', '#95A5A6')] * len(sample_tags))
        
        ax.set_title('標籤統計', fontsize=16, fontweight='bold')
        ax.set_ylabel('出現次數', fontsize=12)
        
        # 美化長條圖
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                   f'{int(height)}', ha='center', va='bottom')
        
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
        plt.tight_layout()
        
        return fig

class MindMapGenerator:
    """心智圖生成器"""
    
    def __init__(self):
        self.node_colors = {
            'root': '#E74C3C',
            'subject': '#3498DB', 
            'topic': '#2ECC71',
            'subtopic': '#F39C12',
            'detail': '#9B59B6'
        }
    
    def create_mind_map(self, document: Dict[str, Any], questions: List[Dict[str, Any]]) -> plt.Figure:
        """建立心智圖"""
        fig, ax = plt.subplots(figsize=(14, 10))
        
        # 建立網路圖
        G = nx.Graph()
        
        # 添加根節點
        root_title = document.get('summary', '文件')[:20] + '...' if len(document.get('summary', '')) > 20 else document.get('summary', '文件')
        G.add_node('root', label=root_title, node_type='root')
        
        # 添加科目節點
        subject = document.get('subject', '未分類')
        G.add_node('subject', label=subject, node_type='subject')
        G.add_edge('root', 'subject')
        
        # 添加重點節點
        bullets = document.get('bullets', [])
        for i, bullet in enumerate(bullets[:5]):  # 最多顯示5個重點
            bullet_id = f'bullet_{i}'
            bullet_text = bullet[:15] + '...' if len(bullet) > 15 else bullet
            G.add_node(bullet_id, label=bullet_text, node_type='topic')
            G.add_edge('subject', bullet_id)
        
        # 添加標籤節點
        all_tags = set()
        for question in questions:
            if question.get('tags'):
                all_tags.update(question['tags'])
        
        for i, tag in enumerate(list(all_tags)[:8]):  # 最多顯示8個標籤
            tag_id = f'tag_{i}'
            G.add_node(tag_id, label=tag, node_type='subtopic')
            # 連接到相關的重點
            if bullets and i < len(bullets):
                G.add_edge(f'bullet_{i % len(bullets)}', tag_id)
            else:
                G.add_edge('subject', tag_id)
        
        # 添加題目節點
        for i, question in enumerate(questions[:3]):  # 最多顯示3個題目
            q_id = f'question_{i}'
            q_text = question.get('stem', '')[:20] + '...' if len(question.get('stem', '')) > 20 else question.get('stem', '')
            G.add_node(q_id, label=q_text, node_type='detail')
            # 連接到標籤
            if all_tags:
                tag_idx = i % min(len(all_tags), 8)
                G.add_edge(f'tag_{tag_idx}', q_id)
        
        # 設定佈局
        pos = nx.spring_layout(G, k=3, iterations=50)
        
        # 繪製節點
        for node, data in G.nodes(data=True):
            node_type = data.get('node_type', 'detail')
            color = self.node_colors.get(node_type, '#95A5A6')
            size = {'root': 3000, 'subject': 2000, 'topic': 1500, 'subtopic': 1000, 'detail': 800}.get(node_type, 500)
            
            nx.draw_networkx_nodes(
                G, pos, nodelist=[node],
                node_color=color,
                node_size=size,
                alpha=0.8,
                ax=ax
            )
            
            # 添加標籤
            label = data.get('label', node)
            ax.text(
                pos[node][0], pos[node][1], label,
                ha='center', va='center',
                fontsize={'root': 12, 'subject': 11, 'topic': 10, 'subtopic': 9, 'detail': 8}.get(node_type, 8),
                fontweight='bold' if node_type in ['root', 'subject'] else 'normal',
                color='white' if node_type in ['root', 'subject'] else 'black'
            )
        
        # 繪製邊
        nx.draw_networkx_edges(
            G, pos,
            edge_color='#7F8C8D',
            width=1.5,
            alpha=0.6,
            ax=ax
        )
        
        ax.set_title(f'知識心智圖 - {subject}', fontsize=16, fontweight='bold', pad=20)
        ax.axis('off')
        
        plt.tight_layout()
        return fig

class ChartViewer:
    """圖表檢視器"""
    
    def __init__(self, parent_widget):
        self.parent = parent_widget
        self.viz_manager = VisualizationManager()
        self.mindmap_generator = MindMapGenerator()
        
    def show_statistics_charts(self, stats: Dict[str, Any], documents: List[Dict[str, Any]]):
        """顯示統計圖表"""
        # 建立新視窗
        chart_window = tk.Toplevel(self.parent)
        chart_window.title("統計圖表")
        chart_window.geometry("1200x800")
        
        # 建立筆記本控件
        notebook = ttk.Notebook(chart_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 科目分布圖
        pie_frame = ttk.Frame(notebook)
        notebook.add(pie_frame, text="科目分布")
        
        pie_fig = self.viz_manager.create_subject_pie_chart(stats)
        pie_canvas = FigureCanvasTkinter(pie_fig, pie_frame)
        pie_canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # 時間線圖
        timeline_frame = ttk.Frame(notebook)
        notebook.add(timeline_frame, text="時間線")
        
        timeline_fig = self.viz_manager.create_timeline_chart(documents)
        timeline_canvas = FigureCanvasTkinter(timeline_fig, timeline_frame)
        timeline_canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # 標籤統計圖
        tag_frame = ttk.Frame(notebook)
        notebook.add(tag_frame, text="標籤統計")
        
        tag_fig = self.viz_manager.create_tag_word_cloud_chart(documents)
        tag_canvas = FigureCanvasTkinter(tag_fig, tag_frame)
        tag_canvas.get_tk_widget().pack(fill='both', expand=True)
    
    def show_mind_map(self, document: Dict[str, Any], questions: List[Dict[str, Any]]):
        """顯示心智圖"""
        # 建立新視窗
        mindmap_window = tk.Toplevel(self.parent)
        mindmap_window.title(f"心智圖 - {document.get('subject', '未分類')}")
        mindmap_window.geometry("1000x700")
        
        # 建立心智圖
        mindmap_fig = self.mindmap_generator.create_mind_map(document, questions)
        mindmap_canvas = FigureCanvasTkinter(mindmap_fig, mindmap_window)
        mindmap_canvas.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        
        # 添加工具列
        toolbar_frame = tk.Frame(mindmap_window)
        toolbar_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        # 儲存按鈕
        save_btn = tk.Button(
            toolbar_frame,
            text="儲存心智圖",
            command=lambda: self.save_mindmap(mindmap_fig, document)
        )
        save_btn.pack(side='left', padx=5)
        
        # 重新生成按鈕
        regenerate_btn = tk.Button(
            toolbar_frame,
            text="重新生成",
            command=lambda: self.regenerate_mindmap(mindmap_canvas, document, questions)
        )
        regenerate_btn.pack(side='left', padx=5)
    
    def save_mindmap(self, fig: plt.Figure, document: Dict[str, Any]):
        """儲存心智圖"""
        from tkinter import filedialog
        
        file_path = filedialog.asksaveasfilename(
            title="儲存心智圖",
            defaultextension=".png",
            filetypes=[
                ("PNG 圖片", "*.png"),
                ("PDF 檔案", "*.pdf"),
                ("SVG 向量圖", "*.svg")
            ]
        )
        
        if file_path:
            fig.savefig(file_path, dpi=300, bbox_inches='tight')
            tk.messagebox.showinfo("成功", f"心智圖已儲存至 {file_path}")
    
    def regenerate_mindmap(self, canvas, document: Dict[str, Any], questions: List[Dict[str, Any]]):
        """重新生成心智圖"""
        # 清除現有畫布
        canvas.get_tk_widget().destroy()
        
        # 重新生成
        new_fig = self.mindmap_generator.create_mind_map(document, questions)
        new_canvas = FigureCanvasTkinter(new_fig, canvas.master)
        new_canvas.get_tk_widget().pack(fill='both', expand=True)

class DataExporter:
    """資料匯出器"""
    
    @staticmethod
    def export_to_csv(documents: List[Dict[str, Any]], questions: List[Dict[str, Any]], file_path: str):
        """匯出到 CSV"""
        import csv
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # 寫入標題
            writer.writerow(['類型', '科目', '內容', '答案', '標籤', '建立時間'])
            
            # 寫入資料
            for doc in documents:
                doc_questions = [q for q in questions if q['document_id'] == doc['id']]
                
                if doc_questions:
                    for question in doc_questions:
                        writer.writerow([
                            '考題' if doc.get('is_exam') else '資料',
                            doc.get('subject', ''),
                            question.get('stem', ''),
                            question.get('answer', ''),
                            ', '.join(question.get('tags', [])),
                            doc.get('created_at', '')
                        ])
                else:
                    writer.writerow([
                        '考題' if doc.get('is_exam') else '資料',
                        doc.get('subject', ''),
                        doc.get('summary', ''),
                        '',
                        '',
                        doc.get('created_at', '')
                    ])
    
    @staticmethod
    def export_to_json(documents: List[Dict[str, Any]], questions: List[Dict[str, Any]], file_path: str):
        """匯出到 JSON"""
        export_data = {
            'export_time': datetime.now().isoformat(),
            'documents': documents,
            'questions': questions
        }
        
        with open(file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, ensure_ascii=False, indent=2)
    
    @staticmethod
    def export_to_anki(documents: List[Dict[str, Any]], questions: List[Dict[str, Any]], file_path: str):
        """匯出到 Anki 格式"""
        with open(file_path, 'w', encoding='utf-8') as file:
            for doc in documents:
                doc_questions = [q for q in questions if q['document_id'] == doc['id']]
                
                for question in doc_questions:
                    # Anki 格式：正面\t背面\t標籤
                    front = question.get('stem', '')
                    back = question.get('answer', '')
                    tags = ' '.join(question.get('tags', []))
                    
                    file.write(f"{front}\t{back}\t{tags}\n")
