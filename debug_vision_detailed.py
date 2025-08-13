#!/usr/bin/env python3
import sys
sys.path.append('.')
from google.cloud import vision
import os
from PIL import Image
import numpy as np

# 設置Google Vision API
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google_credentials.json'
client = vision.ImageAnnotatorClient()

img_path = r'F:\exam_knowledge_uploads\handwriting_20250813_225649_f3207b28.png'

print("=== 詳細分析 Google Vision API 識別結果 ===")

# 測試處理後的圖片
processed_path = img_path.replace('.png', '_debug_check.png')
with open(processed_path, 'rb') as image_file:
    content = image_file.read()

image = vision.Image(content=content)
response = client.text_detection(image=image)

if response.text_annotations:
    print(f"識別到的文字數量: {len(response.text_annotations)}")
    
    # 詳細分析每個文字塊
    for i, text in enumerate(response.text_annotations):
        print(f"\n文字塊 {i}:")
        print(f"  內容: '{text.description}'")
        if hasattr(text, 'bounding_poly') and text.bounding_poly:
            vertices = text.bounding_poly.vertices
            if vertices:
                print(f"  位置: ({vertices[0].x}, {vertices[0].y}) - ({vertices[2].x}, {vertices[2].y})")
        
        # 只分析前5個文字塊，避免輸出太多
        if i >= 5:
            break
else:
    print("沒有識別到任何文字")

if response.error.message:
    print(f'錯誤: {response.error.message}')

print("\n=== 檢查圖片方向 ===")
img = Image.open(processed_path)
img_array = np.array(img)

# 檢查圖片是否需要旋轉（基於文字的位置分布）
# 這裡我們可以看看是否有明顯的水平或垂直文字模式
print(f"圖片尺寸: {img.size}")
print(f"圖片陣列形狀: {img_array.shape}")
