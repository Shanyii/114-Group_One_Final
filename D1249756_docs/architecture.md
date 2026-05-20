# 系統架構設計文件（Architecture Design Document）
## AI 課堂講義學習與複習規劃 Agent — 後端 / 系統整合模組

---

## 1. 文件基本資訊（Document Metadata）

| 欄位 | 內容 |
|------|------|
| **文件標題** | AI 課堂講義學習與複習規劃 Agent — 後端 / 系統整合 ADD |
| **版本號** | v1.1 |
| **負責人** | 黃柏豪（後端 / 系統整合） |
| **建立日期** | 2026-05-20 |
| **更新日期** | 2026-05-20（Q1–Q6 決策確認，升版 v1.1） |
| **審核人員** | 組長、林瑞城（前端）、沈靖恩（Agent）、楊沁霖（RAG） |
| **關聯文件** | [docs/prd.md](./prd.md) |

---

## 2. 架構概覽（Architecture Overview）

### 2.1 系統簡介

本系統是一個以 **FastAPI** 為核心的後端服務，支援 AI Agent 協作執行學習任務。學生上傳講義（PDF / PPT）後，系統透過多層 Agent 完成重點摘要、測驗生成、批改、弱點分析與複習規劃，並將所有執行歷程持久化儲存，以供前端即時呈現與事後查閱。

### 2.2 架構風格

採用 **分層架構（Layered Architecture）+ 事件驅動工具呼叫（Tool-Calling Agent Pattern）** 的混合設計：

- **表現層（API Layer）**：FastAPI 路由，處理 HTTP 請求與 SSE 推送
- **應用層（Application Layer）**：Intent 判斷、任務流程控制器（Orchestrator）
- **領域層（Domain Layer）**：各 Tool Function 業務邏輯（摘要、出題、批改…）
- **基礎設施層（Infrastructure Layer）**：SQLite、ChromaDB（持久化向量索引）、LLM API 呼叫（Gemini 開發 / GPT-4o Demo）

### 2.3 高階架構圖

```mermaid
graph TD
    subgraph Client["前端 / 使用者"]
        UI["Web UI（林瑞城）"]
        SSE_Client["SSE Log 接收器"]
    end

    subgraph Backend["後端服務（FastAPI）"]
        API["API Layer\nREST Endpoints"]
        Orch["Orchestrator\n任務流程控制器"]
        Intent["Intent Agent\n意圖判斷"]
        Tools["Tool Functions\n8 個工具函式"]
        LogSvc["Log Service\nsave_log / stream"]
        StateSvc["State Service\nLearning State CRUD"]
    end

    subgraph Storage["資料儲存"]
        SQLite[("SQLite\n學習狀態 / Log")]
        VectorDB[("ChromaDB\n講義向量索引（持久化）")]
        FileStore["File Store\n上傳講義暫存"]
    end

    subgraph External["外部服務"]
        LLM["Gemini API（開發）\nGPT-4o（Demo）"]
        Embed["text-embedding-004"]
    end

    UI -->|HTTP POST| API
    API --> Orch
    Orch --> Intent
    Intent --> Tools
    Tools --> LLM
    Tools --> VectorDB
    Orch --> LogSvc
    Orch --> StateSvc
    LogSvc --> SQLite
    StateSvc --> SQLite
    Tools --> FileStore
    Embed --> VectorDB
    LogSvc -->|SSE| SSE_Client
```

---

## 3. 技術選型（Technology Stack）

| 層次 | 技術選擇 | 選擇理由 |
|------|---------|---------|
| **後端框架** | FastAPI（Python 3.11+） | 原生支援 async/await、自動生成 OpenAPI 文件、SSE 支援佳、團隊熟悉 Python |
| **關聯式資料庫** | SQLite | 無需額外部署、適合單機 Demo 環境、Python 內建 sqlite3 支援 |
| **向量資料庫** | ChromaDB（跨 Session 持久化） | ✅ Q2 確認：採用 ChromaDB 本地持久化目錄，無需每次重建索引 |
| **LLM** | Gemini 2.0 Flash（開發） / GPT-4o（Demo） | ✅ Q1 確認：開發期用 Gemini 降低成本；Demo 展示切換 GPT-4o 提升效果 |
| **Embedding** | text-embedding-004（Google） | 與 Gemini 同生態系、支援中文、768 維向量 |
| **文件解析** | pdfplumber（PDF）/ python-pptx（PPT） | 中文 PDF 提取穩定；python-pptx 為 PPT 標準解析庫 |
| **即時通訊** | Server-Sent Events（SSE） | 單向推播足夠、比 WebSocket 輕量、FastAPI 原生支援；同機部署無跨域問題 |
| **ORM / DB 工具** | aiosqlite + SQLAlchemy Core | 支援 async 操作、不過度抽象 |
| **部署** | 本機 uvicorn（前後端同 Server，port 8000） | ✅ Q3 確認：前後端同機，靜態檔案由 FastAPI `StaticFiles` 掛載 |
| **任務執行** | FastAPI BackgroundTasks | ✅ Q6 確認：Demo 規模不需 Celery，BackgroundTask 足夠 |

---

## 4. 系統元件設計（Component Design）

### 4.1 元件關係圖

```mermaid
graph LR
    subgraph API["API Layer"]
        R_Upload["/api/upload"]
        R_Task["/api/task"]
        R_TaskGet["/api/task/{id}"]
        R_Student["/api/student/{id}/state"]
        R_Grade["/api/grade"]
        R_Log["/api/log/{id}"]
    end

    subgraph App["Application Layer"]
        Orch["Orchestrator"]
        Intent["IntentAgent"]
    end

    subgraph Domain["Domain / Tools"]
        DocParser["DocumentParser\nread_document + chunk_document"]
        RAGRetriever["RAGRetriever\nretrieve_content"]
        Summarizer["Summarizer\ngenerate_summary"]
        QuizGen["QuizGenerator\ngenerate_quiz"]
        Grader["Grader\ngrade_answer"]
        StateUpdater["StateUpdater\nupdate_learning_state"]
        PlanGen["PlanGenerator\ngenerate_study_plan"]
    end

    subgraph Infra["Infrastructure Layer"]
        LogRepo["LogRepository\nsave_log"]
        StateRepo["StateRepository"]
        VectorRepo["VectorRepository"]
        LLMClient["LLMClient"]
    end

    R_Upload --> Orch
    R_Task --> Orch
    R_Grade --> Orch
    Orch --> Intent
    Intent --> Orch
    Orch --> DocParser
    Orch --> RAGRetriever
    Orch --> Summarizer
    Orch --> QuizGen
    Orch --> Grader
    Orch --> StateUpdater
    Orch --> PlanGen
    Orch --> LogRepo
    RAGRetriever --> VectorRepo
    Summarizer --> LLMClient
    QuizGen --> LLMClient
    Grader --> LLMClient
    PlanGen --> LLMClient
    StateUpdater --> StateRepo
    LogRepo --> R_Log
    StateRepo --> R_Student
    Orch --> R_TaskGet
```

### 4.2 各元件說明

| 元件 | 職責 | 對外介面 | 依賴 |
|------|------|---------|------|
| **API Layer** | HTTP 路由、請求驗證、回應序列化 | REST Endpoints、SSE Stream | Orchestrator |
| **IntentAgent** | 解析自然語言指令，判斷任務類型（Summary / Quiz / Plan / Full） | `classify(text) -> IntentType` | LLMClient（可選，也可用關鍵字規則） |
| **Orchestrator** | 根據 Intent 決定執行哪些 Tool，管理步驟順序與錯誤處理 | `execute_task(intent, ctx) -> TaskResult` | 所有 Tool Functions |
| **DocumentParser** | 解析 PDF / PPT 為純文字，切分 Chunk | `parse(file) -> chunks[]` | pdfplumber, python-pptx |
| **RAGRetriever** | 接收查詢，從向量庫檢索相關段落（TF-IDF + 語意搜尋混合） | `retrieve(query) -> paragraphs[]` | VectorRepository |
| **Summarizer** | 呼叫 LLM 生成段落摘要 | `summarize(chunks[]) -> summary` | LLMClient |
| **QuizGenerator** | 根據主題呼叫 LLM 生成選擇題 | `generate(topic, n) -> questions[]` | LLMClient |
| **Grader** | 批改學生答案，提供解析 | `grade(q, answer) -> result` | LLMClient |
| **StateUpdater** | 更新學習狀態 Memory（弱點計數、章節完成） | `update(student_id, quiz_results)` | StateRepository |
| **PlanGenerator** | 根據弱點與考試日期生成複習計畫 | `plan(weak_topics, exam_date) -> plan` | LLMClient |
| **LogRepository** | 持久化 TaskLog 至 SQLite，提供 SSE 推播 | `save(log)`, `stream(task_id)` | SQLite, SSE |
| **StateRepository** | 學習狀態 CRUD | `get(student_id)`, `upsert(state)` | SQLite |
| **VectorRepository** | 管理 ChromaDB 向量索引（建立、持久化查詢） | `index(chunks[])`, `search(query)` | ChromaDB |
| **LLMClient** | 封裝 LLM API 呼叫，統一介面、處理重試；透過 `provider` 參數切換 Gemini / GPT-4o | `complete(prompt, provider) -> text` | Gemini API、OpenAI API |
| **DeveloperLogRepo** | 記錄完整工具呼叫技術細節（供開發者除錯） | `save_dev_log(task_log)` | SQLite |
| **WorkflowLogRepo** | 記錄使用者可讀的任務步驟摘要（供前端展示） | `save_workflow_log(steps[])`, `stream(task_id)` | SQLite, SSE |

---

## 5. 資料架構（Data Architecture）

### 5.1 ER 圖

```mermaid
erDiagram
    STUDENT {
        string student_id PK
        string student_name
        string current_subject
        json weak_topics
        json completed_chapters
        string preferred_quiz_type
        datetime last_updated
    }

    TASK {
        string task_id PK
        string student_id FK
        string document_id FK
        string intent
        string status
        datetime created_at
        datetime completed_at
    }

    TASK_LOG {
        string log_id PK
        string task_id FK
        string user_input
        string intent
        json tools_called
        string retrieved_topic
        string final_result
        int total_duration_ms
        datetime timestamp
    }

    DOCUMENT {
        string document_id PK
        string student_id FK
        string filename
        string file_type
        text raw_text
        datetime uploaded_at
    }

    QUIZ_RECORD {
        string record_id PK
        string task_id FK
        string student_id FK
        string topic
        string question
        string student_answer
        string correct_answer
        bool is_correct
        text explanation
        datetime answered_at
    }

    STUDENT ||--o{ TASK : "執行"
    STUDENT ||--o{ DOCUMENT : "上傳"
    STUDENT ||--o{ QUIZ_RECORD : "作答"
    TASK ||--|| TASK_LOG : "記錄"
    TASK ||--o{ QUIZ_RECORD : "包含"
    DOCUMENT ||--o{ TASK : "對應"
```

### 5.2 資料儲存策略

| 資料類型 | 儲存位置 | 保留期限 | 說明 |
|---------|---------|---------|------|
| 學生學習狀態 | SQLite `students` | 永久 | 跨 Session 保留弱點記憶 |
| Developer Log（技術詳情） | SQLite `dev_logs` | 30 天 | ✅ Q5：完整工具呼叫鏈、duration_ms、LLM prompt，供開發除錯 |
| Workflow Log（使用者摘要） | SQLite `workflow_logs` | 永久 | ✅ Q5：可讀步驟摘要，供前端 Agent Terminal 顯示 |
| 測驗作答紀錄 | SQLite `quiz_records` | 永久 | 用於弱點分析 |
| 講義向量索引 | ChromaDB（`./chroma_db/`） | 持久化 | ✅ Q2：跨 Session 保留，同一份講義無需重複建索引 |
| 上傳原始檔案 | 本機 `./uploads/` | Session 結束後清除 | 不長期儲存原始講義 |

### 5.3 資料流向

```mermaid
graph TD
    User["學生上傳 PDF"]
    Parse["DocumentParser\n解析 + Chunk"]
    Embed["Embedding Model\n向量化"]
    VDB["ChromaDB\n向量索引"]
    Query["RAGRetriever\n語意查詢"]
    LLM["LLM API\n摘要 / 出題 / 批改"]
    DB_State["SQLite: students\n學習狀態"]
    DB_Log["SQLite: task_logs\nLog 紀錄"]
    DB_Quiz["SQLite: quiz_records\n作答紀錄"]
    Frontend["前端展示"]

    User --> Parse
    Parse --> Embed
    Embed --> VDB
    Query --> VDB
    VDB --> LLM
    LLM --> Frontend
    LLM --> DB_Log
    LLM --> DB_Quiz
    DB_Quiz --> DB_State
    DB_State --> Frontend
    DB_Log --> Frontend
```

---

## 6. API 設計（API Design）

### 6.1 統一回應格式

所有 API 統一回傳以下結構：

```json
{
  "status": "success | error",
  "data": { ... },
  "error": {
    "code": "ERROR_CODE",
    "message": "錯誤說明"
  }
}
```

### 6.2 端點規格

| 方法 | 路徑 | 描述 | 請求格式 | 回應格式 |
|------|------|------|---------|---------|
| `POST` | `/api/upload` | 上傳講義檔案 | `multipart/form-data: file, student_id` | `{ data: { document_id } }` |
| `POST` | `/api/task` | 送出任務請求 | `{ student_id, document_id, instruction }` | `{ data: { task_id, status: "pending" } }` |
| `GET` | `/api/task/{task_id}` | 查詢任務狀態與結果 | — | `{ data: { status, result, steps_done } }` |
| `GET` | `/api/student/{student_id}/state` | 查詢學習狀態 | — | `{ data: { weak_topics, completed_chapters, ... } }` |
| `POST` | `/api/grade` | 提交作答結果 | `{ task_id, student_id, answers[] }` | `{ data: { grading_results[], weak_topics } }` |
| `GET` | `/api/log/{task_id}` | 取得任務 Log | — | `{ data: { log_id, tools_called[], ... } }` |
| `GET` | `/api/stream/{task_id}` | SSE 即時 Log 推播 | — | `text/event-stream` |

### 6.3 API 呼叫序列圖

```mermaid
sequenceDiagram
    participant FE as 前端
    participant API as FastAPI
    participant Orch as Orchestrator
    participant Tool as Tool Functions
    participant DB as SQLite

    FE->>API: POST /api/upload (file)
    API-->>FE: { document_id }

    FE->>API: POST /api/task { instruction, document_id }
    API-->>FE: { task_id, status: "pending" }

    FE->>API: GET /api/stream/{task_id} (SSE)
    API->>Orch: execute_task(intent, ctx)

    loop 每個 Tool 步驟
        Orch->>Tool: tool_function()
        Tool-->>Orch: result
        Orch-->>FE: SSE event: { step, tool, status }
    end

    Orch->>DB: save_log(task_log)
    API-->>FE: SSE event: { status: "completed", result }

    FE->>API: POST /api/grade { answers[] }
    API->>Orch: grade + update_state
    Orch->>DB: upsert student state
    API-->>FE: { grading_results, weak_topics }
```

### 6.4 版本控制策略

- 使用 URL 路徑版本號：`/api/v1/...`（v1.0 暫時省略，正式部署時補上）
- 版本升級時保留舊版至少一個版本週期

---

## 7. 安全性設計（Security Design）

| 面向 | 設計決策 |
|------|---------|
| **身份驗證** | ✅ Q4 確認：`student_id` 由**前端**首次訪問時以 `crypto.randomUUID()` 生成，持久化至 `localStorage`；後端直接接受，不額外派發 |
| **CORS** | ✅ Q3 確認：前後端同機部署（FastAPI 同時服務靜態前端），**無需設定 CORS**；若未來分離部署再加入 `CORSMiddleware` |
| **檔案上傳防護** | 限制 MIME Type（僅允許 `application/pdf`, `application/vnd.openxmlformats-officedocument.presentationml.presentation`）；檔案大小 ≤ 50MB |
| **Input Validation** | 所有請求參數透過 Pydantic Model 驗證，自動過濾非法輸入 |
| **Rate Limiting** | 對 `/api/task` 設定 IP 速率限制（每分鐘 ≤ 10 次），防止 LLM API 濫用 |
| **敏感資料** | Gemini API Key 與 OpenAI API Key 存於 `.env`，透過 `python-dotenv` 載入，不寫入版本控制 |

---

## 8. 部署架構（Deployment Architecture）

### 8.1 環境規劃

| 環境 | 說明 |
|------|------|
| **Development** | 本機 `uvicorn --reload`，LLM 使用 Gemini 2.0 Flash，ChromaDB 本地持久化 |
| **Demo（期末）** | 同機部署，LLM 切換 GPT-4o，前端靜態檔由 FastAPI `StaticFiles` 掛載於 `/` |
| **Production（Out of Scope）** | Docker 容器化部署，超出本版本範圍 |

### 8.2 本機部署架構圖

> ✅ Q3 確認：前後端同機，無跨域問題，前端靜態資源由 FastAPI 直接服務。

```mermaid
graph TD
    subgraph LocalMachine["本機（開發 / Demo 環境，port 8000）"]
        Browser["瀏覽器\n前端 HTML / JS\n（FastAPI StaticFiles）"]
        Uvicorn["uvicorn\nFastAPI App\n:8000"]
        SQLiteFile["learning.db\nSQLite 檔案"]
        ChromaDir["./chroma_db/\nChromaDB 持久化目錄"]
        UploadDir["./uploads/\n暫存講義"]
    end

    subgraph Cloud["外部雲端服務"]
        GeminiAPI["Gemini 2.0 Flash\n（開發）"]
        GPT4oAPI["GPT-4o\n（Demo）"]
        EmbedAPI["text-embedding-004"]
    end

    Browser -->|同源 HTTP / SSE| Uvicorn
    Uvicorn --> SQLiteFile
    Uvicorn --> ChromaDir
    Uvicorn --> UploadDir
    Uvicorn -->|HTTPS| GeminiAPI
    Uvicorn -->|HTTPS| GPT4oAPI
    Uvicorn -->|HTTPS| EmbedAPI
```

### 8.3 目錄結構

```
backend/
├── main.py                  # FastAPI app 入口
├── routers/
│   ├── upload.py            # /api/upload
│   ├── task.py              # /api/task, /api/task/{id}
│   ├── grade.py             # /api/grade
│   ├── student.py           # /api/student/{id}/state
│   └── log.py               # /api/log/{id}, /api/stream/{id}
├── services/
│   ├── orchestrator.py      # 任務流程控制器
│   ├── intent_agent.py      # Intent 判斷
│   └── log_service.py       # Log 管理與 SSE 推播
├── tools/
│   ├── document_parser.py   # read_document, chunk_document
│   ├── rag_retriever.py     # retrieve_content
│   ├── summarizer.py        # generate_summary
│   ├── quiz_generator.py    # generate_quiz
│   ├── grader.py            # grade_answer
│   ├── state_updater.py     # update_learning_state
│   └── plan_generator.py    # generate_study_plan
├── repositories/
│   ├── state_repo.py        # StudentState CRUD
│   ├── log_repo.py          # TaskLog CRUD
│   └── vector_repo.py       # ChromaDB 操作
├── models/
│   ├── schemas.py           # Pydantic 請求 / 回應 Schema
│   └── db_models.py         # SQLAlchemy Table 定義
├── core/
│   ├── llm_client.py        # LLM API 封裝
│   └── config.py            # 環境變數載入
├── learning.db              # SQLite 資料庫（gitignore）
├── chroma_db/               # ChromaDB 向量索引（gitignore）
└── .env                     # API Keys（gitignore）
```

---

## 9. 非功能性考量（Non-Functional Considerations）

| 面向 | 設計決策 |
|------|---------|
| **效能** | 非 LLM 端點 < 200ms（P95）；LLM 任務非同步執行；向量查詢 Top-K 設為 3-5 篇，避免 Context 過長 |
| **可靠性** | LLM 呼叫加入最多 3 次指數退避重試；Tool 失敗時 Orchestrator 捕獲例外，回傳 `status: failed` 並記錄 Log |
| **可觀測性** | 每個 Tool 呼叫記錄執行時間（`duration_ms`）至 TaskLog；FastAPI 內建 `/docs` Swagger UI；結構化 JSON Log 輸出至 stdout |
| **可維護性** | Tool Functions 遵守單一職責原則，可獨立測試；LLMClient 封裝所有 LLM 差異，切換供應商只需改 Client |
| **可測試性** | LLMClient 設計為可 Mock；Repository 層可用 in-memory SQLite 替換；Tool Function 接受純 Python 物件輸入，便於單元測試 |

---

## 10. 架構決策紀錄（Architecture Decision Records）

### ADR-001：選擇 SQLite 作為主要資料庫

- **背景**：需要持久化學習狀態與 Log，但系統為 Demo 規模，不預期高並發。
- **決策**：使用 SQLite（`aiosqlite` 支援 async）。
- **理由**：無需額外部署、Python 內建支援、適合單機 Demo；後續若需擴展可遷移至 PostgreSQL。
- **後果**：並發寫入能力受限（SQLite 鎖定機制），但 Demo 場景下單用戶操作，影響可忽略。

---

### ADR-002：Log 即時推播採用 SSE 而非 WebSocket

- **背景**：前端需要即時看到 Agent 每個步驟的執行狀態。
- **決策**：使用 Server-Sent Events（SSE）。
- **理由**：SSE 為單向推播，符合「後端主動推送 Log 事件」的場景；比 WebSocket 輕量，FastAPI 透過 `StreamingResponse` 原生支援，無需額外套件。
- **後果**：若未來需要雙向即時通訊（如學生即時互動），需升級至 WebSocket。

---

### ADR-003：向量資料庫確認採用 ChromaDB 跨 Session 持久化

- **背景**：RAG 模組需要向量檢索，且每次重建索引耗時（含 Embedding 呼叫費用）。
- **決策**：✅ Q2 確認採用 ChromaDB，啟用本地持久化目錄（`./chroma_db/`），同一份講義上傳後無需重建。
- **理由**：ChromaDB 持久化模式設定簡單（`PersistentClient`）；避免每次 Demo 重複 Embedding 呼叫；FAISS 不具備原生持久化 API，需自行序列化。
- **後果**：`./chroma_db/` 目錄須納入 `.gitignore`，不隨程式碼提交。

---

### ADR-004：任務非同步執行採用 FastAPI BackgroundTask

- **背景**：LLM 任務執行時間可能長達 30 秒，不可阻塞 HTTP 回應。
- **決策**：✅ Q6 確認使用 `FastAPI.BackgroundTasks` 執行任務，立即回傳 `task_id`，前端透過 SSE 追蹤進度。
- **理由**：Demo 規模不需引入 Celery + Redis 等重型任務隊列；BackgroundTask 足以支撐單用戶並發需求。
- **後果**：進程重啟會中斷進行中的背景任務；正式環境應遷移至 Celery。

---

### ADR-005：Log 系統採用雙層設計（Developer Log + User Workflow Log）

- **背景**：Q5 確認 Log 需同時服務兩種受眾：開發者（除錯用）與學生（理解 Agent 流程用）。
- **決策**：分離為兩張資料表與兩個 Repository：
  - `dev_logs`：記錄完整技術細節（LLM prompt、duration_ms、向量查詢分數）
  - `workflow_logs`：記錄使用者可讀步驟摘要（`[Step 1] 讀取講義完成`），透過 SSE 即時推送至前端
- **理由**：混合儲存會導致前端過濾邏輯複雜；分層後各層關注點清晰，前端直接消費 `workflow_logs` 不需二次處理。
- **後果**：每次任務需寫入兩份 Log，略增 I/O；但 SQLite 寫入速度足以應付此場景。

---

## 11. 決策確認紀錄（Resolved Decisions）

> 所有原 Open Questions 已於 2026-05-20 確認，無待決事項。

| # | 問題 | 確認決策 | 狀態 |
|---|------|---------|------|
| Q1 | LLM 選型 | **Gemini 2.0 Flash（開發）＋ GPT-4o（Demo）**；`LLMClient` 以 `provider` 參數切換 | ✅ 已確認 |
| Q2 | 向量索引持久化策略 | **ChromaDB 跨 Session 持久化**；`PersistentClient` 模式 | ✅ 已確認 |
| Q3 | 前後端部署關係 | **同一台 Server**；FastAPI `StaticFiles` 掛載前端，無需 CORS | ✅ 已確認 |
| Q4 | `student_id` 產生方式 | **前端以 `crypto.randomUUID()` 生成**，存入 `localStorage` | ✅ 已確認 |
| Q5 | Log 呈現策略 | **雙層 Log**：`dev_logs`（技術詳情）＋ `workflow_logs`（使用者摘要 / SSE） | ✅ 已確認 |
| Q6 | 非同步任務機制 | **FastAPI `BackgroundTasks`**；Demo 規模無需 Celery | ✅ 已確認 |

---

*文件版本：v1.1 ｜ 最後更新：2026-05-20（Q1–Q6 決策確認）｜ 負責人：黃柏豪（後端 / 系統整合）*
*關聯 PRD：[docs/prd.md](./prd.md)*
