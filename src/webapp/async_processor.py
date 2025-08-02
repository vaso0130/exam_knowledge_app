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
    """非同步處理器"""
    
    def __init__(self, flow_manager):
        self.flow_manager = flow_manager
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.results_dir = Path("async_results")
        self.results_dir.mkdir(exist_ok=True)
        
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
        self._save_job_status(job_id, job_info)
        
        # 啟動背景線程處理
        thread = threading.Thread(
            target=self._process_job,
            args=(job_id, job_type, kwargs),
            daemon=True
        )
        thread.start()
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """取得工作狀態"""
        if job_id in self.jobs:
            return self.jobs[job_id]
        
        # 嘗試從檔案載入
        return self._load_job_status(job_id)
    
    def _process_job(self, job_id: str, job_type: str, kwargs: Dict[str, Any]):
        """處理工作的背景方法"""
        try:
            self._update_job_status(job_id, 'running', 10, '開始處理...')
            
            if job_type == 'content_processing':
                result = self._process_content(job_id, **kwargs)
            elif job_type == 'question_processing':
                result = self._process_question(job_id, **kwargs)
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
    
    def _update_job_status(self, job_id: str, status: str, progress: int, 
                          message: str, result: Any = None, error: str = None):
        """更新工作狀態"""
        if job_id in self.jobs:
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
            
            self._save_job_status(job_id, self.jobs[job_id])
    
    def _save_job_status(self, job_id: str, job_info: Dict[str, Any]):
        """儲存工作狀態到檔案"""
        try:
            status_file = self.results_dir / f"{job_id}.json"
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(job_info, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"儲存工作狀態失敗: {e}")
    
    def _load_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """從檔案載入工作狀態"""
        try:
            status_file = self.results_dir / f"{job_id}.json"
            if status_file.exists():
                with open(status_file, 'r', encoding='utf-8') as f:
                    job_info = json.load(f)
                    self.jobs[job_id] = job_info
                    return job_info
        except Exception as e:
            print(f"載入工作狀態失敗: {e}")
        
        return None
    
    def cleanup_old_jobs(self, days: int = 7):
        """清理舊的工作記錄"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        for job_file in self.results_dir.glob("*.json"):
            if job_file.stat().st_mtime < cutoff_time:
                try:
                    job_file.unlink()
                    job_id = job_file.stem
                    if job_id in self.jobs:
                        del self.jobs[job_id]
                except Exception as e:
                    print(f"清理工作檔案失敗: {e}")
