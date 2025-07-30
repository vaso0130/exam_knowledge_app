import json
import re
from typing import Dict, Any, Optional

def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    從可能包含 Markdown 格式的文字中提取 JSON 物件。

    Args:
        text: 從 API 返回的原始文字。

    Returns:
        解析後的字典物件，如果解析失敗則返回 None。
    """
    if not isinstance(text, str):
        return None

    # 1. 尋找被 ```json ... ``` 包圍的區塊
    match = re.search(r"```json\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        json_str = match.group(1)
    else:
        # 2. 如果沒有找到 markdown 區塊，嘗試尋找第一個 '{' 到最後一個 '}'
        start_index = text.find('{')
        end_index = text.rfind('}')
        if start_index != -1 and end_index != -1 and start_index < end_index:
            json_str = text[start_index:end_index + 1]
        else:
            # 3. 如果還是找不到，直接使用原始文字
            json_str = text

    try:
        # 清理可能的控制字元
        cleaned_str = ''.join(c for c in json_str if c.isprintable() or c in '\n\t')
        return json.loads(cleaned_str)
    except json.JSONDecodeError:
        # 如果解析失敗，返回 None
        return None
