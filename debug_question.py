#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
調試指定題目的答案解析問題
檢查題目ID: d052ba1c-f2d2-4721-b749-f1f387fb9fa9
"""

import sys
import os
import json
import markdown

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from src.core.database import DatabaseManager

def main():
    # 初始化資料庫管理器
    db = DatabaseManager()
    
    # 查詢指定題目
    question_id = "d052ba1c-f2d2-4721-b749-f1f387fb9fa9"
    print(f"🔍 查詢題目ID: {question_id}")
    print("=" * 60)
    
    try:
        question = db.get_question_by_id(question_id)
        
        if not question:
            print("❌ 找不到指定的題目")
            return
        
        print("✅ 找到題目！")
        print(f"📝 標題: {question.get('title', '無標題')}")
        print(f"📚 科目: {question.get('subject', '未知')}")
        print(f"📄 文件來源: {question.get('doc_title', '未知')}")
        print(f"🕐 建立時間: {question.get('created_at', '未知')}")
        
        print("\n" + "=" * 60)
        print("🎯 題目內容:")
        print("-" * 30)
        question_text = question.get('question_text', '')
        print(question_text[:500] + "..." if len(question_text) > 500 else question_text)
        
        print("\n" + "=" * 60)
        print("✅ 原始答案內容:")
        print("-" * 30)
        answer_text = question.get('answer_text', '')
        if answer_text:
            print(f"答案長度: {len(answer_text)} 字符")
            print("\n原始答案內容:")
            print(answer_text[:1000] + "..." if len(answer_text) > 1000 else answer_text)
            
            print("\n" + "=" * 60)
            print("🔧 Markdown 解析測試:")
            print("-" * 30)
            
            try:
                # 使用與 webapp 相同的 markdown 配置
                md = markdown.Markdown(extensions=['sane_lists', 'codehilite', 'fenced_code', 'tables'])
                html_output = md.convert(answer_text)
                
                print("✅ Markdown 解析成功!")
                print(f"HTML 輸出長度: {len(html_output)} 字符")
                print("\nHTML 預覽:")
                print(html_output[:800] + "..." if len(html_output) > 800 else html_output)
                
                # 檢查是否包含SQL語法
                if "SELECT" in answer_text.upper() or "CREATE" in answer_text.upper() or "INSERT" in answer_text.upper():
                    print("\n⚠️  檢測到SQL語法內容")
                
                # 檢查可能的問題字符
                problematic_chars = [char for char in answer_text if ord(char) > 127 and char not in '，。；：！？（）【】｛｝']
                if problematic_chars:
                    print(f"\n⚠️  檢測到特殊字符: {set(problematic_chars)}")
                
            except Exception as md_error:
                print(f"❌ Markdown 解析失敗: {md_error}")
                print(f"錯誤類型: {type(md_error).__name__}")
                
                # 嘗試分段解析
                print("\n🔍 嘗試分段解析...")
                lines = answer_text.split('\n')
                for i, line in enumerate(lines[:10]):  # 只檢查前10行
                    try:
                        md_test = markdown.Markdown(extensions=['sane_lists', 'codehilite', 'fenced_code', 'tables'])
                        md_test.convert(line)
                        print(f"✅ 第{i+1}行解析成功: {line[:50]}...")
                    except Exception as line_error:
                        print(f"❌ 第{i+1}行解析失敗: {line[:50]}... | 錯誤: {line_error}")
                        
        else:
            print("❌ 沒有答案內容")
            
        # 檢查答案來源
        answer_sources = question.get('answer_sources')
        if answer_sources:
            print(f"\n📚 答案來源: {answer_sources}")
            
    except Exception as e:
        print(f"❌ 查詢過程發生錯誤: {e}")
        print(f"錯誤類型: {type(e).__name__}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
