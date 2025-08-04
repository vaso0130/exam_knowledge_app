"""
筆記AI處理器
處理筆記的各種AI功能，包括整理、摘要、關鍵字提取等
"""

import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..core.gemini_client import GeminiClient
from ..core.database import DatabaseManager


class NoteAIProcessor:
    """筆記AI處理器"""
    
    # AI整理方式定義
    AI_ORGANIZATION_METHODS = {
        'mindmap': {
            'name': '心智圖結構化',
            'description': '將筆記轉換成視覺化的心智圖格式',
            'prompt_template': '''請將以下筆記內容整理成心智圖格式。

筆記內容：
{content}

請按照以下格式輸出：
1. 主題（中心節點）
2. 主要分支（第一層）
3. 次要分支（第二層）
4. 詳細內容（第三層）

要求：
- 結構清晰，層次分明
- 用簡潔的關鍵詞表達
- 突出重點概念
- 使用markdown格式輸出'''
        },
        'hierarchical': {
            'name': '層次化重點整理',
            'description': '按重要性和邏輯關係分層整理',
            'prompt_template': '''請將以下筆記內容進行層次化重點整理。

筆記內容：
{content}

請按照以下結構整理：
## 核心概念（最重要）
## 關鍵要點（重要）
## 支撐細節（一般重要）
## 補充說明（參考）

要求：
- 按重要性分層
- 邏輯關係清晰
- 重點突出
- 便於記憶和理解'''
        },
        'feynman': {
            'name': '費曼技巧解析',
            'description': '用簡單易懂的方式重新解釋概念',
            'prompt_template': '''請用費曼技巧重新整理以下筆記內容。

筆記內容：
{content}

請按照費曼技巧的步驟：
1. **核心概念識別**：找出最重要的概念
2. **簡單解釋**：用最簡單的語言解釋
3. **舉例說明**：提供具體的例子
4. **類比比喻**：用熟悉的事物做比較
5. **查漏補缺**：指出可能的疑問點

要求：
- 語言簡潔易懂
- 避免專業術語
- 多用生活化例子
- 幫助深度理解'''
        },
        'qa_learning': {
            'name': '問答式學習',
            'description': '生成一系列漸進式問題來加深理解',
            'prompt_template': '''請根據以下筆記內容設計問答式學習材料。

筆記內容：
{content}

請設計三個層次的問題：

## 基礎理解題（檢查基本概念）
- 5-7個問題
- 答案在筆記中可直接找到

## 應用分析題（檢查理解深度）
- 3-5個問題
- 需要思考和分析

## 綜合評估題（檢查掌握程度）
- 2-3個問題
- 需要綜合運用和創新思考

每個問題都要提供詳細的參考答案。'''
        },
        'comparison': {
            'name': '對比分析整理',
            'description': '找出關鍵概念間的異同和關聯',
            'prompt_template': '''請對以下筆記內容進行對比分析整理。

筆記內容：
{content}

請按照以下方式整理：

## 核心概念提取
列出筆記中的主要概念

## 概念間比較
- 相似點分析
- 差異點分析
- 關聯性分析

## 概念關係圖
用文字描述概念間的關係

## 記憶技巧
提供幫助記憶這些概念及其關係的方法

要求：
- 突出概念間的聯繫
- 便於比較記憶
- 邏輯清晰'''
        },
        'memory_palace': {
            'name': '記憶宮殿法',
            'description': '將內容轉換成故事或空間記憶結構',
            'prompt_template': '''請用記憶宮殿法重新組織以下筆記內容。

筆記內容：
{content}

請按照以下步驟：

## 空間設計
選擇一個熟悉的地點（如家、學校、常去的路線）

## 路線規劃
設計一條清晰的遊覽路線

## 內容放置
將筆記內容按邏輯順序"放置"在各個位置

## 聯想設計
為每個知識點設計生動的視覺聯想

## 故事串聯
用一個有趣的故事將所有內容串聯起來

要求：
- 空間路線清晰
- 聯想生動有趣
- 便於記憶回憶
- 符合邏輯順序'''
        }
    }
    
    def __init__(self):
        self.gemini_client = GeminiClient()
        self.db_manager = DatabaseManager()
    
    def get_available_methods(self) -> Dict[str, Dict[str, str]]:
        """獲取可用的AI整理方法"""
        return {
            key: {
                'name': method['name'],
                'description': method['description']
            }
            for key, method in self.AI_ORGANIZATION_METHODS.items()
        }
    
    async def organize_note(self, note_id: str, method: str, user_id: int) -> Dict[str, Any]:
        """
        使用指定方法整理筆記
        
        Args:
            note_id: 筆記ID
            method: 整理方法
            user_id: 用戶ID
            
        Returns:
            整理結果
        """
        try:
            # 獲取筆記內容
            note = self.db_manager.get_note_by_id(note_id, user_id)
            if not note:
                raise ValueError("筆記不存在或無權限訪問")
            
            # 檢查方法是否有效
            if method not in self.AI_ORGANIZATION_METHODS:
                raise ValueError(f"未支援的整理方法: {method}")
            
            method_config = self.AI_ORGANIZATION_METHODS[method]
            
            # 構建提示詞
            prompt = method_config['prompt_template'].format(
                content=note['content']
            )
            
            # 調用AI進行整理
            organized_content = await self.gemini_client.generate_content(prompt)
            
            # 保存整理結果
            result = {
                'method': method,
                'method_name': method_config['name'],
                'original_content': note['content'],
                'organized_content': organized_content,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # 保存到資料庫
            analysis_id = self.db_manager.save_note_ai_analysis(
                note_id=note_id,
                analysis_type=f'organization_{method}',
                result=result
            )
            
            result['analysis_id'] = analysis_id
            return result
            
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def generate_note_summary(self, note_id: str, user_id: int) -> Dict[str, Any]:
        """生成筆記摘要"""
        try:
            note = self.db_manager.get_note_by_id(note_id, user_id)
            if not note:
                raise ValueError("筆記不存在或無權限訪問")
            
            prompt = f"""請為以下筆記內容生成一個簡潔的摘要。

筆記內容：
{note['content']}

要求：
1. 摘要長度控制在100-200字
2. 突出核心要點
3. 保持邏輯清晰
4. 便於快速了解內容

請直接輸出摘要內容："""
            
            summary = await self.gemini_client.generate_content(prompt)
            
            # 更新筆記的AI摘要
            self.db_manager.update_note_ai_analysis(
                note_id=note_id,
                ai_summary=summary
            )
            
            return {
                'summary': summary,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def extract_keywords(self, note_id: str, user_id: int) -> Dict[str, Any]:
        """提取筆記關鍵字"""
        try:
            note = self.db_manager.get_note_by_id(note_id, user_id)
            if not note:
                raise ValueError("筆記不存在或無權限訪問")
            
            prompt = f"""請從以下筆記內容中提取關鍵字。

筆記內容：
{note['content']}

要求：
1. 提取5-10個最重要的關鍵字
2. 關鍵字應該是核心概念或術語
3. 按重要性排序
4. 用JSON格式輸出，如：["關鍵字1", "關鍵字2", ...]

請直接輸出JSON格式的關鍵字陣列："""
            
            keywords_response = await self.gemini_client.generate_content(prompt)
            
            # 嘗試解析JSON
            try:
                keywords = json.loads(keywords_response)
                if not isinstance(keywords, list):
                    raise ValueError("關鍵字格式錯誤")
            except json.JSONDecodeError:
                # 如果JSON解析失敗，嘗試從文本中提取
                keywords = [kw.strip() for kw in keywords_response.replace('[', '').replace(']', '').replace('"', '').split(',')]
                keywords = [kw for kw in keywords if kw]  # 移除空字串
            
            # 更新筆記的AI關鍵字
            self.db_manager.update_note_ai_analysis(
                note_id=note_id,
                ai_keywords=keywords
            )
            
            return {
                'keywords': keywords,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def suggest_related_content(self, note_id: str, user_id: int) -> Dict[str, Any]:
        """提供相關內容建議"""
        try:
            note = self.db_manager.get_note_by_id(note_id, user_id)
            if not note:
                raise ValueError("筆記不存在或無權限訪問")
            
            # 獲取用戶的其他筆記（簡化版，只取標題）
            user_notes = self.db_manager.get_user_notes(user_id, limit=20)
            other_notes_titles = [n['title'] for n in user_notes if n['id'] != note_id]
            
            prompt = f"""基於以下筆記內容，請提供相關內容的學習建議。

當前筆記內容：
{note['content']}

用戶的其他筆記標題：
{', '.join(other_notes_titles) if other_notes_titles else '無其他筆記'}

請提供：
1. **延伸學習建議**：推薦3-5個相關的學習主題
2. **關聯筆記**：從用戶現有筆記中找出相關的筆記（如果有）
3. **學習資源**：建議的學習資源類型（書籍、文章、影片等）
4. **實踐建議**：如何將這些知識應用到實際中

請用結構化的格式輸出："""
            
            suggestions = await self.gemini_client.generate_content(prompt)
            
            result = {
                'suggestions': suggestions,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # 保存建議到資料庫
            self.db_manager.save_note_ai_analysis(
                note_id=note_id,
                analysis_type='content_suggestions',
                result=result
            )
            
            return result
            
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def generate_interactive_quiz(self, note_id: str, user_id: int) -> Dict[str, Any]:
        """生成筆記的互動選擇題"""
        try:
            note = self.db_manager.get_note_by_id(note_id, user_id)
            if not note:
                raise ValueError("筆記不存在或無權限訪問")
            
            prompt = f"""基於以下筆記內容，請生成5-7道選擇題來測試理解程度。

筆記內容：
{note['content']}

請按照以下JSON格式輸出：
{{
    "quiz_title": "筆記測驗標題",
    "questions": [
        {{
            "question": "題目內容",
            "options": ["選項A", "選項B", "選項C", "選項D"],
            "correct_answer": 0,
            "explanation": "答案解釋"
        }}
    ]
}}

要求：
1. 題目應該涵蓋筆記的核心內容
2. 選項設計要有一定的迷惑性
3. 提供詳細的答案解釋
4. 難度適中，既不太簡單也不太難
5. 必須是有效的JSON格式

請直接輸出JSON："""
            
            quiz_response = await self.gemini_client.generate_content(prompt)
            
            # 嘗試解析JSON
            try:
                quiz_data = json.loads(quiz_response)
                
                # 驗證數據結構
                if 'questions' not in quiz_data or not isinstance(quiz_data['questions'], list):
                    raise ValueError("測驗格式錯誤")
                
                # 為測驗添加額外信息
                quiz_data['note_id'] = note_id
                quiz_data['created_at'] = datetime.utcnow().isoformat()
                quiz_data['quiz_id'] = str(uuid.uuid4())
                
                # 保存測驗到資料庫
                analysis_id = self.db_manager.save_note_ai_analysis(
                    note_id=note_id,
                    analysis_type='interactive_quiz',
                    result=quiz_data
                )
                
                quiz_data['analysis_id'] = analysis_id
                return quiz_data
                
            except json.JSONDecodeError as e:
                return {
                    'error': f'AI回應格式錯誤: {str(e)}',
                    'raw_response': quiz_response,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def generate_note_from_source(self, source_content: str, source_type: str, 
                                      organization_method: str, user_id: int, 
                                      title: str = None) -> Dict[str, Any]:
        """
        從考題或教材生成筆記
        
        Args:
            source_content: 源內容（考題或教材）
            source_type: 源類型（'exam' 或 'material'）
            organization_method: 整理方法
            user_id: 用戶ID
            title: 筆記標題（可選）
        """
        try:
            if source_type == 'exam':
                base_prompt = f"""請根據以下考題內容生成學習筆記。

考題內容：
{source_content}

請生成包含以下內容的筆記：
1. 考題涉及的核心知識點
2. 相關概念的詳細解釋
3. 解題思路和方法
4. 類似題型的解法
5. 需要注意的重點和易錯點

筆記內容："""
            else:  # material
                base_prompt = f"""請根據以下教材內容生成結構化的學習筆記。

教材內容：
{source_content}

請提取和整理：
1. 主要概念和定義
2. 重要原理和規律
3. 關鍵例子和應用
4. 學習重點和難點
5. 相關的延伸知識

筆記內容："""
            
            # 生成基礎筆記內容
            basic_note = await self.gemini_client.generate_content(base_prompt)
            
            # 根據指定方法進一步整理
            if organization_method and organization_method in self.AI_ORGANIZATION_METHODS:
                method_config = self.AI_ORGANIZATION_METHODS[organization_method]
                organize_prompt = method_config['prompt_template'].format(content=basic_note)
                organized_content = await self.gemini_client.generate_content(organize_prompt)
            else:
                organized_content = basic_note
            
            # 生成標題（如果沒有提供）
            if not title:
                title_prompt = f"""為以下筆記內容生成一個簡潔的標題（10字以內）：

{organized_content[:200]}...

標題："""
                title = await self.gemini_client.generate_content(title_prompt)
                title = title.strip().replace('"', '').replace('標題：', '')
            
            # 創建筆記
            note_id = self.db_manager.create_note(
                user_id=user_id,
                title=title,
                content=organized_content,
                tags=[source_type, 'ai_generated']
            )
            
            return {
                'note_id': note_id,
                'title': title,
                'content': organized_content,
                'source_type': source_type,
                'organization_method': organization_method,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
