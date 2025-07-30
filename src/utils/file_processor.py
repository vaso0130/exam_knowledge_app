import os
import requests
from typing import Optional, Tuple
from urllib.parse import urlparse
import tempfile

# 文件處理相關
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    from docx import Document
except ImportError:
    Document = None

try:
    from bs4 import BeautifulSoup  
except ImportError:
    BeautifulSoup = None

class FileProcessor:
    """檔案處理器，支援多種格式"""
    
    @staticmethod
    def read_text_file(file_path: str) -> str:
        """讀取純文字檔案"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # 嘗試其他編碼
            encodings = ['big5', 'gbk', 'cp1252']
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            raise ValueError(f"無法讀取檔案 {file_path}，編碼格式不支援")
    
    @staticmethod
    def read_pdf_file(file_path: str) -> str:
        """讀取PDF檔案"""
        if PyPDF2 is None:
            raise ImportError("請安裝 PyPDF2 套件：pip install PyPDF2")
        
        text = ""
        try:
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            raise ValueError(f"無法讀取PDF檔案 {file_path}: {e}")
        
        return text.strip()
    
    @staticmethod 
    def read_docx_file(file_path: str) -> str:
        """讀取Word檔案"""
        if Document is None:
            raise ImportError("請安裝 python-docx 套件：pip install python-docx")
        
        try:
            doc = Document(file_path)
            text = []
            for paragraph in doc.paragraphs:
                text.append(paragraph.text)
            return '\n'.join(text)
        except Exception as e:
            raise ValueError(f"無法讀取Word檔案 {file_path}: {e}")
    
    @staticmethod
    def read_html_file(file_path: str) -> str:
        """讀取HTML檔案"""
        if BeautifulSoup is None:
            raise ImportError("請安裝 beautifulsoup4 套件：pip install beautifulsoup4")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            # 移除 script 和 style 標籤
            for script in soup(["script", "style"]):
                script.decompose()
            
            return soup.get_text(separator='\n').strip()
        except Exception as e:
            raise ValueError(f"無法讀取HTML檔案 {file_path}: {e}")
    
    @staticmethod
    def fetch_url_content(url: str) -> str:
        """從URL獲取內容"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            if BeautifulSoup is not None:
                soup = BeautifulSoup(response.content, 'html.parser')
                # 移除 script 和 style 標籤
                for script in soup(["script", "style"]):
                    script.decompose()
                return soup.get_text(separator='\n').strip()
            else:
                return response.text
                
        except Exception as e:
            raise ValueError(f"無法獲取URL內容 {url}: {e}")
    
    @classmethod
    def process_input(cls, input_data: str) -> Tuple[str, str]:
        """
        處理輸入資料（檔案路徑、URL或純文字）
        返回：(處理後的文字內容, 輸入類型)
        """
        input_data = input_data.strip()
        
        # 檢查是否為URL
        if input_data.startswith(('http://', 'https://')):
            try:
                content = cls.fetch_url_content(input_data)
                return content, 'url'
            except Exception as e:
                raise ValueError(f"URL處理失敗: {e}")
        
        # 檢查是否為檔案路徑
        if os.path.exists(input_data):
            file_ext = os.path.splitext(input_data)[1].lower()
            
            if file_ext == '.txt':
                content = cls.read_text_file(input_data)
                return content, 'txt'
            elif file_ext == '.pdf':
                content = cls.read_pdf_file(input_data)
                return content, 'pdf'
            elif file_ext in ['.docx', '.doc']:
                content = cls.read_docx_file(input_data)
                return content, 'docx'
            elif file_ext in ['.html', '.htm']:
                content = cls.read_html_file(input_data)
                return content, 'html'
            else:
                # 嘗試當作純文字檔案讀取
                try:
                    content = cls.read_text_file(input_data)
                    return content, 'txt'
                except:
                    raise ValueError(f"不支援的檔案格式: {file_ext}")
        
        # 當作純文字處理
        return input_data, 'text'
    
    @staticmethod
    def save_markdown(content: str, file_path: str) -> None:
        """儲存Markdown檔案"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    @staticmethod
    def generate_markdown_filename(subject: str, hash_str: str) -> str:
        """生成Markdown檔案名稱"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{subject}/{timestamp}_{hash_str}.md"

class ContentValidator:
    """內容驗證器"""
    
    @staticmethod
    def is_valid_text(text: str, min_length: int = 10) -> bool:
        """檢查文字是否有效"""
        return text and len(text.strip()) >= min_length
    
    @staticmethod
    def clean_text(text: str) -> str:
        """清理文字內容"""
        if not text:
            return ""
        
        # 移除多餘的空白行
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:  # 只保留非空行
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 10000) -> str:
        """截斷過長的文字"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
