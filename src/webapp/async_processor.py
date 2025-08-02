#!/usr/bin/env python3
"""
非同步處理模組
解決 Cloudflare 524 Timeout 問題
"""
import os
import json
import uuid
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

class AsyncProcessor:
    """非同步處理器 - 使用資料庫儲存工作狀態"""
    
    def __init__(self, flow_manager):
        self.flow_manager = flow_manager
        self.jobs: Dict[str, Dict[str, Any]] = {}  # 記憶體快取，提升查詢效能
        # 不再需要檔案目錄
        
    def submit_job(self, job_type: str, **kwargs) -> str:
        """提交非同步工作"""
        job_id = str(uuid.uuid4())
        
        # 儲存工作資訊
        job_info = {
            'id': job_id,
            'type': job_type,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'progress': 0,
            'message': '等待處理中...',
            'result': None,
            'error': None,
            'kwargs': kwargs
        }
        
        self.jobs[job_id] = job_info
        
        # 儲存到資料庫
        self.flow_manager.db_manager.create_async_job(job_id, job_type, kwargs)
        
        # 啟動背景線程處理
        thread = threading.Thread(
            target=self._process_job,
            args=(job_id, job_type, kwargs),
            daemon=True
        )
        thread.start()
        
        return job_id
    
    def start_url_processing_job(self, url: str, title: str, subject: str = "") -> str:
        """啟動網路擷取處理工作"""
        return self.submit_job(
            job_type='url_processing',
            url=url,
            title=title,
            subject=subject
        )
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """取得工作狀態 - 優先從記憶體快取，然後從資料庫"""
        # 先檢查記憶體快取
        if job_id in self.jobs:
            return self.jobs[job_id]
        
        # 從資料庫載入
        job_data = self.flow_manager.db_manager.get_async_job(job_id)
        if job_data:
            # 更新記憶體快取
            self.jobs[job_id] = job_data
        
        return job_data
    
    def _process_job(self, job_id: str, job_type: str, kwargs: Dict[str, Any]):
        """處理工作的背景方法"""
        try:
            self._update_job_status(job_id, 'running', 10, '開始處理...')
            
            if job_type == 'content_processing':
                result = self._process_content(job_id, **kwargs)
            elif job_type == 'question_processing':
                result = self._process_question(job_id, **kwargs)
            elif job_type == 'url_processing':
                result = self._process_url(job_id, **kwargs)
            else:
                raise ValueError(f"未知的工作類型: {job_type}")
            
            self._update_job_status(job_id, 'completed', 100, '處理完成', result=result)
            
        except Exception as e:
            error_msg = f"處理失敗: {str(e)}"
            self._update_job_status(job_id, 'failed', 0, error_msg, error=str(e))
    
    def _process_content(self, job_id: str, file_path: str, filename: str, subject: str) -> Dict[str, Any]:
        """處理學習內容"""
        self._update_job_status(job_id, 'running', 20, '讀取檔案內容...')
        
        # 使用 FileProcessor 讀取檔案
        from ..utils.file_processor import FileProcessor
        
        try:
            # 使用正確的方法名稱
            content, file_type = FileProcessor.process_input(file_path)
            if not content:
                raise Exception("無法讀取檔案內容")
            
            self._update_job_status(job_id, 'running', 30, '分析內容類型...')
            
            # 使用 content_flow 處理
            result = self.flow_manager.content_flow.complete_ai_processing(
                content=content,
                filename=filename,
                suggested_subject=subject
            )
            
            # 模擬進度更新
            steps = [
                (40, '提取知識點...'),
                (50, '生成申論題...'),
                (60, '清理內容...'),
                (70, '生成摘要...'),
                (80, '創建選擇題...'),
                (90, '組合內容...'),
                (95, '儲存到資料庫...')
            ]
            
            for progress, message in steps:
                self._update_job_status(job_id, 'running', progress, message)
                time.sleep(0.5)  # 模擬處理時間
            
            return result
            
        except Exception as e:
            raise Exception(f"內容處理失敗: {str(e)}")
    
    def _process_question(self, job_id: str, content: str, filename: str) -> Dict[str, Any]:
        """處理考題"""
        self._update_job_status(job_id, 'running', 30, '解析題目...')
        
        try:
            # 使用 answer_flow 處理單一問題
            result = self.flow_manager.answer_flow.process_question_content(
                question_content=content,
                filename=filename
            )
            
            self._update_job_status(job_id, 'running', 80, '生成答案...')
            time.sleep(1)
            
            return result
            
        except Exception as e:
            raise Exception(f"考題處理失敗: {str(e)}")
    
    def _process_url(self, job_id: str, url: str, title: str, subject: str) -> Dict[str, Any]:
        """處理網路擷取"""
        self._update_job_status(job_id, 'running', 20, '連接網站，擷取內容...')
        
        from ..utils.file_processor import FileProcessor
        
        try:
            # 使用 FileProcessor 獲取網路內容
            web_content = FileProcessor.fetch_url_content_sync(url)
            
            if not web_content or len(web_content.strip()) < 10:
                raise Exception("無法從該網址獲取有效內容，請檢查網址是否正確")
            
            self._update_job_status(job_id, 'running', 40, '內容擷取完成，開始分析...')
            
            # 使用 content_flow 處理
            result = self.flow_manager.content_flow.complete_ai_processing(
                content=web_content,
                filename=title,
                suggested_subject=subject,
                source_url=url
            )
            
            # 模擬進度更新
            steps = [
                (50, '分析內容類型...'),
                (60, '提取知識點...'),
                (70, '生成申論題...'),
                (80, '生成摘要...'),
                (90, '創建選擇題...'),
                (95, '儲存到資料庫...')
            ]
            
            for progress, message in steps:
                self._update_job_status(job_id, 'running', progress, message)
                time.sleep(0.5)  # 模擬處理時間
            
            return result
            
        except Exception as e:
            raise Exception(f"網路擷取處理失敗: {str(e)}")
    
    def _update_job_status(self, job_id: str, status: str, progress: int, 
                          message: str, result: Any = None, error: str = None):
        """更新工作狀態 - 同時更新記憶體快取和資料庫"""
        if job_id in self.jobs:
            # 更新記憶體快取
            self.jobs[job_id].update({
                'status': status,
                'progress': progress,
                'message': message,
                'updated_at': datetime.now().isoformat()
            })
            
            if result is not None:
                self.jobs[job_id]['result'] = result
            if error is not None:
                self.jobs[job_id]['error'] = error
        
        # 更新資料庫
        self.flow_manager.db_manager.update_async_job_status(
            job_id=job_id,
            status=status,
            progress=progress,
            message=message,
            result=result,
            error=error
        )

    def cleanup_old_jobs(self, days: int = 7) -> int:
        """清理舊的工作記錄"""
        return self.flow_manager.db_manager.cleanup_old_async_jobs(days)
