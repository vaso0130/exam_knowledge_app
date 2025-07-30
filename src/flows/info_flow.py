import asyncio
import hashlib
from datetime import datetime
from typing import Dict, Any, List
import os

from ..core.gemini_client import GeminiClient
from ..core.database import DatabaseManager
from ..utils.file_processor import FileProcessor, ContentValidator

class InfoFlow:
    """學習資料處理流程"""
    
    def __init__(self, gemini_client: GeminiClient, db_manager: DatabaseManager):
        self.gemini = gemini_client
        self.db = db_manager
        self.data_dir = "./data"
        os.makedirs(self.data_dir, exist_ok=True)
    
    async def process_learning_material(self, raw_text: str) -> Dict[str, Any]:
        """處理學習資料的完整流程"""
        try:
            # 清理文字
            cleaned_text = ContentValidator.clean_text(raw_text)
            
            # 1. Summarizer - 摘要全文
            print("正在生成摘要...")
            summary_data = await self.gemini.generate_summary(cleaned_text)
            
            # 2. SubjectClassifier - 分類科目
            print("正在分類科目...")
            subject = await self.gemini.classify_subject(cleaned_text)
            
            # 3. Tagger - 生成標籤
            print("正在生成標籤...")
            tags = await self.gemini.generate_tags(cleaned_text, subject)
            
            # 4. QAGenerator - 生成模擬題
            print("正在生成模擬題...")
            questions = await self.gemini.generate_questions(
                summary_data.get('bullets', [])
            )
            
            # 5. StorageAgent - 儲存資料
            print("正在儲存資料...")
            result = await self._store_info_data(
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                summary_data=summary_data,
                subject=subject,
                tags=tags,
                questions=questions
            )
            
            return {
                'success': True,
                'type': 'info',
                'subject': subject,
                'document_id': result['document_id'],
                'question_ids': result['question_ids'],
                'file_path': result['file_path'],
                'data': {
                    'summary': summary_data.get('summary', ''),
                    'bullets': summary_data.get('bullets', []),
                    'tags': tags,
                    'questions': questions
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'type': 'info'
            }
    
    async def _store_info_data(self, raw_text: str, cleaned_text: str,
                              summary_data: Dict[str, Any], subject: str,
                              tags: List[str], questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """儲存學習資料"""
        
        # 生成唯一檔案名稱
        content_hash = hashlib.md5(cleaned_text.encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{content_hash}.md"
        
        # 建立科目目錄
        subject_dir = os.path.join(self.data_dir, subject)
        os.makedirs(subject_dir, exist_ok=True)
        
        file_path = os.path.join(subject_dir, filename)
        
        # 生成 Markdown 內容
        markdown_content = self._generate_info_markdown(
            original_text=cleaned_text,
            summary=summary_data.get('summary', ''),
            bullets=summary_data.get('bullets', []),
            tags=tags,
            questions=questions,
            subject=subject
        )
        
        # 儲存 Markdown 檔案
        FileProcessor.save_markdown(markdown_content, file_path)
        
        # 儲存到資料庫
        document_id = self.db.insert_document(
            title=summary_data.get('title', file_path.split('/')[-1] if file_path else '未知文件'),
            content=raw_text,
            doc_type="info",
            subject=subject,
            file_path=file_path
        )
        
        # 儲存模擬題
        question_ids = []
        for question in questions:
            question_id = self.db.insert_question(
                document_id=document_id,
                question_text=question.get('stem', ''),
                answer_text=question.get('answer', ''),
                subject=subject
            )
            question_ids.append(question_id)
        
        return {
            'document_id': document_id,
            'question_ids': question_ids,
            'file_path': file_path
        }
    
    def _generate_info_markdown(self, original_text: str, summary: str,
                               bullets: List[str], tags: List[str],
                               questions: List[Dict[str, Any]], subject: str) -> str:
        """生成學習資料的 Markdown 內容"""
        
        content = f"""# 📖 學習資料記錄

> **科目**: `{subject}`  
> **建立時間**: `{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`  
> **類型**: `學習資料`

---

## 📝 內容摘要

> **摘要說明**: 以下是系統自動生成的內容摘要，幫助您快速掌握重點。

{summary}

---

## 🎯 重點整理

"""
        
        if bullets:
            for i, bullet in enumerate(bullets, 1):
                content += f"**{i}.** {bullet}\n\n"
        else:
            content += "*暫無重點整理*\n\n"
        
        content += "---\n\n## 🧠 模擬練習題\n\n"
        content += "> **練習說明**: 根據學習內容自動生成的練習題，幫助您檢驗學習成果。\n\n"
        
        if questions:
            for i, question in enumerate(questions, 1):
                qtype_map = {
                    'MCQ': '🔘 選擇題',
                    'TF': '✓ 是非題', 
                    'SA': '✍️ 簡答題'
                }
                qtype_name = qtype_map.get(question.get('type', 'MCQ'), '🔘 選擇題')
                
                content += f"### 第 {i} 題 ({qtype_name})\n\n"
                
                # 題目內容
                stem = question.get('stem', '').strip()
                if stem:
                    content += f"**📋 題目**:\n```text\n{stem}\n```\n\n"
                
                # 答案內容
                answer = question.get('answer', '').strip()
                if answer:
                    content += f"**✅ 參考答案**:\n\n{answer}\n\n"
                else:
                    content += f"**✅ 參考答案**: *待補充*\n\n"
                
                if i < len(questions):
                    content += "---\n\n"
        else:
            content += "*暫無模擬練習題*\n\n"
        
        content += "---\n\n## 🏷️ 相關標籤\n\n"
        
        if tags:
            for tag in tags:
                content += f"- `{tag}`\n"
        else:
            content += "*暫無相關標籤*\n"
        
        content += "\n---\n\n## 📄 原始內容\n\n"
        content += "> **原始資料**: 以下是您輸入的原始學習內容，供參考對照。\n\n"
        content += f"```text\n{original_text}\n```\n"
        
        content += f"""
---

<div align="center">
<sub>💡 由考題知識整理系統自動生成 | 📅 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</sub>
</div>"""
        
        return content

class Summarizer:
    """摘要生成器（獨立組件）"""
    
    def __init__(self, gemini_client: GeminiClient):
        self.gemini = gemini_client
    
    async def generate_summary(self, text: str) -> Dict[str, Any]:
        """生成摘要"""
        return await self.gemini.generate_summary(text)

class QAGenerator:
    """模擬題生成器（獨立組件）"""
    
    def __init__(self, gemini_client: GeminiClient):
        self.gemini = gemini_client
    
    async def generate_questions(self, bullets: List[str]) -> List[Dict[str, Any]]:
        """生成模擬題"""
        return await self.gemini.generate_questions(bullets)

class TypeDetector:
    """類型判定器"""
    
    def __init__(self, gemini_client: GeminiClient):
        self.gemini = gemini_client
    
    async def detect_type(self, text: str) -> bool:
        """判斷是否為考試題目"""
        return await self.gemini.detect_type(text)
    
    def detect_type_by_keywords(self, text: str) -> bool:
        """基於關鍵字判斷是否為考試題目"""
        exam_keywords = [
            '選擇題', '問答題', '填空題', '是非題', '簡答題',
            '下列何者', '請問', '試述', '解釋', '計算',
            'A)', 'B)', 'C)', 'D)', '(A)', '(B)', '(C)', '(D)',
            '答：', '解：', '【答案】', '正確答案',
            '第一題', '第二題', '第三題', '題目'
        ]
        
        text_lower = text.lower()
        chinese_text = text
        
        # 檢查關鍵字
        keyword_count = 0
        for keyword in exam_keywords:
            if keyword in chinese_text or keyword.lower() in text_lower:
                keyword_count += 1
        
        # 如果包含2個以上考試相關關鍵字，認為是考題
        return keyword_count >= 2

class ContentProcessor:
    """內容處理器統一介面"""
    
    def __init__(self, gemini_client: GeminiClient, db_manager: DatabaseManager):
        self.gemini = gemini_client
        self.db = db_manager
        self.type_detector = TypeDetector(gemini_client)
        self.answer_flow = None  # 延遲導入避免循環導入
        self.info_flow = InfoFlow(gemini_client, db_manager)
    
    async def process_content(self, text: str) -> Dict[str, Any]:
        """統一處理內容"""
        try:
            # 判斷內容類型
            is_exam = await self.type_detector.detect_type(text)
            
            if is_exam:
                # 延遲導入 AnswerFlow
                if self.answer_flow is None:
                    from .answer_flow import AnswerFlow
                    self.answer_flow = AnswerFlow(self.gemini, self.db)
                
                return await self.answer_flow.process_exam_question(text)
            else:
                return await self.info_flow.process_learning_material(text)
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'type': 'unknown'
            }
