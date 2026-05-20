"""
@module llm_client
@description LLM API 統一封裝客戶端。透過 `provider` 參數切換 Gemini（開發）或
             GPT-4o（Demo），外層呼叫者無需感知底層 SDK 差異。
             包含指數退避重試機制（ADR-004）與結構化錯誤處理。
@dependencies google-generativeai, openai, tenacity, core.config
@author 黃柏豪（後端 / 系統整合）
@version 1.1.0
"""

from __future__ import annotations

import logging
from typing import Literal

import google.generativeai as genai
from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from core.config import get_settings

logger = logging.getLogger(__name__)

# ── 供應商型別別名 ────────────────────────────────────────────────────────────
LLMProvider = Literal["gemini", "openai"]


class LLMClient:
    """
    LLM API 統一封裝客戶端。

    支援 Gemini（開發環境）與 GPT-4o（Demo 展示），
    透過 `provider` 參數在執行時切換，其餘業務邏輯不受影響。

    Attributes:
        settings: 系統設定物件
        _openai_client: AsyncOpenAI 客戶端（懶初始化）

    Example:
        >>> client = LLMClient()
        >>> result = await client.complete("幫我摘要以下段落：...")
        >>> result_demo = await client.complete("...", provider="openai")
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._openai_client: AsyncOpenAI | None = None

        # 初始化 Gemini API Key
        genai.configure(api_key=self.settings.gemini_api_key)

    # ── 主要公開介面 ──────────────────────────────────────────────────────────

    async def complete(
        self,
        prompt: str,
        provider: LLMProvider | None = None,
        system_prompt: str = "你是一個專業的學習輔助 AI 助手，請用繁體中文回應。",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        呼叫 LLM 完成文字生成任務，內建指數退避重試。

        Args:
            prompt: 使用者提示詞
            provider: 指定 LLM 供應商（'gemini' | 'openai'），
                      None 則使用 settings.llm_provider 預設值
            system_prompt: 系統角色提示詞
            temperature: 生成溫度（0.0–1.0）
            max_tokens: 最大生成 Token 數

        Returns:
            str: LLM 生成的文字回應

        Raises:
            RuntimeError: 達到最大重試次數後仍失敗時拋出
        """
        resolved_provider: LLMProvider = provider or self.settings.llm_provider  # type: ignore
        logger.debug("[LLMClient] 使用供應商：%s", resolved_provider)

        try:
            if resolved_provider == "gemini":
                return await self._complete_gemini(prompt, system_prompt, temperature, max_tokens)
            elif resolved_provider == "openai":
                return await self._complete_openai(prompt, system_prompt, temperature, max_tokens)
            else:
                raise ValueError(f"不支援的 LLM 供應商：{resolved_provider}")
        except Exception as exc:
            logger.error("[LLMClient] LLM 呼叫失敗：%s", exc)
            raise

    async def embed(self, text: str) -> list[float]:
        """
        使用 Google text-embedding-004 將文字轉換為向量。

        Args:
            text: 要向量化的文字（建議 < 2048 tokens）

        Returns:
            list[float]: 768 維浮點向量

        Raises:
            RuntimeError: Embedding API 呼叫失敗時拋出
        """
        try:
            result = genai.embed_content(
                model=self.settings.embedding_model,
                content=text,
                task_type="retrieval_document",
            )
            return result["embedding"]
        except Exception as exc:
            logger.error("[LLMClient] Embedding 失敗：%s", exc)
            raise RuntimeError(f"Embedding API 呼叫失敗：{exc}") from exc

    async def embed_query(self, query: str) -> list[float]:
        """
        將查詢語句向量化（使用 retrieval_query task type）。

        Args:
            query: 使用者查詢字串

        Returns:
            list[float]: 768 維查詢向量
        """
        try:
            result = genai.embed_content(
                model=self.settings.embedding_model,
                content=query,
                task_type="retrieval_query",
            )
            return result["embedding"]
        except Exception as exc:
            logger.error("[LLMClient] Query Embedding 失敗：%s", exc)
            raise RuntimeError(f"Query Embedding 失敗：{exc}") from exc

    # ── 內部實作（Gemini）─────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _complete_gemini(
        self, prompt: str, system_prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """呼叫 Gemini API 完成文字生成（含重試）。"""
        model = genai.GenerativeModel(
            model_name=self.settings.gemini_model,
            system_instruction=system_prompt,
        )
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        return response.text

    # ── 內部實作（OpenAI）─────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _complete_openai(
        self, prompt: str, system_prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """呼叫 OpenAI API 完成文字生成（含重試）。"""
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(api_key=self.settings.openai_api_key)

        response = await self._openai_client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""


# ── 全域單例（避免重複初始化）────────────────────────────────────────────────

_llm_client_instance: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """
    取得 LLMClient 單例。

    Returns:
        LLMClient: 全域共用的 LLM 客戶端實例
    """
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance
