import asyncio
import hashlib
from datetime import datetime
from typing import Dict, Any, List
import os

from ..core.gemini_client import GeminiClient
from ..core.database import DatabaseManager
from ..utils.file_processor import FileProcessor, ContentValidator

class AnswerFlow:
    """考題處理流程"""
    
    def __init__(self, gemini_client: GeminiClient, db_manager: DatabaseManager):
        self.gemini = gemini_client
        self.db = db_manager
        self.data_dir = "./data"
        os.makedirs(self.data_dir, exist_ok=True)
    
    async def process_exam_question(self, raw_text: str) -> Dict[str, Any]:
        """處理考試題目的完整流程"""
        try:
            # 清理文字
            cleaned_text = ContentValidator.clean_text(raw_text)
            
            # 判斷是否為完整考卷（包含多題）
            is_exam_paper = await self._is_exam_paper(cleaned_text)
            
            if is_exam_paper:
                return await self._process_exam_paper(raw_text, cleaned_text)
            else:
                return await self._process_single_question(raw_text, cleaned_text)
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'type': 'exam'
            }
    
    async def _is_exam_paper(self, text: str) -> bool:
        """判斷是否為包含多題的考卷"""
        # 檢查常見的題目標記
        chinese_numbers = ['一、', '二、', '三、', '四、', '五、', '六、', '七、', '八、', '九、', '十、']
        arabic_numbers = ['1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.']
        parenthesis_numbers = ['（一）', '（二）', '（三）', '（四）', '（五）', '（六）']
        question_numbers = ['第一題', '第二題', '第三題', '第四題', '第五題']
        english_numbers = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']
        
        all_markers = chinese_numbers + arabic_numbers + parenthesis_numbers + question_numbers + english_numbers
        
        marker_count = 0
        for marker in all_markers:
            if marker in text:
                marker_count += 1
        
        # 如果找到2個或以上的題目標記，認為是考卷
        return marker_count >= 2
    
    async def _process_exam_paper(self, raw_text: str, cleaned_text: str) -> Dict[str, Any]:
        """處理完整考卷（多題）"""
        try:
            print("偵測到完整考卷，正在自動分題...")
            
            # 1. 自動分題
            questions_data = await self.gemini.split_exam_paper(cleaned_text)
            
            if not questions_data:
                return {
                    'success': False,
                    'error': '無法自動分割考卷題目',
                    'type': 'exam'
                }
            
            # 2. 科目分類
            print("正在分類科目...")
            subject = await self.gemini.classify_subject(cleaned_text)
            
            # 3. 儲存考卷文件
            result = await self._store_exam_paper_data(
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                questions_data=questions_data,
                subject=subject
            )
            
            return {
                'success': True,
                'type': 'exam_paper',
                'subject': subject,
                'document_id': result['document_id'],
                'question_ids': result['question_ids'],
                'file_path': result['file_path'],
                'questions_count': len(questions_data),
                'data': {
                    'questions': questions_data,
                    'subject': subject
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'考卷處理失敗: {str(e)}',
                'type': 'exam_paper'
            }
    
    async def _process_single_question(self, raw_text: str, cleaned_text: str) -> Dict[str, Any]:
        """處理單一題目"""
        # 1. AnswerGenerator - 生成標準答案
        print("正在生成標準答案...")
        answer_data = await self.gemini.generate_answer(cleaned_text)
        
        # 2. Highlighter - 歸納重點
        print("正在歸納重點...")
        highlights = await self.gemini.generate_highlights(cleaned_text)
        
        # 3. SubjectClassifier - 分類科目
        print("正在分類科目...")
        subject = await self.gemini.classify_subject(cleaned_text)
        
        # 4. Tagger - 生成標籤
        print("正在生成標籤...")
        tags = await self.gemini.generate_tags(cleaned_text, subject)
        
        # 5. StorageAgent - 儲存資料
        print("正在儲存資料...")
        result = await self._store_exam_data(
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            answer_data=answer_data,
            highlights=highlights,
            subject=subject,
            tags=tags
        )
        
        return {
            'success': True,
            'type': 'exam',
            'subject': subject,
            'document_id': result['document_id'],
            'question_id': result['question_id'],
            'file_path': result['file_path'],
            'data': {
                'stem': cleaned_text,
                'answer': answer_data.get('answer', ''),
                'sources': answer_data.get('sources', []),
                'highlights': highlights,
                'tags': tags
            }
        }
    
    async def _store_exam_data(self, raw_text: str, cleaned_text: str,
                              answer_data: Dict[str, Any], highlights: List[str],
                              subject: str, tags: List[str]) -> Dict[str, Any]:
        """儲存考題資料"""
        
        # 生成唯一檔案名稱
        content_hash = hashlib.md5(cleaned_text.encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{content_hash}.md"
        
        # 建立科目目錄
        subject_dir = os.path.join(self.data_dir, subject)
        os.makedirs(subject_dir, exist_ok=True)
        
        file_path = os.path.join(subject_dir, filename)
        
        # 生成 Markdown 內容
        markdown_content = self._generate_exam_markdown(
            stem=cleaned_text,
            answer=answer_data.get('answer', ''),
            sources=answer_data.get('sources', []),
            highlights=highlights,
            tags=tags,
            subject=subject
        )
        
        # 儲存 Markdown 檔案
        FileProcessor.save_markdown(markdown_content, file_path)
        
        # 儲存到資料庫
        document_id = self.db.insert_document(
            title=answer_data.get('question', '未知問題')[:100],
            content=raw_text,
            doc_type="exam",
            subject=subject,
            file_path=file_path
        )
        
        question_id = self.db.insert_question(
            document_id=document_id,
            question_text=answer_data.get('question', cleaned_text),
            answer_text=answer_data.get('answer', ''),
            subject=subject
        )
        
        return {
            'document_id': document_id,
            'question_id': question_id,
            'file_path': file_path
        }
    
    async def _store_exam_paper_data(self, raw_text: str, cleaned_text: str,
                                   questions_data: List[Dict[str, Any]], subject: str) -> Dict[str, Any]:
        """儲存考卷資料（多題）"""
        
        # 生成唯一檔案名稱
        content_hash = hashlib.md5(cleaned_text.encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"exam_paper_{timestamp}_{content_hash}.md"
        
        # 建立科目目錄
        subject_dir = os.path.join(self.data_dir, subject)
        os.makedirs(subject_dir, exist_ok=True)
        
        file_path = os.path.join(subject_dir, filename)
        
        # 生成 Markdown 內容
        markdown_content = self._generate_exam_paper_markdown(
            questions_data=questions_data,
            subject=subject
        )
        
        # 儲存 Markdown 檔案
        FileProcessor.save_markdown(markdown_content, file_path)
        
        # 儲存到資料庫
        document_id = self.db.insert_document(
            title=f"考卷（共{len(questions_data)}題）",
            content=raw_text,
            doc_type="exam",
            subject=subject,
            file_path=file_path
        )
        
        # 儲存每個題目
        question_ids = []
        for i, question_data in enumerate(questions_data):
            # 使用 stem 欄位，如果沒有則回退到 question 欄位
            question_text = question_data.get('stem', question_data.get('question', ''))
            answer_text = question_data.get('answer', '')
            
            question_id = self.db.insert_question(
                document_id=document_id,
                question_text=question_text,
                answer_text=answer_text,
                subject=subject
            )
            question_ids.append(question_id)
        
        return {
            'document_id': document_id,
            'question_ids': question_ids,
            'file_path': file_path
        }
    
    def _generate_exam_paper_markdown(self, questions_data: List[Dict[str, Any]], subject: str) -> str:
        """生成考卷的 Markdown 內容"""
        
        total_questions = len(questions_data)
        content = f"""# 📝 考卷記錄

> **科目**: `{subject}`  
> **建立時間**: `{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`  
> **類型**: `考卷（共 {total_questions} 題）`

---

## 📊 題目概覽

| 題號 | 題型 | 狀態 |
|------|------|------|
"""
        
        # 生成題目概覽表格
        for i, question in enumerate(questions_data, 1):
            number = question.get('number', f'第{i}題')
            q_type = question.get('type', '未分類')
            status = '✅ 已解答' if question.get('answer') else '⏳ 待解答'
            content += f"| {number} | {q_type} | {status} |\n"
        
        content += "\n---\n\n## 📚 題目內容\n\n"
        
        for i, question in enumerate(questions_data, 1):
            number = question.get('number', f'第{i}題')
            content += f"### {i}. {number}\n\n"
            
            # 題目內容 - 使用 stem 欄位
            stem = question.get('stem', question.get('question', '')).strip()
            if stem:
                content += f"**📋 題目**:\n\n{stem}\n\n"
            
            # 答案內容
            answer = question.get('answer', '').strip()
            if answer:
                content += f"**✅ 標準答案**:\n\n{answer}\n\n"
            else:
                content += f"**⏳ 標準答案**: *待補充*\n\n"
            
            # 題型標記
            q_type = question.get('type', '未分類')
            content += f"**🏷️ 題型**: `{q_type}`\n\n"
            
            # 分隔線
            if i < len(questions_data):
                content += "---\n\n"
        
        content += f"""
---

<div align="center">
<sub>💡 由考題知識整理系統自動生成 | 📅 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</sub>
</div>"""
        
        return content
    
    def _generate_exam_markdown(self, stem: str, answer: str, sources: List[str],
                               highlights: List[str], tags: List[str], subject: str) -> str:
        """生成考題的 Markdown 內容"""
        
        content = f"""# 📚 考題記錄

> **科目**: `{subject}`  
> **建立時間**: `{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`  
> **類型**: `考試題目`

---

## 📋 題目

```text
{stem}
```

---

## ✅ 標準答案

{answer}

---

## 🎯 重點摘要

"""
        
        if highlights:
            for i, highlight in enumerate(highlights, 1):
                content += f"**{i}.** {highlight}\n\n"
        else:
            content += "*暫無重點摘要*\n\n"
        
        content += "---\n\n## 📖 參考來源\n\n"
        
        if sources:
            for i, source in enumerate(sources, 1):
                content += f"**{i}.** {source}\n"
        else:
            content += "*暫無參考來源*\n"
        
        content += "\n---\n\n## 🏷️ 相關標籤\n\n"
        
        if tags:
            for tag in tags:
                content += f"- `{tag}`\n"
        else:
            content += "*暫無相關標籤*\n"
        
        content += f"""
---

<div align="center">
<sub>💡 由考題知識整理系統自動生成 | 📅 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</sub>
</div>"""
        
        return content

class AnswerGenerator:
    """答案生成器（獨立組件）"""
    
    def __init__(self, gemini_client: GeminiClient):
        self.gemini = gemini_client
    
    async def generate(self, question_text: str) -> Dict[str, Any]:
        """生成標準答案"""
        return await self.gemini.generate_answer(question_text)

class Highlighter:
    """重點歸納器（獨立組件）"""
    
    def __init__(self, gemini_client: GeminiClient):
        self.gemini = gemini_client
    
    async def generate_highlights(self, text: str) -> List[str]:
        """歸納重點"""
        return await self.gemini.generate_highlights(text)

class SubjectClassifier:
    """科目分類器（獨立組件）"""
    
    def __init__(self, gemini_client: GeminiClient):
        self.gemini = gemini_client
    
    async def classify(self, text: str) -> str:
        """分類科目"""
        return await self.gemini.classify_subject(text)

class Tagger:
    """標籤生成器（獨立組件）"""
    
    def __init__(self, gemini_client: GeminiClient):
        self.gemini = gemini_client
    
    async def generate_tags(self, text: str, subject: str) -> List[str]:
        """生成標籤"""
        return await self.gemini.generate_tags(text, subject)

class StorageAgent:
    """儲存代理（獨立組件）"""
    
    def __init__(self, db_manager: DatabaseManager, data_dir: str = "./data"):
        self.db = db_manager
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
    
    def store_exam_document(self, **kwargs) -> Dict[str, Any]:
        """儲存考題文件"""
        # 實作儲存邏輯
        pass
