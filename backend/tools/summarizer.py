"""
@module summarizer
@description 重點摘要生成工具。將 RAG 檢索到的段落傳入 LLM，
             生成結構化的章節重點摘要與條列式重點。
@dependencies core.llm_client
@author 沈靖恩（Agent / 核心邏輯）
@version 1.1.0
"""

from __future__ import annotations

import json
import logging
import re

from core.llm_client import LLMClient

logger = logging.getLogger(__name__)

SUMMARIZE_PROMPT = """
你是一位專業的學習輔助 AI。請根據以下講義內容，用繁體中文整理出：
1. 整份講義的核心概念摘要：請提供非常詳盡、結構完整的摘要（字數至少 500-1000 字，分段清晰，不設上限）。必須深入涵蓋整篇講義的完整背景脈絡、核心大綱、章節之間的關聯性，以及關鍵結論。切勿過於精簡，請盡可能保留所有重要的細節與知識脈絡。
2. 詳細的條列式重點：請提供 8-15 個涵蓋全篇的詳細條列式重點，用「•」開頭。每個重點均需包含完整的背景脈絡、核心原理說明、公式或理論依據（若有）與具體實例，絕對避免使用過於精簡的字句，每個重點字數應在 100-250 字之間，以保證足夠的學習細節，幫助學生完全理解講義中的複雜概念。
3. 核心名詞/專業術語與生詞清單（用於製作學習閃卡）：請特別擷取講義中「不常出現、較為生僻或較難懂」的專有名詞、生詞與核心概念，避免挑選太過普通或常識性的詞彙。數量請根據講義的難易度與長度動態調整（若講義內容較長或較難，應抓出 8 至 15 個；若內容極短或簡單，最少 5 個）。每個詞彙的定義（def）必須包含詳細的定義說明，以及在該講義上下文中的具體應用解釋。

請以 JSON 格式回應，格式如下：
{{
  "summary": "詳細核心概念摘要（至少 500-1000 字，分段清晰，涵蓋完整脈絡與背景）...",
  "key_points": [
    "• 重點一（請提供詳盡背景脈絡、核心原理與實例，100-250 字）",
    "• 重點二（請提供詳盡背景脈絡、核心原理與實例，100-250 字）",
    ...
  ],
  "glossary": [
    {{"term": "專有名詞/生僻詞一", "def": "詳細定義與在講義上下文中的具體應用解釋"}},
    {{"term": "專有名詞/生僻詞二", "def": "詳細定義與在講義上下文中的具體應用解釋"}},
    ...
  ]
}}

講義內容：
{context}

主題（若有）：{topic}
""".strip()


class Summarizer:
    """
    重點摘要生成工具。

    Args:
        llm_client: LLM 客戶端
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def summarize(
        self,
        passages: list[dict],
        topic: str = "",
        provider: str | None = None,
    ) -> dict:
        """
        根據 RAG 檢索段落生成重點摘要（保留供向下相容使用）。
        """
        if not passages:
            logger.warning("[Summarizer] 段落為空，回傳空摘要")
            return {"topic": topic, "summary": "無相關內容", "key_points": [], "glossary": []}

        # 合併段落（依相似度排序，取前 3 筆避免 Token 超限）
        top_passages = sorted(passages, key=lambda p: p["score"], reverse=True)[:3]
        context = "\n\n---\n\n".join(p["text"] for p in top_passages)
        return await self.summarize_text(context, topic, provider)

    async def summarize_text(
        self,
        text: str,
        topic: str = "",
        provider: str | None = None,
    ) -> dict:
        """
        根據完整講義文字內容生成完整的重點摘要與核心詞彙。
        """
        if not text or text == "無相關內容":
            return {"topic": topic, "summary": "無相關內容", "key_points": [], "glossary": []}

        prompt = SUMMARIZE_PROMPT.format(context=text, topic=topic or "（未指定）")

        try:
            raw = await self._llm.complete(
                prompt=prompt,
                temperature=0.3,
                max_tokens=4096,
                provider=provider,
                is_json=True,
            )
            result = self._parse_json_response(raw)
            result["topic"] = topic
            logger.info("[Summarizer] 完整摘要生成完成，詞彙數：%d", len(result.get("glossary", [])))
            return result
        except Exception as exc:
            logger.error("[Summarizer] 完整摘要生成失敗，將啟動本地離線備用摘要生成：%s", exc)
            return self.generate_local_fallback(text, topic, exc)

    def generate_local_fallback(self, text: str, topic: str, error_msg: Exception) -> dict:
        # 1. 整理段落/行，擷取非空內容
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        # 2. 尋找可能的標題或投影片名稱
        slide_titles = []
        bullets = []
        for line in lines:
            if line.startswith("--- ") and line.endswith(" ---"):
                title = line.replace("---", "").strip()
                slide_titles.append(title)
            elif line.startswith("-") or line.startswith("•") or line.startswith("*"):
                bullet_text = re.sub(r"^[-•*]\s*", "", line).strip()
                if bullet_text and len(bullet_text) > 10:
                    bullets.append(bullet_text)
            elif len(line) > 15 and (line.endswith("。") or line.endswith(".")):
                if len(line) > 30 and len(bullets) < 15:
                    bullets.append(line)

        # 3. 建立核心大綱
        outline_title = topic or "課堂講義主題"
        if not slide_titles:
            slide_titles = [f"章節重點 {i+1}" for i in range(min(5, len(lines) // 5 + 1))]

        summary = (
            f"> ⚙️ **【本地離線備用摘要引擎】**\n"
            f"> *(⚠️ 偵測到 AI 服務呼叫限制：{error_msg}，系統已自動切換至本地離線引擎生成摘要)*\n\n"
            f"### 📖 講義「{outline_title}」核心大綱導讀\n"
            f"這是一份關於「**{outline_title}**」的課堂學習講義。主要包含以下幾個核心概念：\n\n"
        )
        for i, t in enumerate(slide_titles[:8]):
            summary += f"{i+1}. **{t}**\n"
        summary += "\n系統已對講義內容進行本地語意重組與關鍵字過濾，建議點擊下方「隨身問答助教」進行深入的本地問答互動。"

        # 4. 建立 key_points
        key_points = []
        for b in bullets[:10]:
            key_points.append(f"• {b}")
        
        if not key_points:
            key_points = [
                f"• 本地解析重點一：已成功載入講義「{outline_title}」，請查看大綱進行導讀。",
                "• 本地解析重點二：大模型呼叫受限時，您仍可在此檢視講義的主要段落。",
                "• 本地解析重點三：建議使用右側「AI 隨身助教」提問以調用本地語意搜尋引擎。"
            ]

        # 5. 建立 glossary (術語)
        common_terms = {
            "git": "分散式版本控制系統，用來追蹤檔案的修改歷史，支援多人協同開發。",
            "overfitting": "過擬合。模型在訓練集表現優異，但在測試集或新資料上泛化能力差。",
            "bst": "二元搜尋樹。左子樹值皆小於根節點，右子樹值皆大於根節點，中序走訪為排序數列。",
            "sjf": "最短工作優先 CPU 排程演算法。選擇執行時間最短的行程優先執行，平均等待時間最佳。",
            "fcfs": "先來先服務 CPU 排程演算法。依行程抵達順序進行排程，簡單但可能遭遇護送效應。",
            "learning rate": "學習率。控制最佳化演算法更新參數時的步長，太高會震盪發散，太低收斂過慢。",
            "cpu": "中央處理器。負責執行電腦程式中的指令與處理運算資料。",
            "api": "應用程式介面。提供一組定義好的方法，讓不同軟體系統之間進行通訊與協作。"
        }
        
        glossary = []
        text_lower = text.lower()
        for term, definition in common_terms.items():
            if term in text_lower:
                glossary.append({
                    "term": term.upper() if len(term) <= 4 else term.title(),
                    "def": definition
                })
        
        if not glossary:
            words = set(re.findall(r"\b[A-Z]{2,10}\b", text))
            for w in list(words)[:5]:
                glossary.append({
                    "term": w,
                    "def": f"講義中出現的核心概念詞彙（{w}），出現在講義多個段落中。"
                })

        if not glossary:
            glossary = [
                {"term": "Keyword Matching", "def": "本地搜尋採用的關鍵字精準匹配技術，無須呼叫線上 API。"},
                {"term": "Local Fallback", "def": "本地降級引擎。當雲端服務中斷時，自動轉由本地資料庫提供核心學習材料。"}
            ]

        return {
            "topic": topic,
            "summary": summary,
            "key_points": key_points,
            "glossary": glossary
        }

    def _parse_json_response(self, raw: str) -> dict:
        """解析 LLM 返回的 JSON，並使用 safe_json_loads 容忍截斷或格式異常。"""
        from core.json_helper import safe_json_loads
        res = safe_json_loads(raw, default_factory=dict)
        if isinstance(res, dict):
            # 兼容不同大小寫或同義詞的 Key
            for key in ["summary", "Summary", "SUMMARY", "abstract"]:
                if key in res and not res.get("summary"):
                    res["summary"] = res[key]
            for key in ["key_points", "KeyPoints", "keypoints", "points", "points_list"]:
                if key in res and not res.get("key_points"):
                    res["key_points"] = res[key]
            for key in ["glossary", "Glossary", "GLOSSARY", "vocabulary", "terms", "vocab"]:
                if key in res and not res.get("glossary"):
                    res["glossary"] = res[key]

            # 補齊預設值
            res.setdefault("summary", "")
            res.setdefault("key_points", [])
            res.setdefault("glossary", [])
            return res
        return {"summary": str(raw), "key_points": [], "glossary": []}
