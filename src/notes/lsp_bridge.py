"""
NoteAIClient 的LSP集成模組，用於銜接外部LSP伺服器和AI功能
"""
from typing import Dict, Any, List, Optional
import asyncio
import json
import os
import subprocess

class LSPBridge:
    """
    負責與外部LSP伺服器通信的橋接類
    支持多種LSP服務，包括Markdown、Python等
    """
    def __init__(self):
        # LSP伺服器配置
        self.lsp_servers = {
            'markdown': {
                'command': 'marksman',
                'args': ['server'],
                'process': None,
                'initialized': False
            },
            'python': {
                'command': 'pyls',
                'args': [],
                'process': None,
                'initialized': False
            },
            'javascript': {
                'command': 'typescript-language-server',
                'args': ['--stdio'],
                'process': None,
                'initialized': False
            }
        }
        
        # LSP服務狀態
        self.lsp_status = {}
    
    async def initialize_server(self, language: str) -> bool:
        """
        初始化指定語言的LSP伺服器
        
        Args:
            language: 語言類型 (markdown, python等)
            
        Returns:
            是否成功初始化
        """
        if language not in self.lsp_servers:
            print(f"不支援的語言: {language}")
            return False
            
        if self.lsp_servers[language]['initialized']:
            return True
            
        try:
            # 啟動LSP伺服器進程
            cmd = [self.lsp_servers[language]['command']] + self.lsp_servers[language]['args']
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.lsp_servers[language]['process'] = process
            
            # 發送初始化請求
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "processId": os.getpid(),
                    "rootUri": None,
                    "capabilities": {}
                }
            }
            
            if process.stdin:
                init_request_str = json.dumps(init_request) + "\r\n"
                process.stdin.write(init_request_str.encode())
                await process.stdin.drain()
            
            # 讀取初始化響應
            if process.stdout:
                response_line = await process.stdout.readline()
                response = json.loads(response_line)
                
                if 'result' in response:
                    self.lsp_servers[language]['initialized'] = True
                    self.lsp_status[language] = {
                        'status': 'active',
                        'capabilities': response['result']['capabilities']
                    }
                    return True
            
            return False
            
        except Exception as e:
            print(f"LSP伺服器初始化錯誤: {e}")
            return False
    
    async def send_request(self, language: str, method: str, params: Any) -> Dict[str, Any]:
        """
        發送請求到LSP伺服器
        
        Args:
            language: 語言類型
            method: LSP方法名稱
            params: 請求參數
            
        Returns:
            LSP伺服器的回應
        """
        if language not in self.lsp_servers or not self.lsp_servers[language]['initialized']:
            if not await self.initialize_server(language):
                return {'error': f"無法初始化{language}的LSP伺服器"}
        
        try:
            request = {
                "jsonrpc": "2.0",
                "id": 2,  # 簡單起見使用固定ID
                "method": method,
                "params": params
            }
            
            process = self.lsp_servers[language]['process']
            if process and process.stdin:
                request_str = json.dumps(request) + "\r\n"
                process.stdin.write(request_str.encode())
                await process.stdin.drain()
                
                if process.stdout:
                    response_line = await process.stdout.readline()
                    return json.loads(response_line)
            
            return {'error': "LSP伺服器通信失敗"}
            
        except Exception as e:
            print(f"LSP請求錯誤: {e}")
            return {'error': str(e)}
    
    async def get_diagnostics(self, language: str, text: str, uri: str = "file:///temp.md") -> List[Dict[str, Any]]:
        """
        獲取文本的診斷信息
        
        Args:
            language: 語言類型
            text: 要診斷的文本
            uri: 文檔URI
            
        Returns:
            診斷結果列表
        """
        try:
            # 首先確保伺服器已初始化
            if not await self.initialize_server(language):
                return []
                
            # 發送文本變更通知
            await self.send_request(language, "textDocument/didOpen", {
                "textDocument": {
                    "uri": uri,
                    "languageId": language,
                    "version": 1,
                    "text": text
                }
            })
            
            # 等待一些時間讓LSP服務器處理文檔
            await asyncio.sleep(0.5)
            
            # 請求診斷結果
            # 注意: 標準LSP會通過publishDiagnostics通知返回診斷,
            # 這裡為簡化,我們假設有一個直接請求診斷的方法
            diagnostics_result = await self.send_request(language, "textDocument/diagnostic", {
                "textDocument": {"uri": uri}
            })
            
            if 'result' in diagnostics_result and 'diagnostics' in diagnostics_result['result']:
                return diagnostics_result['result']['diagnostics']
            
            return []
            
        except Exception as e:
            print(f"獲取診斷信息錯誤: {e}")
            return []
    
    async def get_completion(self, language: str, text: str, line: int, character: int, uri: str = "file:///temp.md") -> List[Dict[str, Any]]:
        """
        獲取代碼補全建議
        
        Args:
            language: 語言類型
            text: 文檔文本
            line: 光標所在行 (0-based)
            character: 光標所在列 (0-based)
            uri: 文檔URI
            
        Returns:
            補全建議列表
        """
        try:
            # 首先確保伺服器已初始化
            if not await self.initialize_server(language):
                return []
                
            # 發送文本變更通知
            await self.send_request(language, "textDocument/didOpen", {
                "textDocument": {
                    "uri": uri,
                    "languageId": language,
                    "version": 1,
                    "text": text
                }
            })
            
            # 請求補全
            completion_result = await self.send_request(language, "textDocument/completion", {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character}
            })
            
            if 'result' in completion_result and 'items' in completion_result['result']:
                return completion_result['result']['items']
                
            if 'result' in completion_result and isinstance(completion_result['result'], list):
                return completion_result['result']
                
            return []
            
        except Exception as e:
            print(f"獲取補全建議錯誤: {e}")
            return []

    async def shutdown_server(self, language: str) -> bool:
        """
        關閉LSP伺服器
        
        Args:
            language: 語言類型
            
        Returns:
            是否成功關閉
        """
        if language not in self.lsp_servers or not self.lsp_servers[language]['initialized']:
            return True  # 已經關閉或未啟動
            
        try:
            process = self.lsp_servers[language]['process']
            if process:
                # 發送關閉請求
                await self.send_request(language, "shutdown", {})
                await self.send_request(language, "exit", {})
                
                # 終止進程
                process.terminate()
                await process.wait()
                
                self.lsp_servers[language]['initialized'] = False
                self.lsp_servers[language]['process'] = None
                
                if language in self.lsp_status:
                    self.lsp_status[language]['status'] = 'inactive'
                
                return True
                
            return True
            
        except Exception as e:
            print(f"關閉LSP伺服器錯誤: {e}")
            return False
    
    async def shutdown_all(self) -> None:
        """關閉所有LSP伺服器"""
        for language in list(self.lsp_servers.keys()):
            await self.shutdown_server(language)
    
    def check_lsp_availability(self, language: str) -> bool:
        """檢查LSP是否可用"""
        if language not in self.lsp_servers:
            return False
            
        # 簡單檢查命令是否存在
        try:
            result = subprocess.run(['which', self.lsp_servers[language]['command']], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   text=True)
            return result.returncode == 0
        except Exception:
            return False
    
    def get_supported_languages(self) -> List[str]:
        """獲取支援的語言列表"""
        return list(self.lsp_servers.keys())
    
    def get_lsp_status(self) -> Dict[str, Dict[str, Any]]:
        """獲取所有LSP的狀態"""
        return self.lsp_status
