# 產品需求文件（PRD）
## AI 課堂講義學習與複習規劃 Agent — 後端 / 系統整合模組

---

## 1. 文件基本資訊（Document Metadata）

| 欄位 | 內容 |
|------|------|
| **文件標題** | AI 課堂講義學習與複習規劃 Agent — 後端 / 系統整合 PRD |
| **版本號** | v1.0 |
| **負責人** | 黃柏豪（後端 / 系統整合） |
| **建立日期** | 2026-05-20 |
| **參考來源** | 生成式 AI 應用_第一組_期中報告.pdf、ChatGPT 設計討論紀錄 |
| **審核人員** | 組長、前端負責人（林瑞城）、Agent 核心邏輯負責人（沈靖恩）、RAG 負責人（楊沁霖） |

---

## 2. 背景與目標（Background & Objectives）

### 2.1 問題陳述

目前學生在課後自主複習講義時，面臨以下問題：

- 講義篇幅龐大，難以快速掌握重點
- 缺乏客觀評估自身理解程度的機制
- 不知道哪些概念需要優先複習
- 傳統學習工具無法根據個人弱點動態調整學習計畫

本系統不只是一個聊天機器人，而是**協助學生完成整個讀書流程的 Agent**，需要一個穩健的後端來支撐多 Agent 協作、資料持久化、以及完整的任務執行追蹤。

### 2.2 產品目標

後端 / 系統整合模組的核心目標：

1. 提供穩定的 **RESTful API**，作為前後端溝通橋樑
2. 實作**學習紀錄持久化**，追蹤每位學生的弱點與進度
3. 設計**任務觸發與流程控制機制**，協調多個 Agent 的執行順序
4. 建立**結構化 Log 系統**，完整記錄每次任務的工具呼叫鏈與執行結果

### 2.3 成功指標（KPI）

| 指標 | 目標值 |
|------|--------|
| API 平均回應時間 | < 3 秒（含 LLM 推論時間） |
| 任務完整執行率（8 步驟全部完成） | ≥ 95% |
| 學習狀態更新正確率 | ≥ 99% |
| Log 資料完整性 | 100%（每次任務皆有完整 Log） |
| 系統可用性（SLA） | ≥ 99% |

---

## 3. 目標用戶（Target Users）

### 3.1 用戶角色（Personas）

**主要用戶：大學生（學習者）**
- 需要複習課堂講義（PDF / PPT 格式）
- 希望快速掌握重點並透過測驗評估學習成效
- 期望系統能根據弱點提供個人化複習建議

**次要用戶：後端開發者（本組組員）**
- 需要清楚的 API 規格進行系統整合
- 需要 Log 資料進行除錯與系統監控

### 3.2 用戶痛點（Pain Points）

- 學生無法快速識別自己的弱項知識點
- 前端需要一致且穩定的 API 介面與資料格式
- 多 Agent 協作流程複雜，缺乏統一的流程管理機制
- 執行結果難以追溯，無法診斷 Agent 行為

### 3.3 使用情境（Use Cases）

**情境 A：學生上傳講義並請求整理重點**
> 學生上傳「自然語言處理第三章（TF-IDF）」講義，輸入「幫我整理重點，並出 3 題選擇題」，系統自動執行 RAG 查詢 → 摘要生成 → 題目生成流程。

**情境 B：學生作答後查看弱點分析**
> 學生完成選擇題後，系統批改並更新學習記憶，顯示弱點分析（如 TF-IDF 錯 2 次）並推薦個人化複習計畫。

**情境 C：開發者查閱系統 Log**
> 開發者透過 Log API 取得最近一次任務的完整執行鏈，用於除錯或效能分析。

---

## 4. 功能需求（Functional Requirements）

### 4.1 模組一：API 設計與串接（前後端溝通）

#### 使用者故事

- *As a 前端開發者, I want to 呼叫統一的 REST API 端點, so that 我可以觸發任意 Agent 任務並取得結構化回應。*
- *As a 學生, I want to 上傳 PDF/PPT 檔案並送出請求, so that 系統能解析我的講義並執行對應任務。*

#### 功能清單

| API 端點 | 方法 | 說明 |
|----------|------|------|
| `POST /api/upload` | POST | 接收使用者上傳的 PDF / PPT 講義檔案，回傳 `document_id` |
| `POST /api/task` | POST | 接收使用者的自然語言指令，觸發 Intent Agent 判斷並執行對應流程 |
| `GET /api/task/{task_id}` | GET | 查詢指定任務的執行狀態與結果 |
| `GET /api/student/{student_id}/state` | GET | 查詢特定學生的學習狀態（弱點、進度）|
| `POST /api/grade` | POST | 接收學生答題結果，執行批改與記憶更新流程 |
| `GET /api/log/{task_id}` | GET | 取得指定任務的完整 Agent Log |

#### Tool Function 規格

| 函式名稱 | 輸入 | 輸出 | 說明 |
|----------|------|------|------|
| `chunk_document(raw_text)` | 原始文字字串 | `paragraphs[]` | 將講義原文切分為段落 |
| `retrieve_content(keyword_or_question)` | 關鍵字或問題 | `relevant_paragraphs[]` | RAG 語意查詢相關段落 |
| `generate_summary(slide_paragraphs)` | 段落列表 | `summary: string` | 生成章節重點摘要 |
| `generate_quiz(topic, count)` | 主題、題數 | `questions[]` | 自動生成選擇題 / 是非題 |
| `grade_answer(question, student_answer)` | 題目、學生答案 | `{correctness, explanation}` | 批改並提供解析 |
| `update_learning_state(quiz_result)` | 批改結果 | `weak_points{}` | 更新學生弱點記憶 |
| `generate_study_plan(exam_date, weak_points)` | 考試日期、弱點 | `study_plan` | 生成個人化複習計畫 |
| `save_log(tool_call_logs)` | 工具呼叫紀錄 | `log_id` | 持久化本次任務 Log |

#### 驗收標準（Acceptance Criteria）

- [ ] `POST /api/upload` 成功後回傳 `document_id`，且能被後續 `/api/task` 引用
- [ ] `POST /api/task` 在收到請求後 < 500ms 內回傳 `task_id`（任務以非同步方式執行）
- [ ] 所有 API 回應格式統一為 JSON，包含 `status`、`data`、`error` 三個頂層欄位
- [ ] API 文件（Swagger / OpenAPI）完整描述所有端點與資料結構

---

### 4.2 模組二：使用者資料管理（學習紀錄）

#### 使用者故事

- *As a 學生, I want to 系統記住我每次答錯的題目, so that 我可以看到針對我弱點的複習建議。*
- *As a 系統, I want to 追蹤每位學生的學習狀態, so that 後續任務可以個人化調整。*

#### 資料結構定義

**學生學習狀態（Learning State）Schema：**

```json
{
  "student_id": "string（唯一識別碼）",
  "student_name": "string",
  "current_subject": "string（目前科目，如：自然語言處理）",
  "weak_topics": {
    "TF-IDF": 2,
    "PCFG 機率計算": 3,
    "FMM 中文斷詞": 1
  },
  "completed_chapters": ["Chapter 1", "Chapter 2"],
  "preferred_quiz_type": "multiple_choice | true_false | definition",
  "last_updated": "ISO 8601 timestamp"
}
```

**記憶更新規則：**
- 每次答錯一題，對應 `weak_topics` 計數 +1
- `completed_chapters` 在完成一章節所有題目後新增
- `last_updated` 在每次 `update_learning_state()` 執行後更新

#### 功能清單

1. **建立學生檔案**：首次進入系統時自動建立初始學習狀態
2. **更新弱點記憶**：每次批改後呼叫 `update_learning_state()` 更新 `weak_topics`
3. **查詢學習狀態**：前端可透過 `GET /api/student/{id}/state` 取得完整狀態
4. **持久化儲存**：學習狀態儲存至 SQLite 資料庫，確保跨 Session 保留

#### 驗收標準

- [ ] 學生首次使用系統時，自動建立初始 State，`weak_topics` 為空字典
- [ ] 批改完成後，`weak_topics` 中對應主題的計數正確遞增
- [ ] 學習狀態在系統重啟後仍能正確讀取（持久化驗證）
- [ ] 不同學生的資料相互隔離，不會發生資料交叉

---

### 4.3 模組三：系統流程控制（任務觸發）

#### 使用者故事

- *As a 系統, I want to 根據使用者指令自動判斷意圖, so that 正確的 Agent 工具鏈被按序執行。*
- *As a 學生, I want to 送出一句話請求, so that 系統自動完成摘要、出題、批改等完整流程。*

#### 完整任務執行流程（8 步驟）

```
Step 1: read_document()      → 讀取並解析上傳講義
Step 2: retrieve_content()   → RAG 查詢相關段落（TF-IDF / Vector Search）
Step 3: generate_summary()   → 生成重點摘要
Step 4: generate_quiz()      → 生成選擇題（使用者作答後繼續）
Step 5: grade_answer()       → 批改答案並提供解析
Step 6: update_learning_state() → 記錄錯誤概念至 Memory
Step 7: generate_study_plan()   → 生成個人化複習建議
Step 8: save_log()           → 持久化本次任務完整 Log
```

#### Intent 判斷規則

| 使用者意圖 | 關鍵詞範例 | 觸發流程 |
|-----------|-----------|---------|
| 重點整理（Summary） | 「整理重點」、「幫我摘要」 | Step 1 → 2 → 3 |
| 題目生成（Quiz） | 「出題」、「選擇題」 | Step 1 → 2 → 4 |
| 複習規劃（Study Plan） | 「複習計畫」、「下週考試」 | State 查詢 → Step 7 |
| 完整流程 | 「整理重點並出題」 | Step 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 |

#### 驗收標準

- [ ] Intent Agent 能正確識別至少 4 種任務意圖，分類準確率 ≥ 90%（以測試集驗證）
- [ ] 任務步驟按序執行，前一步驟失敗時系統回傳明確錯誤訊息並停止後續步驟
- [ ] 非同步任務狀態可透過 `GET /api/task/{task_id}` 追蹤（`pending / running / completed / failed`）
- [ ] 完整流程（8 步驟）平均執行時間 < 30 秒

---

### 4.4 模組四：Log 紀錄與儲存

#### 使用者故事

- *As a 系統, I want to 記錄每次任務的完整工具呼叫鏈, so that 開發者可以追蹤 Agent 行為並進行除錯。*
- *As a 前端, I want to 即時顯示 Agent 的執行步驟, so that 學生能看到系統正在做什麼。*

#### Log 資料結構

**任務 Log Schema：**

```json
{
  "log_id": "uuid",
  "task_id": "uuid",
  "student_id": "string",
  "timestamp": "2026-05-06T10:30:00+08:00",
  "user_input": "幫我複習 TF-IDF 並出 3 題選擇題",
  "intent": "review_and_quiz",
  "tools_called": [
    {
      "tool": "retrieve_content",
      "input": "TF-IDF",
      "output_summary": "查詢到 3 段相關內容",
      "status": "success",
      "duration_ms": 850
    },
    {
      "tool": "generate_summary",
      "input": "TF-IDF 段落 x3",
      "output_summary": "生成摘要完成",
      "status": "success",
      "duration_ms": 2300
    },
    {
      "tool": "generate_quiz",
      "input": "TF-IDF, count=3",
      "output_summary": "已產生 3 題選擇題",
      "status": "success",
      "duration_ms": 1500
    }
  ],
  "retrieved_topic": "TF-IDF",
  "final_result": "已產生摘要與 3 題選擇題",
  "total_duration_ms": 4650
}
```

**UI 顯示格式（Agent Terminal Log）：**

```
[Log] 判斷任務：複習 + 出題
[Log] 呼叫工具：retrieve_content() → 查詢主題：TF-IDF
[Log] 呼叫工具：generate_summary() → 生成摘要完成
[Log] 呼叫工具：generate_quiz() → 已產生 3 題選擇題
[Log] 任務完成：已產生摘要與 3 題選擇題
```

#### 功能清單

1. **即時 Log 串流**：透過 WebSocket 或 SSE 將執行步驟即時推送至前端
2. **任務 Log 持久化**：每次任務結束後，完整 Log 儲存至資料庫
3. **Log 查詢 API**：`GET /api/log/{task_id}` 取得完整 Log JSON
4. **Log 保留期限**：Log 資料保留至少 30 天

#### 驗收標準

- [ ] 每次任務執行後，`save_log()` 必須被呼叫，Log 完整性 = 100%
- [ ] Log 中的 `tools_called` 列表與實際工具呼叫順序一致
- [ ] 前端能透過 SSE / WebSocket 即時看到每個 Step 的執行狀態
- [ ] Log API 在任務完成後 1 秒內可供查詢

---

## 5. 非功能性需求（Non-Functional Requirements）

| 面向 | 需求描述 |
|------|---------|
| **效能** | API 端點（非 LLM）回應時間 < 200ms（P95）；含 LLM 推論的任務 < 30 秒 |
| **安全性** | API 需驗證 `student_id`；上傳檔案大小限制 ≤ 50MB；不儲存原始講義內容超過 Session |
| **可靠性** | 任意單一 Tool 呼叫失敗時，系統應回傳友善錯誤訊息，不崩潰；任務可重試 |
| **可擴展性** | 新增 Agent / Tool 時，不需修改核心流程控制器（Open/Closed Principle） |
| **相容性** | 後端 API 相容 RESTful 標準；前端使用 HTTP/1.1 或 HTTP/2 皆可存取 |

---

## 6. 系統與技術限制（Constraints & Dependencies）

### 6.1 技術架構

| 元件 | 技術選型 |
|------|---------|
| Web 框架 | FastAPI（Python） |
| 資料庫 | SQLite（學習狀態、Log 持久化） |
| 向量資料庫 | ChromaDB 或 FAISS（RAG 語意檢索） |
| LLM | Gemini API / OpenAI API |
| 文件解析 | pdfplumber（PDF）、python-pptx（PPT） |
| 即時通訊 | Server-Sent Events（SSE）或 WebSocket |

### 6.2 第三方服務依賴

- **Gemini API / OpenAI API**：摘要生成、題目生成、批改等 LLM 任務
- **Embedding Model**：文字向量化（支援中文）

### 6.3 與現有系統整合點

- **前端（林瑞城負責）**：透過 REST API 與 SSE 串接，統一 JSON 格式
- **Agent 核心邏輯（沈靖恩負責）**：後端提供 Tool Function 介面，Agent 呼叫執行
- **RAG 模組（楊沁霖負責）**：後端整合 `retrieve_content()` 查詢介面

---

## 7. 里程碑與時程（Timeline & Milestones）

| 階段 | 目標 | 預計完成 |
|------|------|---------|
| **Phase 0：規格確認** | 完成本 PRD、API Schema 定義、DB Schema 設計 | Week 1 |
| **Phase 1：MVP** | `POST /api/task`、`retrieve_content()`、`generate_summary()` 基本可用 | Week 2 |
| **Phase 2：核心功能** | 完整 8 步驟流程、`update_learning_state()`、Log 持久化 | Week 3 |
| **Phase 3：整合測試** | 前後端整合、Intent 準確率驗證、效能測試 | Week 4 |
| **Demo 準備** | 完整 Demo 情境演練（TF-IDF 複習流程） | Week 5 |

---

## 8. 範圍外（Out of Scope）

以下功能明確**不包含**在本版本（v1.0）後端模組範圍中：

- ❌ 多使用者同時登入的帳號系統（OAuth / JWT 認證）
- ❌ 雲端部署與負載均衡（Kubernetes / Docker Swarm）
- ❌ 多語言支援（目前僅支援繁體中文講義）
- ❌ 音訊 / 影片格式的講義解析
- ❌ 學生之間的協作學習功能
- ❌ 後台管理介面（Admin Dashboard）
- ❌ 自動化測試 CI/CD 流水線

---

## 9. 開放問題（Open Questions）

| # | 問題 | 負責確認 | 狀態 |
|---|------|---------|------|
| Q1 | LLM 使用 Gemini 或 OpenAI？需確認 API Key 授權 | 組長 | ⬜ 待確認 |
| Q2 | 向量資料庫選 ChromaDB 還是 FAISS？兩者的本地部署差異需評估 | 楊沁霖 | ⬜ 待確認 |
| Q3 | 前端與後端是否在同一個 Server 上？影響 CORS 設定與 SSE 穩定性 | 林瑞城 / 黃柏豪 | ⬜ 待確認 |
| Q4 | `student_id` 如何產生？是否由前端生成（UUID）或後端派發？ | 黃柏豪 | ⬜ 待確認 |
| Q5 | Log 資料是否需要對外展示？或只供開發者內部查閱？ | 組長 | ⬜ 待確認 |
| Q6 | 非同步任務是否需要任務隊列（如 Celery）？還是 FastAPI BackgroundTask 足夠？ | 黃柏豪 | ⬜ 待確認 |

---

*文件版本：v1.0 ｜ 最後更新：2026-05-20 ｜ 負責人：黃柏豪（後端 / 系統整合）*
