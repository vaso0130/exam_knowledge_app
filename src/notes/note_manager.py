
import json
from .database import NotesDatabaseManager
from .ai_client import NoteAIClient
from .ghost_ai_client import GhostAIClient
from typing import List, Dict, Any, Optional

class NoteManager:
    """
    Core logic for managing notes. It acts as a bridge between the web layer (blueprint)
    and the data/AI layers (database, ai_client).
    """
    def __init__(self):
        self.db_manager = NotesDatabaseManager()
        self.ai_client = NoteAIClient()
        self.ghost_client = GhostAIClient()  # Ghost 功能專用客戶端

    # === 基本筆記操作 ===

    def create_new_note(self, user_id: int, title: str, content: str, enable_ai_analysis: bool = True, **kwargs) -> Optional[str]:
        """
        Creates a new note, optionally performs initial AI analysis, and saves it.
        """
        note_data = {
            'title': title,
            'content': content,
            'content_type': kwargs.get('content_type', 'markdown'),
            'tags': kwargs.get('custom_tags', []),
        }

        # 如果啟用 AI 分析，則執行分析
        if enable_ai_analysis:
            analysis_results = self.ai_client.analyze_note_content(content)
            note_data.update({
                'ai_summary': analysis_results.get('summary'),
                'ai_keywords': analysis_results.get('keywords', []),
                'tags': analysis_results.get('suggested_tags', []) + kwargs.get('custom_tags', [])
            })

        # Create the note in the database
        note_id = self.db_manager.create_note(user_id, **note_data)
        
        # 如果啟用AI分析，保存分析結果
        if enable_ai_analysis and note_id:
            self.db_manager.save_ai_analysis(user_id, note_id, 'initial_analysis', analysis_results)
        
        return note_id

    def get_note_details(self, user_id: int, note_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取筆記詳情，智慧快取 AI 建議
        
        邏輯：
        1. 獲取筆記基本資訊
        2. 嘗試從資料庫讀取快取的 AI 建議（相關筆記、知識點等）
        3. 如果沒有快取，呼叫 AI API 生成新建議並存回資料庫
        4. 返回完整的筆記詳情（包含 AI 建議）
        
        Args:
            user_id: 用戶ID
            note_id: 筆記ID
        """
        note = self.db_manager.get_note_by_id(user_id, note_id)
        if not note:
            return None

        # 處理 AI 關鍵字
        ai_keywords = note.get('ai_keywords', '[]')
        if isinstance(ai_keywords, str):
            try:
                ai_keywords = eval(ai_keywords) if ai_keywords else []
            except:
                ai_keywords = []

        # 基本筆記詳情
        note_details = {
            'id': note['id'],
            'title': note['title'],
            'content': note['content'],
            'created_at': note['created_at'],
            'updated_at': note['updated_at'],
            'tags': note.get('tags', []),
            'source': note.get('source', 'manual'),
            'ai_summary': note.get('ai_summary', ''),
            'ai_keywords': ai_keywords,
            'has_ai_analysis': bool(note.get('ai_summary') or ai_keywords)
        }

        # Source question info if exists
        try:
            source_data = self.db_manager.get_ai_analysis(user_id, note_id, 'source_question')
            if source_data:
                note_details['source_question'] = source_data[0]['result']
            else:
                note_details['source_question'] = None
        except Exception:
            note_details['source_question'] = None

        # 只有當筆記啟用了 AI 分析時，才生成智慧建議
        if note_details['has_ai_analysis']:
            # 智慧快取：嘗試從資料庫讀取 AI 建議
            try:
                # 檢查是否有快取的相關筆記建議
                cached_related_notes = self.db_manager.get_ai_analysis(user_id, note_id, 'related_notes_suggestions')
                if cached_related_notes:
                    note_details['related_notes'] = cached_related_notes[0]['result'].get('related_notes', [])
                else:
                    # 沒有快取，生成新的相關筆記建議
                    related_notes = self._get_related_notes_fast(user_id, note_id, note)
                    # 存回資料庫
                    self.db_manager.save_ai_analysis(user_id, note_id, 'related_notes_suggestions', {
                        'related_notes': related_notes,
                        'generated_at': note['updated_at']
                    })
                    note_details['related_notes'] = related_notes

                # 檢查是否有快取的相關知識點建議
                cached_knowledge_points = self.db_manager.get_ai_analysis(user_id, note_id, 'knowledge_points_suggestions')
                if cached_knowledge_points:
                    note_details['related_knowledge_points'] = cached_knowledge_points[0]['result'].get('knowledge_points', [])
                else:
                    # 沒有快取，生成新的知識點建議
                    knowledge_points = self._get_related_knowledge_points_fast(note)
                    # 存回資料庫
                    self.db_manager.save_ai_analysis(user_id, note_id, 'knowledge_points_suggestions', {
                        'knowledge_points': knowledge_points,
                        'generated_at': note['updated_at']
                    })
                    note_details['related_knowledge_points'] = knowledge_points

                # 檢查是否有快取的 AI 學習建議
                cached_study_suggestions = self.db_manager.get_ai_analysis(user_id, note_id, 'study_suggestions')
                if cached_study_suggestions:
                    note_details['study_suggestions'] = cached_study_suggestions[0]['result'].get('suggestions', [])
                else:
                    # 沒有快取，呼叫 AI 生成學習建議
                    try:
                        ai_suggestions = self.ai_client.suggest_related_content(
                            note_content=note['content'],
                            existing_notes=[n['title'] for n in self.get_all_notes_for_user(user_id) if n['id'] != note_id],
                            all_knowledge_points=self._get_knowledge_points_from_main_db()
                        )
                        study_suggestions = ai_suggestions.get('study_suggestions', [])
                        # 存回資料庫
                        self.db_manager.save_ai_analysis(user_id, note_id, 'study_suggestions', {
                            'suggestions': study_suggestions,
                            'full_ai_response': ai_suggestions,
                            'generated_at': note['updated_at']
                        })
                        note_details['study_suggestions'] = study_suggestions
                    except Exception as e:
                        print(f"Warning: Failed to generate AI study suggestions: {e}")
                        note_details['study_suggestions'] = []

            except Exception as e:
                print(f"Warning: Error in smart caching for note {note_id}: {e}")
                # 降級處理：提供基本的相關資訊
                note_details['related_notes'] = self._get_related_notes_fast(user_id, note_id, note)
                note_details['related_knowledge_points'] = self._get_related_knowledge_points_fast(note)
                note_details['study_suggestions'] = []
        else:
            # 用戶關掉了 AI 功能，不生成智慧建議
            note_details['related_notes'] = []
            note_details['related_knowledge_points'] = []
            note_details['study_suggestions'] = []

        return note_details

    def _get_related_notes_fast(self, user_id: int, current_note_id: str, note: Dict) -> List[Dict]:
        """快速獲取相關筆記（基於標籤和關鍵字匹配，不調用 AI）"""
        try:
            # 獲取用戶所有筆記
            all_notes = self.get_all_notes_for_user(user_id)
            related_notes = []
            
            current_keywords = set()
            if note.get('ai_keywords'):
                try:
                    keywords = eval(note.get('ai_keywords', '[]')) if isinstance(note.get('ai_keywords'), str) else note.get('ai_keywords', [])
                    current_keywords = set(kw.lower() for kw in keywords)
                except:
                    pass
            
            # 基於關鍵字匹配找相關筆記
            for other_note in all_notes:
                if other_note['id'] == current_note_id:
                    continue
                    
                score = 0
                other_keywords = set()
                if other_note.get('ai_keywords'):
                    try:
                        keywords = eval(other_note.get('ai_keywords', '[]')) if isinstance(other_note.get('ai_keywords'), str) else other_note.get('ai_keywords', [])
                        other_keywords = set(kw.lower() for kw in keywords)
                    except:
                        pass
                
                # 計算關鍵字重疊度
                if current_keywords and other_keywords:
                    overlap = len(current_keywords.intersection(other_keywords))
                    if overlap > 0:
                        score = overlap / len(current_keywords.union(other_keywords))
                
                # 標題相似度
                if note['title'].lower() in other_note['title'].lower() or other_note['title'].lower() in note['title'].lower():
                    score += 0.3
                
                if score > 0.2:  # 相似度閾值
                    related_notes.append({
                        'id': other_note['id'],
                        'title': other_note['title'],
                        'similarity_score': round(score, 2),
                        'created_at': other_note['created_at']
                    })
            
            # 按相似度排序，取前5個
            related_notes.sort(key=lambda x: x['similarity_score'], reverse=True)
            return related_notes[:5]
            
        except Exception as e:
            print(f"Error getting related notes fast: {e}")
            return []

    def _get_related_knowledge_points_fast(self, note: Dict) -> List[Dict]:
        """快速獲取相關知識點（基於標籤匹配）"""
        try:
            # 簡化版：從筆記關鍵字中推測相關知識點
            related_kp = []
            if note.get('ai_keywords'):
                try:
                    keywords = eval(note.get('ai_keywords', '[]')) if isinstance(note.get('ai_keywords'), str) else note.get('ai_keywords', [])
                    # 這裡可以擴展為真正的知識點匹配邏輯
                    for keyword in keywords[:3]:  # 取前3個關鍵字作為相關知識點
                        related_kp.append({
                            'keyword': keyword,
                            'type': 'inferred',
                            'confidence': 0.7
                        })
                except:
                    pass
            
            return related_kp
        except Exception as e:
            print(f"Error getting related knowledge points fast: {e}")
            return []

    def get_user_notes_list(self, user_id: int, **filters) -> List[Dict[str, Any]]:
        """Retrieves a list of all notes for a user with optional filters."""
        if filters.get('search_query') or filters.get('tags') or filters.get('category_id'):
            return self.db_manager.search_notes(
                user_id, 
                query=filters.get('search_query', ''),
                tags=filters.get('tags', []),
                category_id=filters.get('category_id')
            )
        return self.db_manager.get_all_notes_for_user(user_id, filters.get('include_archived', False))

    def get_all_notes_for_user(self, user_id: int, include_archived: bool = False) -> List[Dict[str, Any]]:
        """獲取用戶的所有筆記（直接包裝資料庫方法）"""
        return self.db_manager.get_all_notes_for_user(user_id, include_archived)

    def update_existing_note(self, user_id: int, note_id: str, enable_ai_reanalysis: bool = False, **updates) -> bool:
        """Updates an existing note. Optionally re-runs AI analysis if content changes."""
        # 取得舊內容以保存版本
        original_note = None
        try:
            original_note = self.db_manager.get_note_by_id(user_id, note_id)
        except Exception:
            original_note = None

        if original_note and 'content' in updates and updates['content'] != original_note.get('content'):
            # 保存舊內容為版本歷史（使用 ai_analysis 表重用存儲）
            try:
                self.db_manager.save_ai_analysis(
                    user_id, note_id, 'revision_snapshot', {
                        'previous_title': original_note.get('title'),
                        'previous_content': original_note.get('content'),
                        'previous_ai_summary': original_note.get('ai_summary'),
                        'previous_ai_keywords': original_note.get('ai_keywords'),
                        'length': len(original_note.get('content') or ''),
                    }
                )
            except Exception as e:
                print(f"Warning: failed to save revision snapshot: {e}")

        if enable_ai_reanalysis and 'content' in updates:
            analysis_results = self.ai_client.analyze_note_content(updates['content'])
            updates.update({
                'ai_summary': analysis_results.get('summary'),
                'ai_keywords': analysis_results.get('keywords', [])
            })
            # 保存重新分析結果
            self.db_manager.save_ai_analysis(user_id, note_id, 'content_update_analysis', analysis_results)

        return self.db_manager.update_note(user_id, note_id, **updates)

    def delete_note_by_id(self, user_id: int, note_id: str) -> bool:
        """Deletes a note for a user."""
        return self.db_manager.delete_note(user_id, note_id)

    # === AI 整理功能 ===

    def organize_note_with_ai(self, user_id: int, note_id: str, organization_type: str) -> Dict[str, Any]:
        """
        使用 AI 以指定方式整理筆記
        
        Args:
            user_id: 用戶ID
            note_id: 筆記ID
            organization_type: 整理方式 ('mindmap', 'hierarchical', 'feynman', 'qa_learning', 'comparison', 'memory_palace')
        """
        note = self.db_manager.get_note_by_id(user_id, note_id)
        if not note:
            return {'error': '筆記不存在或無權限訪問'}

        content = note['content']
        
        # 根據整理類型調用對應的 AI 方法
        ai_methods = {
            'mindmap': self.ai_client.organize_with_mindmap,
            'hierarchical': self.ai_client.organize_hierarchically,
            'feynman': self.ai_client.organize_with_feynman_technique,
            'qa_learning': self.ai_client.organize_with_qa_learning,
            'comparison': self.ai_client.organize_with_comparison,
            'memory_palace': self.ai_client.organize_with_memory_palace,
            'mandala_ninegrid': self.ai_client.organize_with_mandala_ninegrid,
            'format_enhance': self.ai_client.format_and_enhance_content
        }
        
        if organization_type not in ai_methods:
            return {'error': f'不支援的整理類型: {organization_type}'}
        
        try:
            result = ai_methods[organization_type](content)
            
            # 保存 AI 整理結果到資料庫
            analysis_id = self.db_manager.save_ai_analysis(user_id, note_id, f'organization_{organization_type}', result)
            
            return {
                'success': True,
                'organization_type': organization_type,
                'result': result,
                'analysis_id': analysis_id,  # 返回資料庫記錄 ID
                'saved_to_db': analysis_id is not None
            }
        except Exception as e:
            return {'error': f'AI 整理失敗: {str(e)}'}

    def get_saved_organization(self, user_id: int, note_id: str, organization_type: str) -> Optional[Dict[str, Any]]:
        """獲取已保存的AI整理結果"""
        try:
            analyses = self.db_manager.get_ai_analysis_by_type(user_id, note_id, f'organization_{organization_type}')
            if analyses:
                # 返回最新的整理結果
                return analyses[0]
            return None
        except Exception as e:
            print(f"Error getting saved organization: {e}")
            return None

    def get_all_saved_organizations(self, user_id: int, note_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """獲取筆記的所有AI整理結果"""
        try:
            all_analyses = self.db_manager.get_ai_analysis(user_id, note_id)
            
            # 分組整理結果
            organizations = {}
            for analysis in all_analyses:
                if analysis['analysis_type'].startswith('organization_'):
                    org_type = analysis['analysis_type'].replace('organization_', '')
                    if org_type not in organizations:
                        organizations[org_type] = []
                    organizations[org_type].append(analysis)
            
            return organizations
        except Exception as e:
            print(f"Error getting all organizations: {e}")
            return {}

    def delete_organization(self, user_id: int, note_id: str, analysis_id: int) -> bool:
        """刪除特定的AI整理結果"""
        try:
            return self.db_manager.delete_ai_analysis(user_id, note_id, analysis_id)
        except Exception as e:
            print(f"Error deleting organization: {e}")
            return False

    def get_available_organization_types(self) -> List[Dict[str, str]]:
        """獲取可用的AI整理方式列表"""
        return [
            {'type': 'mindmap', 'name': '心智圖結構化', 'description': '將內容轉換成視覺化的心智圖格式'},
            {'type': 'hierarchical', 'name': '層次化重點整理', 'description': '按重要性和邏輯關係分層整理'},
            {'type': 'feynman', 'name': '費曼技巧解析', 'description': '用簡單易懂的方式重新解釋概念'},
            {'type': 'qa_learning', 'name': '問答式學習', 'description': '生成一系列漸進式問題來加深理解'},
            {'type': 'comparison', 'name': '對比分析整理', 'description': '找出關鍵概念間的異同和關聯'},
            {'type': 'memory_palace', 'name': '記憶宮殿法', 'description': '將內容轉換成故事或空間記憶結構'},
            {'type': 'format_enhance', 'name': '格式化與補強', 'description': '整理格式、補充資料、修正錯字'}
        ]

    # === 格式化與補強應用功能 ===
    
    def apply_formatted_content(self, user_id: int, note_id: str, analysis_id: int) -> Dict[str, Any]:
        """將格式化與補強的內容應用到原始筆記"""
        # 驗證使用者對筆記的訪問權限
        note = self.db_manager.get_note_by_id(user_id, note_id)
        if not note:
            return {'success': False, 'error': '筆記不存在或無權限訪問'}
        
        # 獲取格式化結果
        analysis = self.db_manager.get_note_ai_analysis_by_id(analysis_id)
        if not analysis:
            return {'success': False, 'error': '找不到指定的格式化結果'}
            
        # 驗證分析結果屬於該筆記
        if analysis['note_id'] != note_id:
            return {'success': False, 'error': '格式化結果與筆記不匹配'}
            
        # 驗證分析類型是格式化與補強
        if not analysis['analysis_type'].endswith('format_enhance'):
            return {'success': False, 'error': '指定的分析結果不是格式化與補強類型'}
        
        # 從結果中提取格式化內容
        result = analysis['result']
        formatted_content = result.get('formatted_content')
        
        if not formatted_content:
            return {'success': False, 'error': '格式化結果中未找到格式化內容'}
        
        # 更新筆記內容
        update_success = self.db_manager.update_note(user_id, note_id, content=formatted_content)
        
        if update_success:
            return {
                'success': True, 
                'message': '筆記內容已成功更新為格式化版本',
                'note_id': note_id
            }
        else:
            return {'success': False, 'error': '更新筆記內容失敗'}
    
    # === 互動式選擇題功能 ===

    def generate_quiz_for_note(self, user_id: int, note_id: str) -> Dict[str, Any]:
        """為筆記生成互動式選擇題"""
        note = self.db_manager.get_note_by_id(user_id, note_id)
        if not note:
            return {'error': '筆記不存在或無權限訪問'}

        try:
            quiz_result = self.ai_client.generate_interactive_quiz(note['content'])
            
            # 確保 options 是陣列格式
            if 'questions' in quiz_result:
                for question in quiz_result['questions']:
                    if 'options' in question and not isinstance(question['options'], list):
                        # 如果 options 不是陣列，將其轉換為陣列
                        if isinstance(question['options'], dict):
                            # 例如 {A: '選項1', B: '選項2'} 轉換為 ['選項1', '選項2']
                            # 或者保持 ABCD 順序: [options['A'], options['B'], ...]
                            keys = sorted(question['options'].keys())
                            question['options'] = [question['options'][k] for k in keys if k in question['options']]
                        else:
                            # 如果是其他類型，設置為空陣列
                            question['options'] = []
            
            # 保存選擇題結果
            self.db_manager.save_ai_analysis(user_id, note_id, 'interactive_quiz', quiz_result)
            
            return {
                'success': True,
                'quiz': quiz_result,
                'note_title': note['title']
            }
        except Exception as e:
            return {'error': f'選擇題生成失敗: {str(e)}'}

    def get_saved_quiz(self, user_id: int, note_id: str) -> Optional[Dict[str, Any]]:
        """獲取已保存的選擇題"""
        analyses = self.db_manager.get_ai_analysis(user_id, note_id, 'interactive_quiz')
        if analyses:
            quiz_result = analyses[0]['result']
            
            # 確保 options 是陣列格式
            if 'questions' in quiz_result:
                for question in quiz_result['questions']:
                    if 'options' in question and not isinstance(question['options'], list):
                        # 如果 options 不是陣列，將其轉換為陣列
                        if isinstance(question['options'], dict):
                            # 例如 {A: '選項1', B: '選項2'} 轉換為 ['選項1', '選項2']
                            keys = sorted(question['options'].keys())
                            question['options'] = [question['options'][k] for k in keys if k in question['options']]
                        else:
                            # 如果是其他類型，設置為空陣列
                            question['options'] = []
                            
            return quiz_result  # 返回修正後的最新選擇題
        return None

    # === 從題庫/教材生成筆記 ===

    def create_note_from_questions(self, user_id: int, questions_data: List[Dict], title: str = None, additional_content: str = None, tags: str = None) -> Optional[str]:
        """從題庫資料生成筆記"""
        try:
            ai_result = self.ai_client.generate_note_from_questions(questions_data)
            
            note_title = title or ai_result.get('title', '從題庫生成的筆記')
            note_content = ai_result.get('content', '')
            
            # 如果有額外內容，則附加到生成的內容後面
            if additional_content and additional_content.strip():
                note_content += f"\n\n## 額外補充\n\n{additional_content}"
            
            # 處理標籤
            final_tags = []
            
            # 添加 AI 建議的標籤
            ai_tags = ai_result.get('suggested_tags', [])
            if ai_tags:
                final_tags.extend(ai_tags)
            
            # 添加用戶提供的標籤
            if tags and tags.strip():
                user_tags = [tag.strip() for tag in tags.split(',') if tag.strip()]
                final_tags.extend(user_tags)
            
            # 去除重複標籤
            final_tags = list(set(final_tags))
            
            # 創建筆記
            note_id = self.db_manager.create_note(
                user_id=user_id,
                title=note_title,
                content=note_content,
                content_type='markdown',
                tags=json.dumps(final_tags, ensure_ascii=False),
                ai_summary=ai_result.get('study_tips'),
                ai_keywords=json.dumps(ai_result.get('key_concepts', []), ensure_ascii=False)
            )
            
            if note_id:
                # 保存生成資訊
                self.db_manager.save_ai_analysis(user_id, note_id, 'generated_from_questions', {
                    'source_type': 'questions',
                    'source_count': len(questions_data),
                    'generation_result': ai_result,
                    'has_additional_content': bool(additional_content and additional_content.strip()),
                    'user_tags': tags
                })
            
            return note_id
        except Exception as e:
            print(f"Error creating note from questions: {e}")
            return None

    def generate_smart_note_content(self, user_id: int, context: Dict[str, Any]) -> str:
        """
        智能生成筆記內容，結合題目、答案、使用者現有內容和AI提示
        
        Args:
            user_id: 使用者ID
            context: 包含以下鍵值的字典
                - question_text: 題目文字
                - answer_text: 答案文字
                - user_content: 使用者已輸入的內容
                - user_prompt: 使用者給AI的額外指示
                - title: 筆記標題
        
        Returns:
            生成的筆記內容
        """
        try:
            # 呼叫AI客戶端的智能生成方法
            generated_content = self.ai_client.generate_smart_note_content(context)
            return generated_content
        except Exception as e:
            print(f"Error generating smart note content: {e}")
            # 如果AI生成失敗，返回一個基本的模板
            fallback_content = self._create_fallback_content(context)
            return fallback_content

    def _create_fallback_content(self, context: Dict[str, Any]) -> str:
        """創建增強版備用內容模板，當AI生成失敗時使用"""
        question_text = context.get('question_text', '')
        answer_text = context.get('answer_text', '')
        user_content = context.get('user_content', '')
        user_prompt = context.get('user_prompt', '')
        
        fallback = f"""# {context.get('title', '學習筆記')}

## 📚 知識背景與脈絡

這個題目涉及的核心知識點包括：
- 從題目中提取關鍵概念
- 分析題目與答案間的關聯
- 理解相關學科知識框架

## 🔍 概念剖析

### 核心概念
題目關注的重點：
```
{question_text}
```

### 解答要點
參考答案的關鍵信息：
```
{answer_text}
```

## � 解題思路與方法

1. 首先理解問題的關鍵點
2. 分析可能的解題策略
3. 應用相關知識點
4. 驗證結果的正確性

## 📌 重點整理

| 知識點 | 重要性 | 常見考點 |
|-------|------|--------|
| 待補充... | ⭐⭐⭐ | 題目中的關鍵概念 |
| 待補充... | ⭐⭐ | 解答中的重要方法 |

## �📝 個人學習筆記
{user_content if user_content else "在這裡記錄您的學習心得和重點整理。"}

## 🧠 記憶技巧與擴展學習

- 將本題知識點與其他相關概念連結
- 創建思維導圖幫助記憶關鍵信息
- 嘗試用自己的話解釋核心概念

{f"## 🎯 學習指引\\n{user_prompt}" if user_prompt else ""}
"""
        return fallback

    def create_note_from_materials(self, user_id: int, materials_content: str, material_type: str = "教材", title: str = None) -> Optional[str]:
        """從教材內容生成筆記"""
        try:
            ai_result = self.ai_client.generate_note_from_materials(materials_content, material_type)
            
            note_title = title or ai_result.get('title', f'從{material_type}生成的筆記')
            note_content = ai_result.get('content', '')
            
            # 創建筆記
            note_id = self.db_manager.create_note(
                user_id=user_id,
                title=note_title,
                content=note_content,
                content_type='markdown',
                tags=json.dumps(ai_result.get('suggested_tags', []), ensure_ascii=False),
                ai_summary=ai_result.get('summary'),
                ai_keywords=json.dumps(ai_result.get('key_points', []), ensure_ascii=False)
            )
            
            if note_id:
                # 保存生成資訊
                self.db_manager.save_ai_analysis(user_id, note_id, 'generated_from_materials', {
                    'source_type': material_type,
                    'generation_result': ai_result
                })
            
            return note_id
        except Exception as e:
            print(f"Error creating note from materials: {e}")
            return None

    # === 智慧建議功能 ===

    def get_note_suggestions(self, user_id: int, note_id: str) -> Dict[str, List]:
        """Generates suggestions for related content based on a note."""
        note = self.db_manager.get_note_by_id(user_id, note_id)
        if not note:
            return {}

        # 檢查筆記是否啟用AI功能（使用與 get_note_details 相同的邏輯）
        ai_keywords = note.get('ai_keywords', '[]')
        if isinstance(ai_keywords, str):
            try:
                ai_keywords = eval(ai_keywords) if ai_keywords else []
            except:
                ai_keywords = []
        
        has_ai_analysis = bool(note.get('ai_summary') or ai_keywords)
        
        if not has_ai_analysis:
            return {
                'related_notes': [],
                'knowledge_points': [],
                'suggested_topics': []
            }

        # 獲取用戶的其他筆記標題
        all_other_note_titles = [n['title'] for n in self.db_manager.get_all_notes_for_user(user_id) if n['id'] != note_id]
        
        # 從主程式獲取知識點（需要整合主程式的資料庫）
        all_knowledge_points = self._get_knowledge_points_from_main_db()

        return self.ai_client.suggest_related_content(
            note_content=note['content'],
            existing_notes=all_other_note_titles,
            all_knowledge_points=all_knowledge_points
        )

    def _get_knowledge_points_from_main_db(self) -> List[str]:
        """從主程式資料庫獲取知識點列表"""
        try:
            # 這裡需要使用主程式的資料庫管理器
            from ..core.database import DatabaseManager
            main_db = DatabaseManager()
            knowledge_points = main_db.get_all_knowledge_points()
            return [kp['name'] for kp in knowledge_points]
        except Exception as e:
            print(f"Error fetching knowledge points: {e}")
            return []

    # === 分類管理 ===

    def create_category_for_user(self, user_id: int, name: str, **kwargs) -> Optional[int]:
        return self.db_manager.create_category(user_id, name, **kwargs)

    def get_user_categories(self, user_id: int) -> List[Dict[str, Any]]:
        return self.db_manager.get_all_categories_for_user(user_id)

    def add_note_to_category(self, user_id: int, note_id: str, category_id: int) -> bool:
        return self.db_manager.link_note_to_category(user_id, note_id, category_id)

    # === 知識點整合 ===

    def link_note_to_knowledge_point(self, user_id: int, note_id: str, knowledge_point_id: int, relevance_score: float = 0.8) -> bool:
        """將筆記與知識點關聯"""
        return self.db_manager.link_note_to_knowledge_point(user_id, note_id, knowledge_point_id, relevance_score)

    def get_note_knowledge_points(self, user_id: int, note_id: str) -> List[Dict[str, Any]]:
        """獲取筆記相關的知識點"""
        return self.db_manager.get_related_knowledge_points(user_id, note_id)

    # === 筆記關聯 ===

    def create_note_relationship(self, user_id: int, source_note_id: str, target_note_id: str, relationship_type: str = 'related') -> bool:
        """建立筆記間的關聯"""
        return self.db_manager.create_note_relationship(user_id, source_note_id, target_note_id, relationship_type)

    def get_related_notes(self, user_id: int, note_id: str) -> List[Dict[str, Any]]:
        """獲取相關筆記"""
        return self.db_manager.get_related_notes(user_id, note_id)

    # === AI文字偵測功能 ===

    def detect_and_suggest_text(self, user_id: int, content: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        AI文字偵測 - 即時分析用戶輸入的文字內容並提供智慧建議
        
        Args:
            user_id: 用戶ID
            content: 要分析的文字內容
            context: 上下文信息（如筆記標題、已有內容等）
        
        Returns:
            包含建議的字典
        """
        try:
            # 調用AI客戶端進行文字偵測
            detection_result = self.ghost_client.detect_and_suggest_text(content, context)

            # 規範化回傳結構，避免下游對非陣列型別進行迭代
            detection_result = self._normalize_detection_result(detection_result)

            # 確保 has_suggestions 欄位可靠存在
            detection_result['has_suggestions'] = bool(
                detection_result.get('suggestions') or
                detection_result.get('quick_fixes') or
                detection_result.get('content_enhancements') or
                detection_result.get('formatting_tips')
            )

            # 記錄偵測日誌（可選，用於改進功能）
            self._log_text_detection(user_id, content, detection_result)

            return detection_result
            
        except Exception as e:
            print(f"AI文字偵測失敗: {e}")
            return {
                'suggestions': [],
                'quick_fixes': [],
                'content_enhancements': [],
                'formatting_tips': [],
                'has_suggestions': False,
                'error': str(e)
            }

    def _normalize_detection_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """將 AI 偵測結果的欄位規範為預期型別，避免布林或物件導致迭代錯誤。"""
        try:
            normalized = dict(result or {})

            def as_list(v):
                # 將輸入轉為 list：list -> 原樣；dict -> [dict]；str -> [str]；True/False/None -> []；其他 -> []
                if isinstance(v, list):
                    return v
                if isinstance(v, dict):
                    return [v]
                if isinstance(v, str):
                    return [v]
                return []

            normalized['suggestions'] = as_list(normalized.get('suggestions'))
            normalized['quick_fixes'] = as_list(normalized.get('quick_fixes'))
            normalized['content_enhancements'] = as_list(normalized.get('content_enhancements'))
            normalized['formatting_tips'] = as_list(normalized.get('formatting_tips'))

            return normalized
        except Exception:
            # 發生任何異常時回傳安全的空結構
            return {
                'suggestions': [],
                'quick_fixes': [],
                'content_enhancements': [],
                'formatting_tips': []
            }
    
    def _log_text_detection(self, user_id: int, content: str, result: Dict[str, Any]) -> None:
        """
        記錄文字偵測的使用情況（可選功能，用於改進AI建議品質）
        
        Args:
            user_id: 用戶ID
            content: 分析的內容
            result: 偵測結果
        """
        try:
            # 這裡可以記錄到資料庫或日誌文件
            # 暫時只做簡單的控制台記錄
            suggestions_field = result.get('suggestions', [])
            # 避免 suggestions 是 bool 或其他不可迭代型別
            if not isinstance(suggestions_field, list):
                suggestions_count = 0
            else:
                suggestions_count = len(suggestions_field)
            if suggestions_count > 0:
                print(f"用戶 {user_id} 的文字偵測產生了 {suggestions_count} 個建議")
        except Exception as e:
            # 日誌記錄失敗不應該影響主要功能
            print(f"記錄文字偵測日誌失敗: {e}")

    def generate_enhancement_content(self, user_id: int, enhancement_request: str, current_content: str, title: str = "", context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        根據增強建議生成實際內容
        
        Args:
            user_id: 用戶ID  
            enhancement_request: 增強建議的描述
            current_content: 目前的筆記內容
            title: 筆記標題
            context: 額外的上下文資訊
            
        Returns:
            包含生成內容的字典
        """
        try:
            print(f"為用戶 {user_id} 生成內容增強：{enhancement_request}")
            
            # 調用AI客戶端生成增強內容
            enhancement_result = self.ai_client.generate_content_enhancement(
                enhancement_request=enhancement_request,
                current_content=current_content,
                title=title,
                context=context or {}
            )
            
            # 記錄生成的內容用於追蹤
            if enhancement_result.get('generated_content'):
                print(f"成功生成內容，長度: {len(enhancement_result['generated_content'])} 字符")
            
            return enhancement_result
            
        except Exception as e:
            print(f"內容增強生成錯誤: {e}")
            return {
                'generated_content': enhancement_request,  # 失敗時返回原始建議
                'success': False,
                'error': str(e)
            }

    def update_note_content_directly(self, user_id: int, note_id: str, new_content: str) -> Dict[str, Any]:
        """
        直接更新筆記內容（用於格式化與補強功能）
        
        Args:
            user_id: 用戶ID
            note_id: 筆記ID
            new_content: 新的內容
            
        Returns:
            更新結果
        """
        try:
            # 檢查筆記是否存在且用戶有權限
            note = self.db_manager.get_note_by_id(user_id, note_id)
            if not note:
                return {
                    'success': False,
                    'error': '筆記不存在或無權限訪問'
                }
            
            # 更新筆記內容
            update_result = self.db_manager.update_note(user_id, note_id, content=new_content)
            
            if update_result:
                return {
                    'success': True,
                    'message': '筆記內容已成功更新'
                }
            else:
                return {
                    'success': False,
                    'error': '更新筆記內容失敗'
                }
                
        except Exception as e:
            print(f"直接更新筆記內容時發生錯誤: {e}")
            return {
                'success': False,
                'error': f'更新筆記內容時發生錯誤: {str(e)}'
            }

