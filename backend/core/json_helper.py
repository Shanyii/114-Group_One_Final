"""
@module json_helper
@description 提供強健的 JSON 解析與自動修復機制，專門應對 LLM 輸出被截斷（Token 限制）或格式不完美的問題。
@author 黃柏豪
@version 1.0.0
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


def repair_truncated_json(raw: str) -> str:
    """
    嘗試修復因 Token 截斷或格式異常而損壞的 JSON 字串，使其能被成功 loads。
    
    支援：
    1. 移除 Markdown 標記 (```json ... ```)
    2. 自動閉合未結束的雙引號
    3. 自動閉合未結束的花括號 {} 與中括號 []
    4. 陣列模式下，若最後一個元素損壞，自動丟棄最後一個不完整元素並閉合陣列
    5. 物件模式下，若最後一個欄位損壞，自動丟棄該欄位並閉合花括號
    """
    raw = raw.strip()
    if not raw:
        return raw

    # 1. 嘗試直接解析
    try:
        json.loads(raw)
        return raw
    except json.JSONDecodeError:
        pass

    # 2. 提取 JSON 內容（去除 markdown 或前導後隨字元）
    match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if match:
        raw = match.group(1).strip()
    else:
        # 尋找第一個 [ 或 { 
        start_arr = raw.find('[')
        start_obj = raw.find('{')
        if start_arr != -1 and (start_obj == -1 or start_arr < start_obj):
            raw = raw[start_arr:]
        elif start_obj != -1:
            raw = raw[start_obj:]

    # 再次嘗試直接解析
    try:
        json.loads(raw)
        return raw
    except json.JSONDecodeError:
        pass

    # 3. 狀態掃描，找出未閉合狀態並補齊
    in_string = False
    escaped = False
    stack = []
    clean_chars = []

    for char in raw:
        if escaped:
            escaped = False
            clean_chars.append(char)
            continue
        if char == '\\':
            escaped = True
            clean_chars.append(char)
            continue
        if char == '"':
            in_string = not in_string
            clean_chars.append(char)
            continue
        
        if not in_string:
            if char in ('{', '['):
                stack.append(char)
            elif char in ('}', ']'):
                if stack:
                    # 為了強健性，遇到對應閉合就 pop
                    top = stack[-1]
                    if (char == '}' and top == '{') or (char == ']' and top == '['):
                        stack.pop()
        clean_chars.append(char)

    fixed = "".join(clean_chars)

    # 補齊引號
    if in_string:
        fixed += '"'

    # 倒序閉合括號
    temp_fixed = fixed
    for s in reversed(stack):
        if s == '{':
            temp_fixed = temp_fixed.rstrip(' \t\n\r, :')
            # 處理可能殘留的 "key": 或 "key": "value 被截斷
            # 如果尾部以冒號結尾，表示有鍵無值，補上 null
            if temp_fixed.endswith(':'):
                temp_fixed += ' null'
            temp_fixed += '}'
        elif s == '[':
            temp_fixed = temp_fixed.rstrip(' \t\n\r,')
            temp_fixed += ']'

    # 測試基礎修復是否成功
    try:
        json.loads(temp_fixed)
        return temp_fixed
    except json.JSONDecodeError:
        pass

    # 4. 陣列 (Array) 級別修復：丟棄最後一個不完整的元素
    # 例如：[{"a":1}, {"a":2
    if fixed.startswith('['):
        last_brace = fixed.rfind('}')
        if last_brace != -1:
            truncated = fixed[:last_brace+1].rstrip(' \t\n\r,')
            truncated += ']'
            try:
                json.loads(truncated)
                logger.info("[JSONHelper] 陣列截斷修復成功（丟棄了最後一題不完整項目）")
                return truncated
            except json.JSONDecodeError:
                pass

    # 5. 物件 (Object) 級別修復：丟棄最後一個不完整的屬性
    if fixed.startswith('{'):
        # 循序往回找逗號，試圖丟棄最後一個鍵值對
        idx = len(fixed)
        while True:
            idx = fixed.rfind(',', 0, idx)
            if idx == -1:
                break
            truncated = fixed[:idx].rstrip(' \t\n\r') + '}'
            try:
                json.loads(truncated)
                logger.info("[JSONHelper] 物件截斷修復成功（丟棄了最後一項不完整欄位）")
                return truncated
            except json.JSONDecodeError:
                pass

    # 6. 若都失敗，回傳原本的，讓後續處理
    return raw


def safe_json_loads(raw: str, default_factory=dict) -> dict | list:
    """
    安全解析 JSON，若失敗則進行自動修復。
    
    Args:
        raw: 原始 JSON 字串
        default_factory: 解析完全失敗時的回傳預設型別（dict 或 list）
        
    Returns:
        dict | list: 解析後的 Python 物件
    """
    if not raw:
        return default_factory()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 嘗試修復
    repaired = repair_truncated_json(raw)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as exc:
        logger.error("[JSONHelper] 無法修復 JSON。原始內容前100字：%s... 錯誤：%s", raw[:100], exc)
        return default_factory()
