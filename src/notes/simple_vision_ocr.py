"""
簡化OCR處理器 - 專為筆記手寫識別優化
針對稀疏中文字、數字、手寫內容的快速識別
與主程式的文檔OCR分離，專注於筆記場景
"""

import os
import logging
from typing import Optional, Tuple
from PIL import Image
import numpy as np
import io

logger = logging.getLogger(__name__)

# Google Vision OCR - 直接導入避免循環依賴
try:
    from google.cloud import vision
    from google.oauth2 import service_account
    VISION_AVAILABLE = True
except ImportError:
    vision = None
    service_account = None
    VISION_AVAILABLE = False


class NotesVisionOCR:
    """筆記專用的Google Vision OCR處理器"""
    
    def __init__(self, credentials_path: str = "google_credentials.json"):
        """初始化筆記專用OCR客戶端"""
        self.client = None
        self.credentials_path = credentials_path
        
        if not VISION_AVAILABLE:
            logger.error("google-cloud-vision 未安裝，筆記OCR功能將不可用")
            return
        
        try:
            if os.path.exists(credentials_path):
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
                credentials = service_account.Credentials.from_service_account_file(credentials_path)
                self.client = vision.ImageAnnotatorClient(credentials=credentials)
                logger.info("筆記專用Google Vision OCR初始化成功")
            else:
                logger.error(f"找不到憑證檔案 {credentials_path}，筆記OCR功能將不可用")
        except Exception as e:
            logger.error(f"初始化筆記專用Google Vision OCR失敗: {e}")
    
    def _preprocess_image_for_ocr(self, image_path: str) -> str:
        """
        預處理圖片以改善OCR識別效果
        處理透明背景、增強對比度等
        
        Args:
            image_path: 原始圖片路徑
            
        Returns:
            str: 處理後的圖片路徑（臨時檔案）
        """
        try:
            img = Image.open(image_path)
            logger.info(f"原始圖片: {img.size}, 模式: {img.mode}")
            
            # 如果是RGBA格式，需要處理透明度
            if img.mode == 'RGBA':
                logger.info("檢測到RGBA格式，進行透明度處理...")
                
                # 創建白色背景
                background = Image.new('RGB', img.size, (255, 255, 255))
                
                # 將RGBA圖片合成到白色背景上
                background.paste(img, mask=img.split()[3])  # 使用alpha通道作為mask
                img = background
                logger.info("已將透明背景轉換為白色背景")
            
            # 確保是RGB格式
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 檢查圖片是否主要是黑色內容
            img_array = np.array(img)
            avg_brightness = img_array.mean()
            logger.info(f"圖片平均亮度: {avg_brightness}")
            
            # 如果圖片太暗，進行反色處理
            if avg_brightness < 128:
                logger.info("圖片偏暗，進行反色處理以改善識別...")
                img_array = 255 - img_array
                img = Image.fromarray(img_array.astype(np.uint8))
            
            # 增強對比度
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)  # 增強對比度
            logger.info("已增強圖片對比度")
            
            # 保存處理後的圖片到臨時檔案
            processed_path = image_path.replace('.png', '_processed.png')
            img.save(processed_path, 'PNG')
            logger.info(f"處理後的圖片已保存到: {processed_path}")
            
            return processed_path
            
        except Exception as e:
            logger.error(f"圖片預處理失敗: {e}")
            return image_path  # 返回原始路徑

    def extract_handwriting_text(self, image_path: str) -> str:
        """
        專為筆記手寫優化的文字提取
        
        Args:
            image_path: 圖片路徑
            
        Returns:
            str: 識別到的文字，針對手寫優化
        """
        if self.client is None:
            raise ValueError("筆記OCR客戶端未初始化")

        try:
            # 首先預處理圖片以改善識別效果
            processed_image_path = self._preprocess_image_for_ocr(image_path)
            
            with open(processed_image_path, 'rb') as image_file:
                content = image_file.read()

            image = vision.Image(content=content)
            
            # 策略1: 優先使用TEXT_DETECTION（更適合手寫和稀疏文字）
            logger.info("使用TEXT_DETECTION進行手寫識別...")
            text_response = self.client.text_detection(image=image)
            
            if text_response.error.message:
                logger.warning(f'TEXT_DETECTION錯誤: {text_response.error.message}')
            else:
                texts = text_response.text_annotations
                if texts and texts[0].description.strip():
                    result = texts[0].description.strip()
                    logger.info(f"TEXT_DETECTION成功識別手寫: '{result}'")
                    return self._clean_handwriting_result(result)
            
            # 策略2: 如果TEXT_DETECTION失敗，嘗試DOCUMENT_TEXT_DETECTION
            logger.info("TEXT_DETECTION無結果，嘗試DOCUMENT_TEXT_DETECTION...")
            doc_response = self.client.document_text_detection(image=image)
            
            if doc_response.error.message:
                logger.warning(f'DOCUMENT_TEXT_DETECTION錯誤: {doc_response.error.message}')
            else:
                # 對於多行內容，使用DOCUMENT_TEXT_DETECTION的結構化結果
                if doc_response.full_text_annotation and doc_response.full_text_annotation.text:
                    # 使用原始換行結構
                    result = doc_response.full_text_annotation.text.strip()
                    logger.info(f"DOCUMENT_TEXT_DETECTION識別手寫: '{result}' (保持原始換行)")
                    return self._clean_handwriting_result(result)
                    
                # 嘗試從結構化資料重建文字
                elif doc_response.full_text_annotation and doc_response.full_text_annotation.pages:
                    structured_text = self._extract_structured_text(doc_response.full_text_annotation)
                    if structured_text:
                        logger.info(f"從結構化資料重建文字: '{structured_text}'")
                        return self._clean_handwriting_result(structured_text)
            
            # 策略3: 嘗試原始圖片（沒有預處理）
            logger.info("嘗試使用原始圖片進行識別...")
            with open(image_path, 'rb') as image_file:
                original_content = image_file.read()
            
            original_image = vision.Image(content=original_content)
            original_response = self.client.text_detection(image=original_image)
            
            if not original_response.error.message:
                texts = original_response.text_annotations
                if texts and texts[0].description.strip():
                    result = texts[0].description.strip()
                    logger.info(f"原始圖片TEXT_DETECTION識別成功: '{result}'")
                    return self._clean_handwriting_result(result)
            
            logger.info("所有識別方法都無法檢測到文字")
            return ""

        except Exception as e:
            logger.error(f"筆記OCR處理失敗: {e}")
            raise ValueError(f"筆記OCR處理失敗: {e}")
        finally:
            # 清理臨時檔案
            if 'processed_image_path' in locals() and processed_image_path != image_path:
                try:
                    os.remove(processed_image_path)
                    logger.info("已清理臨時處理檔案")
                except:
                    pass
    
    def _clean_handwriting_result(self, text: str) -> str:
        """
        清理手寫識別結果，針對筆記場景優化
        
        Args:
            text: 原始識別結果
            
        Returns:
            str: 清理後的文字
        """
        if not text:
            return ""

        # 保持原始的換行結構，只清理每一行
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                # 移除常見的OCR錯誤字符
                line = line.replace('|', 'I')  # 常見錯誤：管道符號誤認為I
                
                # 全形數字轉半形
                line = line.replace('０', '0').replace('１', '1').replace('２', '2')
                line = line.replace('３', '3').replace('４', '4').replace('５', '5')
                line = line.replace('６', '6').replace('７', '7').replace('８', '8').replace('９', '9')
                
                # 程式碼相關的常見錯誤修正
                line = self._fix_code_ocr_errors(line)
                
                # 移除多餘空格
                line = ' '.join(line.split())
                
                # 對單行進行數學等式修正
                line = self._fix_math_equation_order(line)
                
                cleaned_lines.append(line)

        # 根據內容智能決定格式
        return self._format_multiline_content(cleaned_lines)
    
    def _fix_code_ocr_errors(self, line: str) -> str:
        """
        修正程式碼中常見的OCR識別錯誤
        
        Args:
            line: 原始行
            
        Returns:
            str: 修正後的行
        """
        # 常見的程式碼OCR錯誤修正
        corrections = {
            # 變數和運算符
            'I = !': 'i = 1',  # 常見錯誤：I誤認為i，!誤認為1
            'I--I': 'i -= 1',  # 減法賦值
            'I - = ': 'i -= ',  # 空格問題
            '- =': '-=',       # 運算符空格
            '+ =': '+=',
            '= =': '==',
            '! =': '!=',
            '< =': '<=',
            '> =': '>=',
            
            # Python關鍵字
            'elsf': 'elif:',
            'elsfi': 'elif:',
            'elifi': 'elif:',
            'eIse': 'else:',
            'eIif': 'elif:',
            'prjnt': 'print',
            'prlnt': 'print',
            'pr1nt': 'print',
            'if i <': 'if i <',  # 確保空格正確
            'it is': '# it is',  # 可能是註解
            
            # 引號和括號
            '("H:")': '("Hi")',  # 常見字串
            '("H:': '("Hi")',
            '"H:"': '"Hi"',
        }
        
        # 應用修正
        for wrong, correct in corrections.items():
            if wrong in line:
                line = line.replace(wrong, correct)
                logger.info(f"修正程式碼錯誤: '{wrong}' -> '{correct}'")
        
        return line
    
    def _format_multiline_content(self, lines: list) -> str:
        """
        根據內容類型智能格式化多行內容
        
        Args:
            lines: 清理後的文字行列表
            
        Returns:
            str: 格式化後的文字
        """
        if not lines:
            return ""
        
        if len(lines) == 1:
            return lines[0]
        
        # 檢查是否包含程式碼特徵
        code_indicators = [
            '=', '(', ')', '{', '}', '[', ']', ';', 
            'def ', 'function', 'if ', 'for ', 'while ',
            'class ', 'import ', 'from ', 'return',
            'var ', 'let ', 'const ', '//', '/*', '*/',
            'print', 'console.log', '++', '--', '+=', '-=',
            '==', '!=', '<=', '>=', '&&', '||',
            'elif', 'else:', 'if:', 'for:', 'while:', 'def:',
            'print(', 'input(', 'len(', 'range(',
            '< ', '> ', '<= ', '>= ', '== ', '!= '
        ]
        
        # 檢查是否有程式碼特徵
        full_text = ' '.join(lines)
        has_code_features = any(indicator in full_text.lower() for indicator in [x.lower() for x in code_indicators])
        
        # 額外檢查Python關鍵字和結構
        python_patterns = [
            r'\bif\b', r'\belif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', 
            r'\bdef\b', r'\bclass\b', r'\bprint\b', r'\breturn\b',
            r'\w+\s*=\s*\d+', r'print\s*\(', r'if\s+\w+\s*[<>=!]'
        ]
        
        import re
        has_python_structure = any(re.search(pattern, full_text, re.IGNORECASE) for pattern in python_patterns)
        
        # 檢查是否是數學內容
        has_math = bool(re.search(r'[\+\-\*\/\=\(\)]+', full_text))
        
        # 強制保持多行的條件
        force_multiline = len(lines) > 2 or has_code_features or has_python_structure
        
        if force_multiline:
            if has_code_features or has_python_structure:
                logger.info(f"檢測到程式碼內容，保持多行格式 (共{len(lines)}行)")
            else:
                logger.info(f"檢測到多行內容，保持格式 (共{len(lines)}行)")
            return '\n'.join(lines)
        elif len(lines) <= 2 and has_math and not (has_code_features or has_python_structure):
            # 簡單的數學表達式，可以合併為一行
            logger.info("檢測到簡單數學表達式，合併為一行")
            return ' '.join(lines)
        else:
            # 其他多行內容，保持換行
            logger.info(f"默認保持多行格式，共{len(lines)}行")
            return '\n'.join(lines)
    
    def _fix_math_equation_order(self, text: str) -> str:
        """
        修正數學等式的順序問題
        Google Vision API有時會從右到左讀取，導致等式顛倒
        
        Args:
            text: 原始文字
            
        Returns:
            str: 修正後的文字
        """
        import re
        
        # 移除可能誤識別的日文字符
        japanese_chars = ['て', 'の', 'を', 'に', 'は', 'が', 'と', 'で', 'も', 'な']
        for char in japanese_chars:
            text = text.replace(char, '')
        
        text = text.strip()
        
        # 檢查是否是簡單的數學等式且順序可能顛倒
        # 例如："2=1+1" 應該是 "1+1=2"
        math_pattern = r'^(\d+)=(\d+[\+\-\*\/]\d+)$'
        match = re.match(math_pattern, text)
        
        if match:
            result = match.group(1)
            expression = match.group(2)
            
            # 檢查等式是否正確，如果正確但順序顛倒，則修正
            try:
                calculated_result = eval(expression)
                if calculated_result == int(result):
                    corrected = f"{expression}={result}"
                    logger.info(f"修正數學等式順序: '{text}' -> '{corrected}'")
                    return corrected
            except:
                # 如果計算失敗，返回原文
                pass
        
        return text
    
    def _extract_structured_text(self, annotation) -> str:
        """
        從Google Vision API的結構化註解中提取文字，保持行結構
        
        Args:
            annotation: full_text_annotation 物件
            
        Returns:
            str: 提取的結構化文字
        """
        try:
            lines = []
            
            for page in annotation.pages:
                for block in page.blocks:
                    block_lines = []
                    for paragraph in block.paragraphs:
                        para_words = []
                        for word in paragraph.words:
                            word_text = ''.join([symbol.text for symbol in word.symbols])
                            para_words.append(word_text)
                        
                        if para_words:
                            block_lines.append(' '.join(para_words))
                    
                    if block_lines:
                        lines.extend(block_lines)
            
            result = '\n'.join(lines) if lines else ""
            logger.info(f"結構化提取得到 {len(lines)} 行文字")
            return result
            
        except Exception as e:
            logger.warning(f"結構化文字提取失敗: {e}")
            return ""


class SimpleVisionOCR:
    """筆記系統的簡化OCR介面"""
    
    def __init__(self):
        """初始化筆記OCR處理器"""
        self.notes_ocr = None
        
        if VISION_AVAILABLE:
            try:
                self.notes_ocr = NotesVisionOCR()
                logger.info("筆記OCR系統初始化成功")
            except Exception as e:
                logger.error(f"筆記OCR系統初始化失敗: {e}")
                self.notes_ocr = None
        else:
            logger.error("Google Vision OCR不可用")
    
    def extract_text_from_image(self, image_path: str) -> Tuple[str, str]:
        """
        從圖片提取文字 - 筆記專用介面
        
        Args:
            image_path: 圖片路徑
            
        Returns:
            Tuple[str, str]: (識別到的文字, 使用的方法)
        """
        if not os.path.exists(image_path):
            raise ValueError(f"圖片檔案不存在: {image_path}")
        
        if not self.notes_ocr or not self.notes_ocr.client:
            logger.error("筆記OCR服務不可用")
            return "[OCR服務不可用]", "錯誤"
        
        try:
            logger.info(f"使用筆記專用OCR識別圖片: {image_path}")
            
            # 使用針對手寫優化的識別方法
            result = self.notes_ocr.extract_handwriting_text(image_path)
            
            if result and len(result.strip()) > 0:
                logger.info(f"筆記OCR識別成功: '{result.strip()}'")
                return result.strip(), "筆記專用Vision API"
            else:
                logger.warning("筆記OCR未識別到文字內容")
                return "[無法識別文字內容]", "筆記專用Vision API"
                
        except Exception as e:
            logger.error(f"筆記OCR識別失敗: {e}")
            return f"[識別失敗: {str(e)}]", "錯誤"
    
    def get_status_info(self) -> dict:
        """獲取筆記OCR狀態資訊"""
        return {
            'vision_available': self.notes_ocr is not None and self.notes_ocr.client is not None,
            'preferred_method': '筆記專用Vision API (手寫優化)',
            'fallback_methods': [],
            'optimized_for': ['手寫中文', '稀疏數字', '筆記內容']
        }


# 全域實例
_simple_vision_ocr_instance = None

def get_simple_vision_ocr() -> SimpleVisionOCR:
    """獲取SimpleVisionOCR全域實例"""
    global _simple_vision_ocr_instance
    if _simple_vision_ocr_instance is None:
        _simple_vision_ocr_instance = SimpleVisionOCR()
    return _simple_vision_ocr_instance
