import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from PIL import Image, ImageTk
import requests
import urllib.parse
import io
import base64
import json
import threading
import subprocess
import tempfile
import os
from typing import Optional, Callable

class MindmapRenderer(ctk.CTkFrame):
    """心智圖渲染器 - 獨立模組"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        # 初始化變數
        self.current_mermaid_code = ""
        self.current_image = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """建立介面元件"""
        # 工具列
        self.toolbar = ctk.CTkFrame(self)
        self.toolbar.pack(fill="x", padx=10, pady=(10, 5))
        
        # 狀態標籤
        self.status_label = ctk.CTkLabel(
            self.toolbar,
            text="尚未載入心智圖",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(side="left", padx=10)
        
        # 控制按鈕
        self.copy_btn = ctk.CTkButton(
            self.toolbar,
            text="📋 複製代碼",
            command=self.copy_mermaid_code,
            height=30,
            width=100
        )
        self.copy_btn.pack(side="right", padx=5)
        
        self.preview_btn = ctk.CTkButton(
            self.toolbar,
            text="🌐 在線預覽",
            command=self.open_online_preview,
            height=30,
            width=100
        )
        self.preview_btn.pack(side="right", padx=5)
        
        self.refresh_btn = ctk.CTkButton(
            self.toolbar,
            text="🔄 重新渲染",
            command=self.refresh_render,
            height=30,
            width=100
        )
        self.refresh_btn.pack(side="right", padx=5)
        
        self.save_btn = ctk.CTkButton(
            self.toolbar,
            text="💾 儲存圖片",
            command=self.save_image,
            height=30,
            width=100
        )
        self.save_btn.pack(side="right", padx=5)
        
        # 主要顯示區域
        self.display_frame = ctk.CTkFrame(self)
        self.display_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # 建立標籤頁
        self.notebook = ttk.Notebook(self.display_frame)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 圖形化標籤頁
        self.image_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.image_frame, text="🖼️ 圖形化")
        
        # 建立滾動區域用於顯示圖片
        self.canvas = tk.Canvas(self.image_frame, bg="white")
        self.v_scrollbar = ttk.Scrollbar(self.image_frame, orient="vertical", command=self.canvas.yview)
        self.h_scrollbar = ttk.Scrollbar(self.image_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)
        
        self.v_scrollbar.pack(side="right", fill="y")
        self.h_scrollbar.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # 程式碼標籤頁
        self.code_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.code_frame, text="📝 程式碼")
        
        # 程式碼文字框
        try:
            font_family = "Menlo" if tk.TkVersion >= 8.5 else "Courier"
        except:
            font_family = "monospace"
            
        self.code_text = tk.Text(
            self.code_frame,
            wrap=tk.WORD,
            font=(font_family, 11),
            bg="white",
            fg="black"
        )
        
        code_scrollbar = ttk.Scrollbar(self.code_frame, orient="vertical", command=self.code_text.yview)
        self.code_text.configure(yscrollcommand=code_scrollbar.set)
        
        code_scrollbar.pack(side="right", fill="y")
        self.code_text.pack(side="left", fill="both", expand=True)
        
        # 初始化顯示
        self.show_placeholder()
    
    def show_placeholder(self):
        """顯示佔位符"""
        self.status_label.configure(text="尚未載入心智圖")
        self.code_text.delete("1.0", tk.END)
        self.code_text.insert("1.0", "# 心智圖程式碼將顯示在這裡\n\n請先選擇一個文件並生成心智圖。")
        
        # 在canvas上顯示提示文字
        self.canvas.delete("all")
        self.canvas.create_text(
            200, 100,
            text="🧠 心智圖將顯示在這裡\n\n請先選擇文件並點擊「AI心智圖」按鈕",
            font=("Arial", 14),
            fill="gray",
            justify="center"
        )
    
    def set_mermaid_code(self, mermaid_code: str, callback: Optional[Callable] = None):
        """設定並渲染 Mermaid 程式碼"""
        if not mermaid_code or not mermaid_code.strip():
            self.show_placeholder()
            return
        
        self.current_mermaid_code = mermaid_code
        
        # 更新程式碼標籤頁
        self.code_text.delete("1.0", tk.END)
        self.code_text.insert("1.0", mermaid_code)
        
        # 更新狀態
        self.status_label.configure(text="正在渲染心智圖...")
        
        # 在背景執行緒中渲染圖片
        threading.Thread(target=self._render_image_background, args=(mermaid_code, callback)).start()
    
    def _render_image_background(self, mermaid_code: str, callback: Optional[Callable] = None):
        """在背景執行緒中渲染圖片"""
        try:
            # 方法1: 優先使用本地 CLI 渲染
            image_data = self._render_via_local_cli(mermaid_code)
            
            if not image_data:
                # 方法2: 如果本地渲染失敗，嘗試使用 Mermaid.js 的線上渲染服務
                print("本地渲染失敗，嘗試線上渲染...")
                image_data = self._render_via_mermaid_live(mermaid_code)
            
            if image_data:
                # 在主執行緒中更新圖片
                self.after(0, self._update_image_display, image_data)
            else:
                # 如果所有方法都失敗，回退到文字顯示
                self.after(0, self._show_text_fallback, mermaid_code)
                
            if callback:
                callback()
                
        except Exception as e:
            # 渲染失敗，顯示錯誤
            self.after(0, self._show_error, str(e))

    def _render_via_local_cli(self, mermaid_code: str) -> Optional[bytes]:
        """使用本地 Mermaid CLI 渲染圖片"""
        try:
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.mmd', encoding='utf-8') as infile, \
                 tempfile.NamedTemporaryFile(mode='r+b', delete=False, suffix='.png') as outfile:
                
                infile.write(mermaid_code)
                infile.flush()
                
                # 確保檔案路徑是絕對路徑
                input_path = os.path.abspath(infile.name)
                output_path = os.path.abspath(outfile.name)

                # 關閉檔案以確保 mmdc 可以存取
                infile.close()
                outfile.close()

                # 執行 mmdc 命令
                # 使用 -w 800 設定寬度，-H 600 設定高度
                command = [
                    'mmdc', 
                    '-i', input_path, 
                    '-o', output_path, 
                    '-w', '1200', # 增加寬度以獲得更高解析度
                    '--backgroundColor', 'transparent'
                ]
                
                # 在 macOS 上，需要指定 Puppeteer 的設定檔路徑
                # 建立一個暫時的 puppeteer-config.json
                puppeteer_config = {
                    "args": ["--no-sandbox", "--disable-setuid-sandbox"]
                }
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as p_config:
                    json.dump(puppeteer_config, p_config)
                    p_config.flush()
                    puppeteer_config_path = os.path.abspath(p_config.name)
                    p_config.close()
                
                command.extend(['-p', puppeteer_config_path])

                subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)

                # 讀取輸出檔案
                with open(output_path, 'rb') as f:
                    image_data = f.read()
                
                # 清理暫存檔案
                os.unlink(input_path)
                os.unlink(output_path)
                os.unlink(puppeteer_config_path)
                
                if image_data:
                    print("本地渲染成功！")
                    return image_data
                return None

        except FileNotFoundError:
            print("錯誤: 'mmdc' 命令未找到。請確保 @mermaid-js/mermaid-cli 已安裝並在系統 PATH 中。")
            return None
        except subprocess.CalledProcessError as e:
            print(f"本地渲染失敗 (mmdc): {e}")
            print(f"Stderr: {e.stderr}")
            return None
        except Exception as e:
            print(f"本地渲染時發生未知錯誤: {e}")
            return None
    
    def _render_via_mermaid_live(self, mermaid_code: str) -> Optional[bytes]:
        """使用 Mermaid Live 服務渲染圖片"""
        try:
            # 方法1: 嘗試使用簡化的配置
            config = {
                "code": mermaid_code,
                "mermaid": {"theme": "default"}
            }
            
            # 使用 UTF-8 編碼並進行 base64 編碼
            config_str = json.dumps(config, ensure_ascii=False)
            encoded_config = base64.b64encode(config_str.encode('utf-8')).decode('ascii')
            
            # 構建 URL
            url = f"https://mermaid.ink/img/{encoded_config}"
            
            # 發送請求，添加適當的請求頭
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'image/png,image/*,*/*;q=0.8'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            return response.content
            
        except requests.exceptions.HTTPError as e:
            print(f"Mermaid Live HTTP 錯誤 ({e.response.status_code}): {e}")
            # 如果是 400 錯誤，可能是中文字符問題，嘗試其他方法
            if e.response.status_code == 400:
                return self._render_via_alternative_method(mermaid_code)
            return None
        except Exception as e:
            print(f"Mermaid Live 渲染失敗: {e}")
            return self._render_via_alternative_method(mermaid_code)
    
    def _render_via_alternative_method(self, mermaid_code: str) -> Optional[bytes]:
        """備用渲染方法：嘗試不同的編碼方式或服務"""
        try:
            print("嘗試備用渲染方法...")
            
            # 方法2: 嘗試直接使用程式碼，不使用配置包裝
            # 這對中文字符可能更友好
            simple_encoded = base64.b64encode(mermaid_code.encode('utf-8')).decode('ascii')
            
            # 嘗試更簡單的 URL 格式
            url = f"https://mermaid.ink/img/{simple_encoded}"
            
            headers = {
                'User-Agent': 'MindmapRenderer/1.0',
                'Accept': 'image/png'
            }
            
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            
            print("備用方法成功！")
            return response.content
            
        except Exception as e:
            print(f"備用渲染方法也失敗: {e}")
            print("將創建佔位符圖片...")
            return self._create_placeholder_image(mermaid_code)
    
    def _create_placeholder_image(self, mermaid_code: str) -> Optional[bytes]:
        """創建一個佔位符圖片，顯示渲染失敗的訊息"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import io
            
            # 創建一個簡單的圖片
            width, height = 600, 400
            image = Image.new('RGB', (width, height), color='white')
            draw = ImageDraw.Draw(image)
            
            # 繪製邊框
            draw.rectangle([10, 10, width-10, height-10], outline='gray', width=2)
            
            # 添加文字
            try:
                # 嘗試使用系統字體
                font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 16)
            except:
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 16)
                except:
                    font = ImageFont.load_default()
            
            # 錯誤訊息
            error_text = "⚠️ 心智圖渲染失敗\n\n可能原因：\n• 網路連接問題\n• 服務暫時不可用\n• 程式碼格式錯誤"
            
            # 計算文字位置
            bbox = draw.textbbox((0, 0), error_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            x = (width - text_width) // 2
            y = (height - text_height) // 2 - 50
            
            draw.multiline_text((x, y), error_text, font=font, fill='red', align='center')
            
            # 顯示部分程式碼（截斷）
            code_preview = mermaid_code[:200] + "..." if len(mermaid_code) > 200 else mermaid_code
            code_text = f"\n原始程式碼預覽：\n{code_preview}"
            
            try:
                code_font = ImageFont.truetype("/System/Library/Fonts/Monaco.ttc", 12)
            except:
                code_font = font
            
            draw.multiline_text((20, y + 120), code_text, font=code_font, fill='black', align='left')
            
            # 轉換為 bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            return img_byte_arr.getvalue()
            
        except Exception as e:
            print(f"創建佔位符圖片失敗: {e}")
            return None
    
    def _update_image_display(self, image_data: bytes):
        """更新圖片顯示"""
        try:
            # 載入圖片
            image = Image.open(io.BytesIO(image_data))
            
            # 調整圖片大小以適應顯示區域
            display_width, display_height = 800, 600
            image.thumbnail((display_width, display_height), Image.Resampling.LANCZOS)
            
            # 轉換為 Tkinter 格式
            self.current_image = ImageTk.PhotoImage(image)
            
            # 更新 canvas
            self.canvas.delete("all")
            
            # 計算居中位置
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width <= 1:  # Canvas 還沒有初始化
                canvas_width, canvas_height = 800, 600
            
            x = max(canvas_width // 2, image.width // 2)
            y = max(canvas_height // 2, image.height // 2)
            
            # 顯示圖片
            self.canvas.create_image(x, y, image=self.current_image, anchor="center")
            
            # 更新滾動區域
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
            # 更新狀態
            self.status_label.configure(text=f"心智圖渲染完成 ({image.width}x{image.height})")
            
        except Exception as e:
            self._show_error(f"圖片顯示失敗: {str(e)}")
    
    def _show_text_fallback(self, mermaid_code: str):
        """當圖片渲染失敗時，顯示文字版本"""
        self.canvas.delete("all")
        
        # 創建一個簡化的視覺化顯示
        try:
            lines = mermaid_code.split('\n')
            y_pos = 30
            x_pos = 30
            
            # 添加標題
            self.canvas.create_text(
                300, 20,
                text="📄 心智圖內容預覽（文字模式）",
                font=("Arial", 14, "bold"),
                fill="blue",
                anchor="n"
            )
            
            # 處理每一行，嘗試提取結構化信息
            for line in lines:
                if line.strip():
                    # 清理和格式化行內容
                    clean_line = line.strip()
                    
                    # 根據縮排確定層級
                    indent_level = (len(line) - len(line.lstrip())) // 2
                    indent_x = x_pos + (indent_level * 20)
                    
                    # 選擇不同的樣式
                    if clean_line.startswith('root'):
                        color = "red" 
                        font_style = ("Arial", 12, "bold")
                    elif indent_level == 1:
                        color = "blue"
                        font_style = ("Arial", 11, "bold")
                    elif indent_level == 2:
                        color = "green"
                        font_style = ("Arial", 10)
                    else:
                        color = "black"
                        font_style = ("Arial", 10)
                    
                    # 顯示文字，限制每行長度
                    display_text = clean_line[:80] + "..." if len(clean_line) > 80 else clean_line
                    
                    self.canvas.create_text(
                        indent_x, y_pos,
                        text=f"{'  ' * indent_level}• {display_text}",
                        font=font_style,
                        fill=color,
                        anchor="nw"
                    )
                    y_pos += 20
            
            # 添加說明文字
            self.canvas.create_text(
                300, y_pos + 30,
                text="注意：由於渲染服務問題，顯示為文字模式\n請使用「🌐 在線預覽」按鈕在瀏覽器中查看完整圖形",
                font=("Arial", 10),
                fill="gray",
                justify="center",
                anchor="n"
            )
            
        except Exception as e:
            # 如果文字處理也失敗，顯示原始程式碼
            self.canvas.create_text(
                20, 50,
                text=f"原始程式碼：\n{mermaid_code[:500]}{'...' if len(mermaid_code) > 500 else ''}",
                font=("Courier", 9),
                fill="black",
                anchor="nw",
                width=550
            )
        
        # 更新滾動區域
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        self.status_label.configure(text="圖片渲染失敗，顯示文字版本")
    
    def _show_error(self, error_message: str):
        """顯示錯誤訊息"""
        self.canvas.delete("all")
        self.canvas.create_text(
            200, 100,
            text=f"❌ 心智圖渲染失敗\n\n{error_message}",
            font=("Arial", 12),
            fill="red",
            justify="center"
        )
        
        self.status_label.configure(text="渲染失敗")
    
    def copy_mermaid_code(self):
        """複製 Mermaid 程式碼到剪貼簿"""
        if self.current_mermaid_code:
            try:
                self.clipboard_clear()
                self.clipboard_append(self.current_mermaid_code)
                self.status_label.configure(text="程式碼已複製到剪貼簿")
                # 3秒後恢復原狀態
                self.after(3000, lambda: self.status_label.configure(text="心智圖渲染完成"))
            except Exception as e:
                print(f"複製失敗: {e}")
    
    def open_online_preview(self):
        """在瀏覽器中開啟線上預覽"""
        if self.current_mermaid_code:
            try:
                import webbrowser
                encoded_code = urllib.parse.quote(self.current_mermaid_code)
                url = f"https://mermaid.live/edit#{encoded_code}"
                webbrowser.open(url)
            except Exception as e:
                print(f"開啟預覽失敗: {e}")
    
    def save_image(self):
        """儲存心智圖圖片"""
        if not self.current_mermaid_code:
            return
        
        try:
            from tkinter import filedialog
            import os
            from datetime import datetime
            
            # 預設檔名包含時間戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"mindmap_{timestamp}.png"
            
            # 選擇儲存位置
            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                initialfile=default_filename,
                filetypes=[
                    ("PNG files", "*.png"),
                    ("SVG files", "*.svg"),
                    ("All files", "*.*")
                ]
            )
            
            if filename:
                if filename.endswith('.svg'):
                    self._save_as_svg(filename)
                else:
                    self._save_as_png(filename)
                    
        except Exception as e:
            print(f"儲存失敗: {e}")
    
    def _save_as_png(self, filename):
        """儲存為 PNG 圖片"""
        try:
            # 重新渲染圖片用於儲存
            image_data = self._render_via_mermaid_live(self.current_mermaid_code)
            
            if image_data:
                with open(filename, 'wb') as f:
                    f.write(image_data)
                self.status_label.configure(text=f"圖片已儲存: {filename}")
                # 3秒後恢復狀態
                self.after(3000, lambda: self.status_label.configure(text="心智圖渲染完成"))
            else:
                self.status_label.configure(text="儲存失敗: 無法生成圖片")
                
        except Exception as e:
            self.status_label.configure(text=f"儲存失敗: {str(e)}")
    
    def _save_as_svg(self, filename):
        """儲存為 SVG 向量圖"""
        try:
            # 使用與圖片渲染相同的配置
            config = {
                "code": self.current_mermaid_code,
                "mermaid": {"theme": "default"}
            }
            
            config_str = json.dumps(config, ensure_ascii=False)
            encoded_config = base64.b64encode(config_str.encode('utf-8')).decode('ascii')
            
            # 使用 SVG 端點
            url = f"https://mermaid.ink/svg/{encoded_config}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'image/svg+xml,*/*;q=0.8'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(response.text)
                
            self.status_label.configure(text=f"SVG 已儲存: {filename}")
            # 3秒後恢復狀態
            self.after(3000, lambda: self.status_label.configure(text="心智圖渲染完成"))
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                # 400 錯誤時，嘗試將程式碼儲存為文字檔案
                self._save_as_text_fallback(filename)
            else:
                self.status_label.configure(text=f"儲存 SVG 失敗: HTTP {e.response.status_code}")
        except Exception as e:
            self.status_label.configure(text=f"儲存 SVG 失敗: {str(e)}")
    
    def _save_as_text_fallback(self, original_filename):
        """當 SVG 儲存失敗時，將 Mermaid 程式碼儲存為文字檔案"""
        try:
            # 將副檔名改為 .txt
            base_name = original_filename.rsplit('.', 1)[0]
            txt_filename = f"{base_name}_mermaid.txt"
            
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write("# Mermaid 心智圖程式碼\n")
                f.write("# 由於渲染服務問題，儲存為原始程式碼\n")
                f.write("# 可以複製到 https://mermaid.live 進行編輯\n\n")
                f.write(self.current_mermaid_code)
            
            self.status_label.configure(text=f"程式碼已儲存為文字檔: {txt_filename}")
            # 3秒後恢復狀態
            self.after(3000, lambda: self.status_label.configure(text="心智圖渲染完成"))
            
        except Exception as e:
            self.status_label.configure(text=f"儲存文字檔案也失敗: {str(e)}")
    
    def refresh_render(self):
        """重新渲染當前心智圖"""
        if self.current_mermaid_code:
            self.set_mermaid_code(self.current_mermaid_code)
    
    def clear(self):
        """清空顯示"""
        self.current_mermaid_code = ""
        self.current_image = None
        self.show_placeholder()
