"""
@module orchestrator
@description 任務流程控制器（Orchestrator）。根據 IntentAgent 判斷的意圖，
             按序呼叫對應的 Tool Functions，並在每個步驟後推播 Workflow Log。
             使用 FastAPI BackgroundTasks 非同步執行（ADR-004）。

完整 8 步驟流程：
  Step 1: read_document()         → 讀取並解析上傳講義
  Step 2: retrieve_content()      → RAG 查詢相關段落
  Step 3: generate_summary()      → 生成重點摘要
  Step 4: generate_quiz()         → 生成選擇題
  Step 5: grade_answer()          → 批改（由 /api/grade 端點觸發）
  Step 6: update_learning_state() → 記錄弱點至 Memory
  Step 7: generate_study_plan()   → 生成個人化複習建議
  Step 8: save_log()              → 持久化本次任務 Log

@dependencies services.intent_agent, tools.*, repositories.*, core.llm_client
@author 黃柏豪（後端 / 系統整合）
@version 1.1.0
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Literal

import aiosqlite

from core.config import get_settings
from core.llm_client import get_llm_client
from repositories.log_repo import LogRepository
from repositories.state_repo import StateRepository
from repositories.vector_repo import get_vector_repo
from services.intent_agent import IntentAgent, IntentType
from tools.document_parser import DocumentParser
from tools.rag_retriever import RAGRetriever
from tools.summarizer import Summarizer
from tools.quiz_generator import QuizGenerator

logger = logging.getLogger(__name__)

# ── Intent → 執行步驟對應表 ───────────────────────────────────────────────────
INTENT_STEPS: dict[IntentType, list[int]] = {
    "summary": [1, 2, 3, 8],
    "quiz": [1, 2, 4, 8],
    "plan": [7, 8],          # 複習計畫直接讀取 State，不需解析文件
    "full": [1, 2, 3, 4, 8],  # 步驟 5-7 由 /api/grade 觸發
}

STEP_NAMES = {
    1: ("read_document",         "[Parser Agent] 啟動 DocumentParser -> 讀取並解析講義"),
    2: ("retrieve_content",      "[RAG Agent] 啟動 RAGRetriever -> 檢索相關語意段落"),
    3: ("generate_summary",      "[Summary Agent] 啟動 Summarizer -> 濃縮並生成多層次重點大綱"),
    4: ("generate_quiz",         "[Quiz Agent] 啟動 QuizGenerator -> 設計觀念測驗題目"),
    5: ("grade_answer",          "[Grader Agent] 啟動 Grader -> 進行學生答案批改與解析"),
    6: ("update_learning_state", "[Memory Agent] 啟動 StateRepository -> 更新學習記憶"),
    7: ("generate_study_plan",   "[Plan Agent] 啟動 PlanGenerator -> 規劃個人化複習計畫"),
    8: ("save_log",              "[System Agent] 啟動 LogRepository -> 儲存雙層技術日誌"),
}


class Orchestrator:
    """
    任務流程控制器。

    由 FastAPI BackgroundTasks 呼叫，非同步執行完整 Agent 任務流程。
    每個步驟完成後透過 LogRepository 推播 SSE 事件至前端。
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_client = get_llm_client()
        self.log_repo = LogRepository()
        self.state_repo = StateRepository()
        self.vector_repo = get_vector_repo()
        self.intent_agent = IntentAgent()
        self.document_parser = DocumentParser()
        self.rag_retriever = RAGRetriever(self.vector_repo, self.llm_client)
        self.summarizer = Summarizer(self.llm_client)
        self.quiz_generator = QuizGenerator(self.llm_client)

    async def execute_task(
        self,
        task_id: str,
        student_id: str,
        document_id: str,
        instruction: str,
        llm_provider: str | None = None,
    ) -> None:
        """
        執行完整 Agent 任務流程（由 BackgroundTasks 呼叫）。

        Args:
            task_id: 任務 UUID
            student_id: 學生 UUID
            document_id: 文件 UUID
            instruction: 使用者自然語言指令
            llm_provider: 指定 LLM 供應商（None 則用預設值）
        """
        start_time = time.time()
        tools_called: list[dict] = []
        result_summary = ""
        intent = "unknown"

        try:
            # 更新任務狀態為 running
            await self._update_task_status(task_id, "running")

            # ── Step 0：Intent 判斷 ───────────────────────────────────────────
            intent = await self.intent_agent.classify(instruction)
            logger.info("[Orchestrator] task_id=%s, intent=%s", task_id, intent)
            await self._update_task_intent(task_id, intent)

            await self.log_repo.append_workflow_step(
                task_id, 0, "intent_classify",
                f"[Intent Agent] 啟動 IntentAgent -> 判斷使用者任務意圖為：{intent}", "success"
            )

            steps = INTENT_STEPS.get(intent, [1, 2, 3, 8])
            context: dict = {"instruction": instruction, "llm_provider": llm_provider}

            # ── 依序執行各步驟 ────────────────────────────────────────────────
            for step_num in steps:
                step_name, step_display_base = STEP_NAMES[step_num]
                step_start = time.time()
                step_status = "success"

                await self.log_repo.append_workflow_step(
                    task_id, step_num, step_name,
                    f"{step_display_base}...", "running"
                )

                try:
                    output = await self._execute_step(
                        step_num, task_id, student_id, document_id, context, llm_provider
                    )
                    context[step_name] = output

                    # Step 4 完成後，自動將生成的題目存入 DB
                    if step_num == 4 and isinstance(output, list) and output:
                        await self._save_generated_quizzes(task_id, output)

                    duration_ms = int((time.time() - step_start) * 1000)
                    tools_called.append({
                        "tool": step_name,
                        "input_summary": str(instruction)[:100],
                        "output_summary": str(output)[:200] if output else "完成",
                        "status": "success",
                        "duration_ms": duration_ms,
                    })

                    await self.log_repo.append_workflow_step(
                        task_id, step_num, step_name,
                        f"{step_display_base}完成", "success"
                    )

                except Exception as step_exc:
                    logger.error("[Orchestrator] Step %d 失敗：%s", step_num, step_exc)
                    step_status = "failed"
                    duration_ms = int((time.time() - step_start) * 1000)
                    tools_called.append({
                        "tool": step_name,
                        "input_summary": str(instruction)[:100],
                        "output_summary": f"錯誤：{step_exc}",
                        "status": "failed",
                        "duration_ms": duration_ms,
                    })
                    await self.log_repo.append_workflow_step(
                        task_id, step_num, step_name,
                        f"{step_display_base}失敗：{step_exc}", "failed"
                    )
                    # 步驟失敗時停止後續執行
                    await self._update_task_status(task_id, "failed", f"步驟 {step_num} 失敗：{step_exc}")
                    raise

            # ── Step 8：儲存 Dev Log ──────────────────────────────────────────
            total_ms = int((time.time() - start_time) * 1000)
            
            # 收集完整的生成結果
            import json
            full_result = {
                "summary": context.get("generate_summary"),
                "quiz": context.get("generate_quiz"),
                "plan": context.get("generate_study_plan")
            }
            full_result_str = json.dumps(full_result, ensure_ascii=False)

            result_summary = context.get("generate_summary") or context.get("generate_quiz") or "任務完成"
            if isinstance(result_summary, (list, dict)):
                result_summary = str(result_summary)[:300]
            elif isinstance(result_summary, str):
                result_summary = result_summary[:300]

            await self.log_repo.save_dev_log(
                task_id=task_id,
                user_input=instruction,
                intent=intent,
                tools_called=tools_called,
                retrieved_topic=context.get("topic"),
                final_result=full_result_str,
                total_duration_ms=total_ms,
            )

            await self._update_task_status(task_id, "completed", result_summary)
            await self.log_repo.append_workflow_step(
                task_id, 8, "save_log",
                f"[Step 8] 任務完成，耗時 {total_ms}ms", "success"
            )

        except Exception as exc:
            logger.error("[Orchestrator] 任務失敗 task_id=%s：%s", task_id, exc)
            await self._update_task_status(task_id, "failed", f"任務執行異常：{exc}")

    # ── 步驟分發器 ────────────────────────────────────────────────────────────

    async def _execute_step(
        self,
        step_num: int,
        task_id: str,
        student_id: str,
        document_id: str,
        context: dict,
        llm_provider: str | None,
    ) -> object:
        """根據步驟號碼呼叫對應的 Tool Function。"""
        if step_num == 1:
            return await self.document_parser.read_from_db(document_id)
        elif step_num == 2:
            query = context.get("instruction", "")
            return await self.rag_retriever.retrieve(query, document_id)
        elif step_num == 3:
            raw_text = context.get("read_document", "")
            doc_text = raw_text[:15000] if raw_text else "無講義內容"
            return await self.summarizer.summarize_text(doc_text, topic=context.get("topic", ""), provider=llm_provider)
        elif step_num == 4:
            raw_text = context.get("read_document", "")
            doc_text = raw_text[:15000] if raw_text else "無講義內容"
            topic = context.get("topic", "講義內容")
            return await self.quiz_generator.generate_text(doc_text, topic, provider=llm_provider)
        elif step_num == 7:
            state = await self.state_repo.get_or_create(student_id)
            from tools.plan_generator import PlanGenerator
            planner = PlanGenerator(self.llm_client)
            return await planner.generate(state.get("weak_topics", {}), provider=llm_provider)
        elif step_num == 8:
            return "save_log_done"
        return None

    def _get_passages_with_fallback(self, context: dict) -> list[dict]:
        """
        取得 RAG 段落，若為空則用 Step 1 讀取的原文作為 fallback。
        這確保即使向量索引為空，Summarizer 與 QuizGenerator 仍有內容可處理。
        """
        passages = context.get("retrieve_content", [])
        if passages:
            return passages

        # Fallback: 使用 read_document 的原始文字，切成一個虛擬段落
        raw_text = context.get("read_document", "")
        if raw_text:
            # 取前 3000 字以避免 Token 爆量
            truncated = raw_text[:3000]
            logger.info("[Orchestrator] RAG 檢索為空，改用原文 fallback（%d 字）", len(truncated))
            return [{"text": truncated, "score": 1.0, "chunk_index": 0, "document_id": ""}]

        return []

    # ── DB 輔助方法 ────────────────────────────────────────────────────────────

    async def _update_task_status(
        self, task_id: str, status: str, result_summary: str | None = None
    ) -> None:
        """更新任務執行狀態。"""
        async with aiosqlite.connect(self.settings.database_url) as db:
            if status in ("completed", "failed"):
                await db.execute(
                    "UPDATE tasks SET status=?, result_summary=?, completed_at=? WHERE task_id=?",
                    (status, result_summary, datetime.utcnow().isoformat(), task_id),
                )
            else:
                await db.execute(
                    "UPDATE tasks SET status=? WHERE task_id=?",
                    (status, task_id),
                )
            await db.commit()

    async def _update_task_intent(self, task_id: str, intent: str) -> None:
        """更新任務 Intent 欄位。"""
        async with aiosqlite.connect(self.settings.database_url) as db:
            await db.execute(
                "UPDATE tasks SET intent=? WHERE task_id=?", (intent, task_id)
            )
            await db.commit()

    async def _save_generated_quizzes(self, task_id: str, quizzes: list[dict]) -> None:
        """
        將 Agent 生成的題目存入 generated_quizzes 資料表。
        批改時直接從這裡撈正確答案，前端不需要傳 correct_answer。
        """
        try:
            async with aiosqlite.connect(self.settings.database_url) as db:
                for i, q in enumerate(quizzes):
                    quiz_id = str(uuid.uuid4())
                    await db.execute(
                        """
                        INSERT INTO generated_quizzes
                        (quiz_id, task_id, quiz_index, topic, question, options,
                         correct_answer, explanation, question_type, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            quiz_id, task_id, i,
                            q.get("topic", ""),
                            q.get("question", ""),
                            json.dumps(q.get("options", []), ensure_ascii=False),
                            q.get("correct_answer", ""),
                            q.get("explanation", ""),
                            q.get("question_type", "multiple_choice"),
                            datetime.utcnow().isoformat(),
                        ),
                    )
                await db.commit()
            logger.info("[Orchestrator] 已儲存 %d 題生成題目至 DB (task_id=%s)", len(quizzes), task_id)
        except Exception as exc:
            logger.error("[Orchestrator] 儲存生成題目失敗：%s", exc)
