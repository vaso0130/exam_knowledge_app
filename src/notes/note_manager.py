
import json
from .database import NotesDatabaseManager
from .ai_client import NoteAIClient
from typing import List, Dict, Any, Optional

class NoteManager:
    """
    Core logic for managing notes. It acts as a bridge between the web layer (blueprint)
    and the data/AI layers (database, ai_client).
    """
    def __init__(self):
        self.db_manager = NotesDatabaseManager()
        self.ai_client = NoteAIClient()

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
            'source_question_id': kwargs.get('source_question_id'),
            'source_question_text': kwargs.get('source_question_text'),
            'source_answer_text': kwargs.get('source_answer_text')
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

        # 來源題目資訊
        if note.get('source_question_id'):
            note_details['source_question'] = {
                'id': note.get('source_question_id'),
                'text': note.get('source_question_text'),
                'answer': note.get('source_answer_text')
            }
        else:
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

    # === 互動式選擇題功能 ===

    def generate_quiz_for_note(self, user_id: int, note_id: str) -> Dict[str, Any]:
        """為筆記生成互動式選擇題"""
        note = self.db_manager.get_note_by_id(user_id, note_id)
        if not note:
            return {'error': '筆記不存在或無權限訪問'}

        try:
            quiz_result = self.ai_client.generate_interactive_quiz(note['content'])
            
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
            return analyses[0]['result']  # 返回最新的選擇題
        return None

    # === 從題庫/教材生成筆記 ===

    def create_note_from_questions(
        self,
        user_id: int,
        questions_data: List[Dict],
        title: str = None,
        source_question_id: str = None,
        source_question_text: str = None,
        source_answer_text: str = None
    ) -> Optional[str]:
        """從題庫資料生成筆記"""
        try:
            ai_result = self.ai_client.generate_note_from_questions(questions_data)

            note_title = title or ai_result.get('title', '從題庫生成的筆記')
            note_content = ai_result.get('content', '')

            # 創建筆記
            note_id = self.db_manager.create_note(
                user_id=user_id,
                title=note_title,
                content=note_content,
                content_type='markdown',
                tags=json.dumps(ai_result.get('suggested_tags', []), ensure_ascii=False),
                ai_summary=ai_result.get('study_tips'),
                ai_keywords=json.dumps(ai_result.get('key_concepts', []), ensure_ascii=False),
                source_question_id=source_question_id,
                source_question_text=source_question_text,
                source_answer_text=source_answer_text
            )
            
            if note_id:
                # 保存生成資訊
                self.db_manager.save_ai_analysis(user_id, note_id, 'generated_from_questions', {
                    'source_type': 'questions',
                    'source_count': len(questions_data),
                    'generation_result': ai_result
                })
            
            return note_id
        except Exception as e:
            print(f"Error creating note from questions: {e}")
            return None

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

