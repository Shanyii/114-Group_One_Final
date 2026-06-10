// app.js - StudyAgent AI 核心邏輯與資料庫

// 講義資料庫
const COURSE_PRESETS = {
    1: {
        title: "機器學習與深度學習基礎",
        description: "涵蓋監督式與非監督式學習、損失函數、梯度下降最佳化、過擬合與正規化 (L1/L2) 機制。",
        agentLogs: [
            { text: "[Parser Agent] 正在解析上傳檔案：ML_Lecture_01.pdf...", type: "info", delay: 300 },
            { text: "[Parser Agent] 成功讀取 3 頁簡報內容，偵測到主要語言：繁體中文。", type: "success", delay: 300 },
            { text: "[Intent Agent] 提取簡報核心知識域：監督式學習、最佳化演算法、泛化問題。", type: "info", delay: 400 },
            { text: "[RAG Agent] 檢索機器學習詞彙知識庫，對照專有名詞定義中...", type: "info", delay: 400 },
            { text: "[Summary Agent] 正在萃取重點... 建立投影片重點樹狀結構中...", type: "info", delay: 500 },
            { text: "[Summary Agent] 重點分析完成：已生成『損失函數』與『過擬合防護』兩大結構。", type: "success", delay: 400 },
            { text: "[Quiz Agent] 開始設計測驗題型。目標：檢驗學生對梯度方向、L2懲罰項的觀念偏誤...", type: "info", delay: 500 },
            { text: "[Quiz Agent] 生成 5 題多維度評估測驗：2 題單選、2 題複選、1 題是非題。", type: "success", delay: 400 },
            { text: "[Memory Agent] 建立學生的學習基準線 (Baseline)。", type: "info", delay: 300 },
            { text: "[Critic Agent] 檢查生成內容一致性... 通過自我檢驗檢測！", type: "success", delay: 400 },
            { text: "[Response Agent] 重點與測驗模組包裝完成，正在載入 Dashboard 介面...", type: "info", delay: 300 }
        ],
        summaries: [
            {
                slideNum: "Slide 1",
                title: "機器學習分類與監督式學習",
                desc: "機器學習主要分為監督式學習（有標籤資料）、非監督式學習（無標籤資料）與強化學習（透過獎勵機制與環境互動學習）。",
                bullets: [
                    "監督式學習核心任務：迴歸 (Regression, 預測連續數值) 與分類 (Classification, 預測離散類別)。",
                    "資料劃分：必須將資料集切分為訓練集 (Training Set) 調整權重，與測試集 (Testing Set) 評估泛化能力。"
                ]
            },
            {
                slideNum: "Slide 2",
                title: "最佳化核心：損失函數與梯度下降",
                desc: "損失函數 (Loss Function) 衡量模型預測與真實值之間的差距。梯度下降 (Gradient Descent) 則是藉由尋找斜率最陡峭的相反方向來更新權重，以極小化損失函數。",
                bullets: [
                    "學習率 (Learning Rate, α)：控制每一次參數更新的步伐大小。過大會導致無法收斂、震盪，過小則收斂速度極慢。",
                    "局部最小值與鞍點 (Local Minima & Saddle Points)：高維空間中優化演算法常遇到的挑戰。"
                ]
            },
            {
                slideNum: "Slide 3",
                title: "過擬合與正規化 (Overfitting & Regularization)",
                desc: "過擬合 (Overfitting) 指模型在訓練集表現極佳，但在未曾見過的測試集上表現極差（泛化能力弱）。正規化則是透過在損失函數中加入懲罰項來抑制權重過大。",
                bullets: [
                    "L1 正規化 (Lasso)：加入權重絕對值之和。會產生稀疏矩陣（將不重要的參數歸零），具有特徵選取功能。",
                    "L2 正規化 (Ridge)：加入權重平方和。使參數數值均勻縮小，促使模型平滑，防止單一特徵權重過大。"
                ]
            }
        ],
        glossary: [
            { term: "梯度下降 (Gradient Descent)", def: "沿著損失函數斜率最陡的相反方向更新參數，以尋找全局或局部最小值的最佳化演算法。" },
            { term: "過擬合 (Overfitting)", def: "模型過度擬合訓練資料中的雜訊，導致在新資料（測試集）上的預測能力（泛化能力）下降。" },
            { term: "L2 正規化 (L2 Regularization)", def: "又稱 Ridge 懲罰項，藉由在 Loss Function 加入權重的平方和，來限制模型複雜度並讓權重平滑縮小。" },
            { term: "學習率 (Learning Rate)", def: "決定最佳化演算法在搜尋參數空間時，每次迭代更新跨出步伐大小的超參數。" }
        ],
        quiz: [
            {
                id: 1,
                type: "single",
                question: "當模型發生過擬合 (Overfitting) 時，以下哪種策略通常「無法」改善這個問題？",
                options: [
                    "增加訓練資料的樣本數",
                    "使用 L2 正規化 (Ridge) 來懲罰過大的權重",
                    "大幅增加模型的層數與神經元數量以提高模型複雜度",
                    "實施 Early Stopping (提早停止訓練) 機制"
                ],
                correctIndex: 2,
                explanation: "增加模型層數與神經元數量會增加模型複雜度，這反而會讓模型更容易去記住訓練資料的細訊與雜訊，從而加劇過擬合。正確的防範方式應是降低模型複雜度、增加資料或施加正規化。"
            },
            {
                id: 2,
                type: "single",
                question: "關於梯度下降法中的學習率 (Learning Rate, α)，下列敘述何者正確？",
                options: [
                    "學習率設定得越小，模型收斂的速度就越快，且能保證找到全域最佳解",
                    "學習率設定過大可能導致損失函數 (Loss) 震盪甚至發散，無法收斂",
                    "學習率是模型在訓練過程中，透過梯度自動計算並動態調整的內部參數，無須人為設定",
                    "學習率只影響模型初始權重的隨機分配，不影響權重更新的步伐"
                ],
                correctIndex: 1,
                explanation: "學習率控制參數更新的步長。若 α 太大，步子跨得太大，容易越過最低點並造成 Loss 震盪甚至發散；α 太小則收斂極慢。學習率屬於「超參數」，非模型內部自學參數。"
            },
            {
                id: 3,
                type: "true_false",
                question: "L1 正規化 (Lasso) 與 L2 正規化 (Ridge) 都會使不重要的特徵權重完全歸零，進而達到自動選取特徵的效果。",
                options: [
                    "正確",
                    "錯誤"
                ],
                correctIndex: 1,
                explanation: "這是錯誤的。L1 正規化 (Lasso) 的幾何特性會傾向於使不重要特徵的權重精確歸零（產生稀疏矩陣）；而 L2 正規化 (Ridge) 只會將權重壓縮至接近零，但絕少能精確等於零。因此只有 L1 具備明確的自動特徵選取效果。"
            },
            {
                id: 4,
                type: "multiple",
                question: "【複選題】下列哪些屬於「監督式學習 (Supervised Learning)」的典型應用場景？（請選出所有正確選項）",
                options: [
                    "根據房屋坪數、地段預測房價 (Regression)",
                    "將電商網站的客戶依購買行為自動分成三個不同的群體 (Clustering)",
                    "分析醫學影像，判斷腫瘤是良性還是惡性 (Classification)",
                    "垃圾郵件過濾系統，判別信件是否為垃圾信 (Classification)"
                ],
                correctIndex: [0, 2, 3],
                explanation: "監督式學習的資料必須包含「標籤 (Label)」。房價預測（目標是連續值標籤）為迴歸，腫瘤良惡性判斷與垃圾郵件分類（目標是類別標籤）為分類，皆屬監督式學習。而將客戶分群（無預設標籤）屬於「非監督式學習」中的分群法 (Clustering)。"
            },
            {
                id: 5,
                type: "single",
                question: "在損失函數中加入 L2 正規化懲罰項時，若正規化係數 λ (Lambda) 設得極大（趨近於無限大），會導致模型發生什麼現象？",
                options: [
                    "模型會完全契合訓練資料，導致嚴重的過擬合 (Overfitting)",
                    "模型的所有權重都會被強烈壓抑趨近於 0，導致欠擬合 (Underfitting)",
                    "模型的訓練速度會提升數倍，且必定能收斂到 Loss = 0",
                    "模型的泛化誤差會降到最低，在測試集上達到 100% 準確率"
                ],
                correctIndex: 1,
                explanation: "L2 正規化目標是最小化 (Original Loss + λ * Σ w^2)。如果 λ 趨近於無限大，為了使整體 Loss 最小，優化過程會被迫將所有權重 w 強壓至極接近 0。這使得模型失去從特徵中學習的能力，退化成極其簡單的常數模型，導致嚴重的欠擬合 (Underfitting)。"
            }
        ]
    },
    2: {
        title: "資料結構 - 二元搜尋樹 (Binary Search Tree)",
        description: "深入探討 BST 的基本性質、搜尋與插入演算法、節點刪除時的各類特例處理（無子節點、一個子節點、兩個子節點）。",
        agentLogs: [
            { text: "[Parser Agent] 正在解析上傳檔案：DataStructure_BST.md...", type: "info", delay: 300 },
            { text: "[Parser Agent] 解析成功，偵測到 Markdown 語法，總字數：3,420 字。", type: "success", delay: 300 },
            { text: "[Intent Agent] 識別主要知識架構為樹狀拓撲、走訪演算法、動態更新操作。", type: "info", delay: 400 },
            { text: "[RAG Agent] 檢索二元樹定義庫，交叉比對中序、前序、後序走訪規則...", type: "info", delay: 400 },
            { text: "[Summary Agent] 正在產生 BST 的核心操作重點分析...", type: "info", delay: 500 },
            { text: "[Summary Agent] 完成：已完成『搜尋/插入時的複雜度』與『刪除節點三類情境』摘要。", type: "success", delay: 400 },
            { text: "[Quiz Agent] 開始設計演算法思考題，以模擬追蹤指標移動為主...", type: "info", delay: 500 },
            { text: "[Quiz Agent] 生成 5 題 BST 測驗題，側重於刪除節點時的 Successor 尋找邏輯。", type: "success", delay: 400 },
            { text: "[Memory Agent] 初始化 BST 樹狀概念評分卡。", type: "info", delay: 300 },
            { text: "[Critic Agent] 確認走訪演算法之圖形解釋與文字描述無誤。", type: "success", delay: 400 },
            { text: "[Response Agent] 資料編排完畢，開啟 BST Dashboard 介面...", type: "info", delay: 300 }
        ],
        summaries: [
            {
                slideNum: "Slide 1",
                title: "二元搜尋樹的基本性質與搜尋",
                desc: "二元搜尋樹 (BST) 是一種特殊的二元樹，其任意節點滿足：左子樹所有節點鍵值均小於該節點鍵值，右子樹所有節點鍵值均大於該節點鍵值。",
                bullets: [
                    "搜尋效率：理想狀況下（平衡樹），每次比較能淘汰一半的子樹，時間複雜度為 O(log n)。",
                    "走訪特點：對 BST 進行中序走訪 (In-order Traversal: 左->根->右)，所輸出的節點序列必為嚴格遞增數列。"
                ]
            },
            {
                slideNum: "Slide 2",
                title: "BST 節點插入與退化問題",
                desc: "新節點插入必定發生在樹的葉子節點 (Leaf)。從根節點開始比對，小於往左，大於往右，直到找到空位置。",
                bullets: [
                    "樹的退化：如果插入的數值本身是有序的（例如：1, 2, 3, 4, 5），BST 會退化成單向鏈結串列 (Skewed Tree)。",
                    "最壞複雜度：退化後，搜尋與插入的時間複雜度會惡化至 O(n)。這也是後續發展 AVL 樹或紅黑樹等自平衡樹的主因。"
                ]
            },
            {
                slideNum: "Slide 3",
                title: "BST 節點刪除的三種情境",
                desc: "刪除節點是 BST 中最複雜的操作，必須根據待刪除節點的子節點個數分成三種情況討論：",
                bullets: [
                    "情境 1（無子節點）：直接將其刪除，並將其父節點指向它的指標改為 NULL。",
                    "情境 2（只有一個子節點）：將該唯一的子節點接上父節點即可（直接繼承）。",
                    "情境 3（有兩個子節點）：為維持 BST 性質，必須尋找待刪除節點的『左子樹最大值』(Predecessor) 或『右子樹最小值』(Successor) 來取代其位置，再將該取代節點原位置刪除。"
                ]
            }
        ],
        glossary: [
            { term: "二元搜尋樹 (BST)", def: "每個節點最多有兩個子節點，且滿足左子節點小於根節點、右子節點大於根節點的有序樹狀結構。" },
            { term: "中序走訪 (In-order)", def: "以「左子樹 -> 根節點 -> 右子樹」的順序走訪，在 BST 中能產出從小到大的排序結果。" },
            { term: "後繼者 (Successor)", def: "在 BST 中，大於待刪除節點的所有節點中最小的那一個節點（通常在右子樹的最左下角）。" },
            { term: "樹的高度 (Tree Height)", def: "從根節點到最深葉子節點的最長路徑上的邊數，直接決定了搜尋操作的效率上限。" }
        ],
        quiz: [
            {
                id: 1,
                type: "single",
                question: "對一棵二元搜尋樹 (BST) 進行哪一種走訪 (Traversal)，可以得到一個排序好的遞增數列？",
                options: [
                    "前序走訪 (Pre-order Traversal)",
                    "中序走訪 (In-order Traversal)",
                    "後序走訪 (Post-order Traversal)",
                    "層序走訪 (Level-order Traversal)"
                ],
                correctIndex: 1,
                explanation: "中序走訪的順序是『先走訪左子樹，再訪問根節點，最後走訪右子樹』。因為 BST 滿足『左 < 根 < 右』的關係，故中序走訪正好依從小到大的順序拜訪各節點，產生排序好的遞增數列。"
            },
            {
                id: 2,
                type: "single",
                question: "在一棵包含 N 個節點的二元搜尋樹中，最壞情況下的搜尋時間複雜度是多少？",
                options: [
                    "O(1)",
                    "O(log N)",
                    "O(N)",
                    "O(N log N)"
                ],
                correctIndex: 2,
                explanation: "最壞情況發生在 BST 嚴重退化成一條鏈狀（歪斜樹，例如依序插入 1, 2, 3, 4, 5）。此時樹的高度等於節點數 N，搜尋就像搜尋鏈結串列一樣，時間複雜度退化為 O(N)。若樹是平衡的，則為 O(log N)。"
            },
            {
                id: 3,
                type: "single",
                question: "若要刪除 BST 中某個「有兩個子節點」的節點 X，我們通常會找哪一個節點來取代 X 的位置，以維持 BST 的合法性？",
                options: [
                    "X 節點的左子節點",
                    "X 節點的右子節點",
                    "X 節點左子樹的最大值 (Predecessor) 或右子樹的最小值 (Successor)",
                    "根節點 (Root)"
                ],
                correctIndex: 2,
                explanation: "當刪除有雙子節點的節點 X 時，其空位必須由最接近 X 值的節點填補。該節點可以是比 X 小的節點中最大的（左子樹最大值），或是比 X 大的節點中最小的（右子樹最小值），這樣才能保證替換後其餘左子樹仍小於新節點、右子樹仍大於新節點。"
            },
            {
                id: 4,
                type: "multiple",
                question: "【複選題】若依序將資料 [15, 8, 22, 4, 12, 19, 27] 插入一棵初始為空的二元搜尋樹中，下列敘述哪些是正確的？（請選出所有正確選項）",
                options: [
                    "這棵樹的根節點為 15",
                    "節點 12 會被掛在節點 8 的右子節點上",
                    "節點 19 會被掛在節點 22 的右子節點上",
                    "這是一棵完全平衡的樹，其高度為 2（以根節點為第 0 層計）"
                ],
                correctIndex: [0, 1, 3],
                explanation: "分析插入過程：(1) 15 為根。(2) 8 比 15 小，為左子。(3) 22 比 15 大，為右子。(4) 4 比 15 小、比 8 小，為 8 的左子。(5) 12 比 15 小、比 8 大，為 8 的右子。(6) 19 比 15 大、比 22 小，為 22 的左子（故選項3錯誤）。(7) 27 比 15 大、比 22 大，為 22 的右子。繪製出來後，這是一棵高度為 2 的完美平衡二元樹。"
            },
            {
                id: 5,
                type: "true_false",
                question: "在二元搜尋樹 (BST) 中，新插入的節點必然會被安置在某個葉子節點 (Leaf Node) 的子樹空缺處，而不會插在樹的中間成為內部節點的雙親。",
                options: [
                    "正確",
                    "錯誤"
                ],
                correctIndex: 0,
                explanation: "正確。標準的 BST 插入演算法在搜尋新節點的合適位置時，會從根節點向下比較，直到撞到 NULL（即某個現有節點的空子節點指針），然後在此處建立新節點。因此新節點在插入瞬間，必然是作為新的葉子節點加入，而不會在中途插隊拆散原本的父子關係。"
            }
        ]
    },
    3: {
        title: "作業系統 - 行程排程演算法",
        description: "理解多工 OS 如何分配 CPU。剖析 FCFS, SJF, SRTF 與 Round Robin 的調度規則、甘特圖繪製及平均等待時間計算。",
        agentLogs: [
            { text: "[Parser Agent] 正在解析上傳檔案：OS_Scheduling.pptx...", type: "info", delay: 300 },
            { text: "[Parser Agent] 讀取完成，發現 PowerPoint 包含 15 張投影片與 2 張 CPU 排程甘特圖。", type: "success", delay: 300 },
            { text: "[Intent Agent] 識別主要意圖：行程狀態轉換、排程準則（等待時間、週轉時間）、搶佔演算法。", type: "info", delay: 400 },
            { text: "[RAG Agent] 載入 OS 排程演算法公式：Turnaround Time = Completion - Arrival...", type: "info", delay: 400 },
            { text: "[Summary Agent] 正在整理排程指標與四種核心演算法...", type: "info", delay: 500 },
            { text: "[Summary Agent] 摘要完成：已生成『CPU 利用率指標』與『輪轉排程時間片影響』摘要。", type: "success", delay: 400 },
            { text: "[Quiz Agent] 設計甘特圖追蹤與平均時間計算題...", type: "info", delay: 500 },
            { text: "[Quiz Agent] 成功生成 5 題排程題，包含一題多級回饋佇列是非題。", type: "success", delay: 400 },
            { text: "[Memory Agent] 建立作業系統排程法掌握度模型。", type: "info", delay: 300 },
            { text: "[Critic Agent] 檢查排程模擬表格數據一致性... 核對無誤。", type: "success", delay: 400 },
            { text: "[Response Agent] Dashboard 排程就緒，顯示結果中...", type: "info", delay: 300 }
        ],
        summaries: [
            {
                slideNum: "Slide 1",
                title: "CPU 排程基本概念與績效指標",
                desc: "作業系統排程器的任務是在記憶體中準備執行的多個行程中，選出一個並分配 CPU 資源，以最大化系統效率。",
                bullets: [
                    "CPU 利用率 (CPU Utilization) 與 吞吐量 (Throughput, 單位時間完成的行程數)。",
                    "週轉時間 (Turnaround Time)：從行程提交到執行完成的總時間差距（包含等待時間 + 執行時間）。",
                    "等待時間 (Waiting Time)：行程在 Ready Queue 中等待獲得 CPU 執行的累積時間總和。"
                ]
            },
            {
                slideNum: "Slide 2",
                title: "基礎排程演算法比較",
                desc: "不同排程演算法針對優先順序有不同的調度邏輯，可分為非搶佔式 (Non-preemptive) 與搶佔式 (Preemptive)：",
                bullets: [
                    "FCFS (First-Come, First-Served)：先到先服務。缺點是會有『護衛效應 (Convoy Effect)』，即大行程卡在前面，後面小行程等極久。",
                    "SJF (Shortest Job First)：最短工作優先。能達到『最小平均等待時間』的理論最佳值。但有『飢餓 (Starvation)』問題，且 CPU 區間長度難以預測。",
                    "SRTF (Shortest Remaining Time First)：SJF 的搶佔式版本，當有剩餘執行時間更短的行程抵達時，強制抽換 CPU。"
                ]
            },
            {
                slideNum: "Slide 3",
                title: "輪轉排程 (Round Robin) 與時間配額",
                desc: "輪轉排程 (Round Robin, RR) 專為分時系統設計。每個行程被分配一個固定的『時間配額 (Time Quantum, q)』，用完就強迫釋放 CPU 並排入佇列尾端。",
                bullets: [
                    "時間配額的決定：若 q 設定得極大，RR 將退化成 FCFS；若 q 極小，則頻繁的『內文切換 (Context Switch)』會浪費大量 CPU 效能於儲存暫存器上。",
                    "規則：一般建議將時間配額設為使 80% 的 CPU 區間 (CPU Burst) 均能在單一時間配額內完成。"
                ]
            }
        ],
        glossary: [
            { term: "護衛效應 (Convoy Effect)", def: "在 FCFS 中，一個大型 CPU 綁定行程卡在前面，導致後方多個短行程等待極長時間，使 CPU 與 I/O 設備利用率下降的現象。" },
            { term: "搶佔式排程 (Preemptive)", def: "當行程正在執行時，排程器可以根據優先權、時間片等條件強制剝奪其 CPU 使用權，放回準備佇列中。" },
            { term: "內文切換 (Context Switch)", def: "CPU 從一個行程切換到另一個行程時，保存當前行程狀態（暫存器、PCB）並載入新行程狀態的系統開銷。" },
            { term: "多級回饋佇列 (MLFQ)", def: "動態調整行程優先權的排程法。若行程使用完時間片則降級，若行程頻繁進行 I/O 則升級，可自動平衡互動型與計算型行程。" }
        ],
        quiz: [
            {
                id: 1,
                type: "single",
                question: "在 CPU 排程中，哪一種排程演算法在「平均等待時間 (Average Waiting Time)」的評估指標上，被證實是理論上的最佳解 (Optimal)？",
                options: [
                    "先來先服務 (First-Come, First-Served, FCFS)",
                    "輪轉排程 (Round Robin, RR)",
                    "最短工作優先 (Shortest Job First, SJF)",
                    "多級佇列排程 (Multilevel Queue Scheduling)"
                ],
                correctIndex: 2,
                explanation: "最短工作優先 (SJF) 演算法每次都挑選 CPU burst 最短的行程先執行，能使等待時間最短。已被數學證明在降低平均等待時間上是最佳 (Optimal) 的演算法。然而其難以在實際 OS 中精確預測下一個 CPU burst 長度。"
            },
            {
                id: 2,
                type: "single",
                question: "關於輪轉排程 (Round Robin, RR) 的「時間配額 (Time Quantum, q)」設定，下列敘述何者正確？",
                options: [
                    "時間配額設定得越小，內文切換 (Context Switch) 次數越少，系統效率越高",
                    "若時間配額設為無限大，則 Round Robin 會退化成 First-Come, First-Served (FCFS) 演算法",
                    "時間配額的長度必須小於最長行程的執行時間，否則系統會當機",
                    "時間配額設定只影響系統的吞吐量，對行程的響應時間沒有任何影響"
                ],
                correctIndex: 1,
                explanation: "當時間配額 q 大於所有行程的執行時間時，每個行程都能一次執行完畢，無人會因為時間片用完被中斷，此時排程行為與「先來先服務 (FCFS)」完全一致。反之，q 越小，中斷與內文切換越頻繁，開銷越大。"
            },
            {
                id: 3,
                type: "true_false",
                question: "「週轉時間 (Turnaround Time)」的定義是行程從抵達準備佇列 (Ready Queue) 開始，到其在 CPU 上完全執行結束所經過的累積時間，這段時間只包含它在 CPU 上執行的時間，不包含它排隊等待的時間。",
                options: [
                    "正確",
                    "錯誤"
                ],
                correctIndex: 1,
                explanation: "這是錯誤的。週轉時間 (Turnaround Time) 的公式為：完成時間 (Completion Time) - 抵達時間 (Arrival Time)。它包含了行程在 Ready Queue 中的『等待時間 (Waiting Time)』加上在 CPU 上的『執行時間 (Burst Time)』加上 I/O 阻塞時間。只包含執行時間的指標通常是指 Burst Time。"
            },
            {
                id: 4,
                type: "multiple",
                question: "【複選題】當一個行程在執行過程中，因為發起「I/O 請求（如讀取硬碟檔案）」而暫時無法繼續使用 CPU，此時它會經歷哪些狀態轉移？（請選出所有正確選項）",
                options: [
                    "從執行狀態 (Running) 轉移至等待/阻塞狀態 (Waiting/Blocked)",
                    "從等待/阻塞狀態 (Waiting/Blocked) 直接轉移回執行狀態 (Running)",
                    "I/O 處理完成後，從等待/阻塞狀態 (Waiting/Blocked) 轉移至準備狀態 (Ready)",
                    "從準備狀態 (Ready) 獲得排程分派 (Dispatch) 轉移至執行狀態 (Running)"
                ],
                correctIndex: [0, 2, 3],
                explanation: "行程狀態生命週期：(1) 行程發起 I/O，無法使用 CPU，主動放棄並進入 Blocked 狀態。(2) 當 I/O 完成，行程無法直接搶佔 CPU 執行，而是要先回到 Ready Queue 排隊等待排程器調度（即轉移至 Ready 狀態，所以選項2錯誤）。(3) 排程器分派 (Dispatch) 後，行程重新從 Ready 進入 Running 狀態。"
            },
            {
                id: 5,
                type: "single",
                question: "「多級回饋佇列 (Multilevel Feedback Queue, MLFQ)」解決了傳統多級佇列排程的哪一個主要缺點？",
                options: [
                    "行程無法在不同佇列之間移動，缺乏彈性，且容易導致低優先權佇列中的行程飢餓 (Starvation)",
                    "它不再需要時鐘中斷 (Clock Interrupt) 即可運作",
                    "它能夠完全消除內文切換 (Context Switch) 帶來的系統額外負擔",
                    "它強制所有行程使用完全相同的 CPU 時間片，簡化了排程開銷"
                ],
                correctIndex: 0,
                explanation: "在傳統多級佇列 (Multilevel Queue) 中，行程被固定分類在特定佇列（如前台/後台），不能移動。這極缺乏彈性，且常造成低優先權佇列飢餓。MLFQ 允許行程在佇列間「動態移動」，例如表現得像 I/O-bound 的行程會提升優先權，CPU-bound 的則降級，且可透過老化 (Aging) 機制將等太久的行程提升佇列以避免飢餓。"
            }
        ]
    }
};

// ── 後端 API 設定 ──────────────────────────────────────────────────────────
const API_BASE = '/api';

// 持久化 student_id（ADR Q4：前端 crypto.randomUUID）
function getStudentId() {
    let id = localStorage.getItem('studyagent_student_id');
    if (!id) {
        id = crypto.randomUUID();
        localStorage.setItem('studyagent_student_id', id);
    }
    return id;
}
let STUDENT_ID = getStudentId();
let AUTH_TOKEN = localStorage.getItem('studyagent_token') || '';
let CURRENT_USER = localStorage.getItem('studyagent_username') || '';

// 上傳的檔案暫存
let uploadedFile = null;

// 狀態管理
let state = {
    currentScreen: 'upload', // 'upload', 'agent', 'dashboard'
    activeCourseId: null,
    activeTab: 'summary',    // 'summary', 'quiz', 'results'
    userAnswers: {},         // { qId: selectedOptionIndex } 或 { qId: [indices] } for multiple
    currentQuestionIndex: 0,
    customTextContent: "",
    quizScore: 0,
    isProcessing: false,
    // 後端整合狀態
    documentId: null,
    taskId: null,
    backendResult: null,     // { summary, quiz, plan } from backend
    useBackend: false,       // 此次分析是否使用後端
};

// 初始化 DOM 事件
document.addEventListener('DOMContentLoaded', () => {
    initElements();
    setupEventListeners();
    selectPreset(1); // 預設選取第一個講義
});

// DOM 元素引用
let els = {};
function initElements() {
    els = {
        // Screens
        screenUpload: document.getElementById('screen-upload'),
        screenAgent: document.getElementById('screen-agent'),
        screenDashboard: document.getElementById('screen-dashboard'),
        
        // Navigation Buttons & Header
        btnReset: document.getElementById('btn-reset'),
        btnExport: document.getElementById('btn-export'),
        
        // Upload page
        dropzone: document.getElementById('dropzone'),
        fileInput: document.getElementById('file-input'),
        customText: document.getElementById('custom-text'),
        btnStartAgent: document.getElementById('btn-start-agent'),
        presetCards: document.querySelectorAll('.preset-card'),
        
        // Agent process page
        flowSteps: document.querySelectorAll('.flow-step'),
        flowLineProgress: document.getElementById('flow-line-progress'),
        terminalBody: document.getElementById('terminal-body'),
        
        // Dashboard
        tabBtns: document.querySelectorAll('.tab-btn'),
        tabSummary: document.getElementById('tab-summary'),
        tabQuiz: document.getElementById('tab-quiz'),
        tabResults: document.getElementById('tab-results'),
        
        // Summary Tab
        summaryMainList: document.getElementById('summary-main-list'),
        flashcardGrid: document.getElementById('flashcard-grid'),
        
        // Quiz Tab
        quizProgressBar: document.getElementById('quiz-progress-bar'),
        quizCurrentNum: document.getElementById('quiz-current-num'),
        quizTotalNum: document.getElementById('quiz-total-num'),
        quizQuestionContainer: document.getElementById('quiz-question-container'),
        btnPrevQuestion: document.getElementById('btn-prev-question'),
        btnNextQuestion: document.getElementById('btn-next-question'),
        btnSubmitQuiz: document.getElementById('btn-submit-quiz'),
        
        // Results Tab
        scoreCircle: document.getElementById('score-circle'),
        scoreNum: document.getElementById('score-num'),
        roadmapTimeline: document.getElementById('roadmap-timeline'),
        reviewQuestionsList: document.getElementById('review-questions-list'),
        btnRetryQuiz: document.getElementById('btn-retry-quiz'),
        btnReviewStudy: document.getElementById('btn-review-study'),

        // Auth Elements
        authModal: document.getElementById('auth-modal'),
        btnLoginTrigger: document.getElementById('btn-login-trigger'),
        btnCloseAuthModal: document.getElementById('btn-close-auth-modal'),
        btnAuthSubmit: document.getElementById('btn-auth-submit'),
        authForm: document.getElementById('auth-form'),
        authUsername: document.getElementById('auth-username'),
        authPassword: document.getElementById('auth-password'),
        authStudentName: document.getElementById('auth-student-name'),
        authErrorMsg: document.getElementById('auth-error-msg'),
        authSwitchLink: document.getElementById('auth-switch-link'),
        authSwitchText: document.getElementById('auth-switch-text'),
        authModalTitle: document.getElementById('auth-modal-title'),
        userSection: document.getElementById('user-section'),
        authLoggedOut: document.getElementById('auth-logged-out'),
        authLoggedIn: document.getElementById('auth-logged-in'),
        userDisplay: document.getElementById('user-display'),
        btnLogout: document.getElementById('btn-logout')
    };
}

// 註冊 Event Listeners
function setupEventListeners() {
    // 講義範例卡片點擊
    els.presetCards.forEach(card => {
        card.addEventListener('click', () => {
            const presetId = card.getAttribute('data-preset');
            selectPreset(presetId);
        });
    });

    // 拖放檔案處理
    els.dropzone.addEventListener('click', () => els.fileInput.click());
    els.fileInput.addEventListener('change', handleFileSelect);
    els.dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        els.dropzone.classList.add('dragover');
    });
    els.dropzone.addEventListener('dragleave', () => els.dropzone.classList.remove('dragover'));
    els.dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        els.dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            processUploadedFile(e.dataTransfer.files[0]);
        }
    });

    // 文字輸入監聽
    els.customText.addEventListener('input', () => {
        if (els.customText.value.trim().length > 0) {
            // 取消 presetCard 的選取狀態，改為自訂輸入
            els.presetCards.forEach(c => c.classList.remove('active'));
            state.activeCourseId = null;
        } else {
            // 如果清空，重新選回第一個預設
            selectPreset(1);
        }
    });

    // 開始分析按鈕
    els.btnStartAgent.addEventListener('click', startAgentAnalysis);

    // Dashboard 頁籤切換
    els.tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.getAttribute('data-tab');
            switchTab(tabName);
        });
    });

    // 測驗上下題與提交
    els.btnPrevQuestion.addEventListener('click', () => navigateQuestion(-1));
    els.btnNextQuestion.addEventListener('click', () => navigateQuestion(1));
    els.btnSubmitQuiz.addEventListener('click', submitQuiz);

    // 重新測驗與返回複習
    els.btnRetryQuiz.addEventListener('click', resetQuizState);
    els.btnReviewStudy.addEventListener('click', () => switchTab('summary'));

    // 全域重置與匯出報告
    els.btnReset.addEventListener('click', resetToUpload);
    els.btnExport.addEventListener('click', exportReviewReport);

    // 會員登入 / 註冊相關事件
    if (els.btnLoginTrigger) {
        els.btnLoginTrigger.addEventListener('click', () => openAuthModal());
    }
    if (els.btnCloseAuthModal) {
        els.btnCloseAuthModal.addEventListener('click', () => closeAuthModal());
    }
    if (els.authSwitchLink) {
        els.authSwitchLink.addEventListener('click', (e) => {
            e.preventDefault();
            switchAuthMode();
        });
    }
    if (els.authForm) {
        els.authForm.addEventListener('submit', handleAuthSubmit);
    }
    if (els.btnLogout) {
        els.btnLogout.addEventListener('click', handleLogout);
    }
    
    // 初始化會員狀態顯示
    updateAuthUI();
}

// 選擇內建範例
function selectPreset(presetId) {
    els.presetCards.forEach(card => {
        if (card.getAttribute('data-preset') == presetId) {
            card.classList.add('active');
        } else {
            card.classList.remove('active');
        }
    });
    
    state.activeCourseId = presetId;
    els.customText.value = ""; // 清空手動貼上區
}

// 檔案選擇
function handleFileSelect(e) {
    if (e.target.files.length > 0) {
        processUploadedFile(e.target.files[0]);
    }
}

// 解析上傳的檔案 → 呼叫後端 API
async function processUploadedFile(file) {
    els.presetCards.forEach(c => c.classList.remove('active'));
    state.activeCourseId = null;
    uploadedFile = file;

    els.customText.value = `[已載入檔案] 名稱：${file.name}\n大小：${(file.size / 1024).toFixed(1)} KB\n\n正在上傳至後端解析中...`;
    els.btnStartAgent.disabled = true;

    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('student_id', STUDENT_ID);

        const headers = {};
        if (AUTH_TOKEN) {
            headers['Authorization'] = `Bearer ${AUTH_TOKEN}`;
        }
        const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData, headers });
        const json = await res.json();

        if (json.status === 'success' && json.data?.document_id) {
            state.documentId = json.data.document_id;
            els.customText.value = `[已載入檔案] 名稱：${file.name}\n大小：${(file.size / 1024).toFixed(1)} KB\n文件 ID：${state.documentId}\n\n✅ 上傳成功！請點擊下方「啟動 AI Agent 分析」按鈕開始。`;
        } else {
            throw new Error(json.error?.message || '上傳失敗');
        }
    } catch (err) {
        console.error('上傳失敗:', err);
        els.customText.value = `[已載入檔案] 名稱：${file.name}\n大小：${(file.size / 1024).toFixed(1)} KB\n\n⚠️ 後端上傳失敗（${err.message}），將使用模擬資料展示。`;
        uploadedFile = null;
        state.documentId = null;
    }
    els.btnStartAgent.disabled = false;
}

// 切換主畫面
function switchScreen(screenName) {
    state.currentScreen = screenName;
    
    const screens = [
        { name: 'upload', el: els.screenUpload },
        { name: 'agent', el: els.screenAgent },
        { name: 'dashboard', el: els.screenDashboard }
    ];
    
    screens.forEach(s => {
        if (s.name === screenName) {
            s.el.classList.add('active');
        } else {
            s.el.classList.remove('active');
        }
    });

    // 依據不同畫面控制 header 功能按鈕顯示
    if (screenName === 'dashboard') {
        els.btnReset.style.display = 'inline-flex';
        els.btnExport.style.display = 'inline-flex';
    } else {
        els.btnReset.style.display = 'none';
        els.btnExport.style.display = 'none';
    }
}

// 切換 Dashboard 分頁
function switchTab(tabName) {
    state.activeTab = tabName;
    
    els.tabBtns.forEach(btn => {
        if (btn.getAttribute('data-tab') === tabName) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    const tabs = [
        { name: 'summary', el: els.tabSummary },
        { name: 'quiz', el: els.tabQuiz },
        { name: 'results', el: els.tabResults }
    ];

    tabs.forEach(t => {
        if (t.name === tabName) {
            t.el.classList.add('active');
        } else {
            t.el.classList.remove('active');
        }
    });

    // 若切換到測驗頁且尚未載入題目，則初始化題目
    if (tabName === 'quiz') {
        renderQuizQuestion();
    }
}

// 啟動 Agent 分析流程
async function startAgentAnalysis() {
    if (state.isProcessing) return;
    state.isProcessing = true;
    switchScreen('agent');

    // 清空 Terminal
    els.terminalBody.innerHTML = "";
    els.flowLineProgress.style.height = "0%";
    els.flowSteps.forEach((step, idx) => {
        step.classList.remove('active', 'completed');
        if (idx === 0) step.classList.add('active');
    });

    // 判斷：有 document_id → 呼叫真實後端；否則用模擬資料
    if (state.documentId) {
        state.useBackend = true;
        await startBackendAnalysis();
    } else {
        state.useBackend = false;
        startMockAnalysis();
    }
}

// ── 真實後端 Agent 分析 ──────────────────────────────────────────────────
async function startBackendAnalysis() {
    appendTerminalLine("[System] 已連接後端 AI Agent，開始分析上傳的講義...", "info");

    try {
        // Step 1: 建立任務
        const headers = { 'Content-Type': 'application/json' };
        if (AUTH_TOKEN) {
            headers['Authorization'] = `Bearer ${AUTH_TOKEN}`;
        }
        const taskRes = await fetch(`${API_BASE}/task`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                student_id: STUDENT_ID,
                document_id: state.documentId,
                instruction: "請幫我整理重點摘要並生成測驗題目"
            })
        });
        const taskJson = await taskRes.json();
        if (taskJson.status !== 'success') throw new Error(taskJson.error?.message || '任務建立失敗');

        state.taskId = taskJson.data.task_id;
        appendTerminalLine(`[System] 任務建立成功：task_id=${state.taskId}`, "success");

        // Step 2: SSE 訂閱 workflow log
        const evtSource = new EventSource(`${API_BASE}/log/${state.taskId}/stream`);
        let stepIndex = 0;

        evtSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                const display = data.step_display || data.message || event.data;
                const type = data.status === 'failed' ? 'error' : data.status === 'success' ? 'success' : 'info';
                appendTerminalLine(display, type);

                // 更新流程節點
                const newStep = Math.min(data.step_index || 0, 4);
                if (newStep > stepIndex) {
                    els.flowSteps[stepIndex].classList.remove('active');
                    els.flowSteps[stepIndex].classList.add('completed');
                    els.flowSteps[newStep].classList.add('active');
                    stepIndex = newStep;
                }
                const progress = ((newStep + 1) / 5) * 80 + 10;
                els.flowLineProgress.style.height = `${progress}%`;
            } catch (e) {
                appendTerminalLine(event.data, "info");
            }
        };

        evtSource.onerror = () => { evtSource.close(); };

        // Step 3: 輪詢任務狀態
        const result = await pollTaskUntilDone(state.taskId);
        evtSource.close();

        if (result) {
            appendTerminalLine("[System] ✅ 所有 Agent 任務已完成！載入結果中...", "success");
            state.backendResult = result;
            buildDashboardFromBackend(result);
        } else {
            throw new Error("任務執行失敗或逾時");
        }
    } catch (err) {
        console.error('後端分析失敗:', err);
        appendTerminalLine(`[System] ❌ 後端分析失敗：${err.message}`, "error");
        appendTerminalLine("[System] 將使用內建範例資料作為展示...", "info");
        state.useBackend = false;

        // Fallback 到模擬資料
        await new Promise(r => setTimeout(r, 1500));
        buildDashboardData();
        switchScreen('dashboard');
        switchTab('summary');
    }
    state.isProcessing = false;
}

// 輪詢任務狀態直到完成
async function pollTaskUntilDone(taskId, maxRetries = 60) {
    const headers = {};
    if (AUTH_TOKEN) {
        headers['Authorization'] = `Bearer ${AUTH_TOKEN}`;
    }
    for (let i = 0; i < maxRetries; i++) {
        await new Promise(r => setTimeout(r, 2000));
        try {
            const res = await fetch(`${API_BASE}/task/${taskId}`, { headers });
            const json = await res.json();
            const status = json.data?.status;

            if (status === 'completed') {
                // 取得完整結果
                const resultRes = await fetch(`${API_BASE}/task/${taskId}/result`, { headers });
                const resultJson = await resultRes.json();
                return resultJson.data || null;
            } else if (status === 'failed') {
                return null;
            }
        } catch (e) {
            console.warn('輪詢失敗:', e);
        }
    }
    return null;
}

// Terminal 輸出 helper
function appendTerminalLine(text, type = 'info') {
    const line = document.createElement('div');
    line.className = `terminal-line ${type}`;
    line.innerText = text;
    els.terminalBody.appendChild(line);
    els.terminalBody.scrollTop = els.terminalBody.scrollHeight;
}

// ── 模擬 Agent 分析（使用內建資料） ──────────────────────────────────────
function startMockAnalysis() {
    let courseData = COURSE_PRESETS[state.activeCourseId || 1];
    let logs = [...courseData.agentLogs];

    if (!state.activeCourseId) {
        logs[0] = { text: "[Parser Agent] 正在解析使用者上傳的自訂簡報文字...", type: "info", delay: 300 };
        logs[1] = { text: "[Parser Agent] 解析文字區塊成功，偵測到約 1200 字內容。", type: "success", delay: 300 };
        logs[2] = { text: "[Intent Agent] 分析自訂內容意圖：提取核心概念大綱、設計自我挑戰題。", type: "info", delay: 400 };
    }

    let logIndex = 0;
    let stepIndex = 0;

    function printNextLog() {
        if (logIndex >= logs.length) {
            setTimeout(() => {
                state.isProcessing = false;
                buildDashboardData();
                switchScreen('dashboard');
                switchTab('summary');
            }, 600);
            return;
        }

        const log = logs[logIndex];
        appendTerminalLine(log.text, log.type);

        const progressPercentage = (logIndex / logs.length) * 80 + 10;
        els.flowLineProgress.style.height = `${progressPercentage}%`;

        let newStepIndex = stepIndex;
        if (log.text.includes("[Parser")) newStepIndex = 0;
        else if (log.text.includes("[Intent") || log.text.includes("[RAG")) newStepIndex = 1;
        else if (log.text.includes("[Summary")) newStepIndex = 2;
        else if (log.text.includes("[Quiz")) newStepIndex = 3;
        else if (log.text.includes("[Memory") || log.text.includes("[Critic") || log.text.includes("[Response")) newStepIndex = 4;

        if (newStepIndex !== stepIndex) {
            els.flowSteps[stepIndex].classList.remove('active');
            els.flowSteps[stepIndex].classList.add('completed');
            els.flowSteps[newStepIndex].classList.add('active');
            stepIndex = newStepIndex;
        }

        logIndex++;
        setTimeout(printNextLog, log.delay || 300);
    }

    setTimeout(printNextLog, 200);
}

// ── 用後端真實結果建立 Dashboard ──────────────────────────────────────────
function buildDashboardFromBackend(result) {
    // 解析後端回傳的 summary
    let summaryData = result.summary || {};
    let quizData = result.quiz || [];

    // 轉換 summary 格式為前端可渲染格式
    let summaries = [];
    if (summaryData.summary || summaryData.key_points) {
        summaries.push({
            slideNum: "AI 摘要",
            title: summaryData.topic || "講義重點摘要",
            desc: summaryData.summary || "",
            bullets: (summaryData.key_points || []).map(p => p.replace(/^[•\-]\s*/, ''))
        });
    }
    if (summaries.length === 0) {
        summaries.push({
            slideNum: "摘要",
            title: "AI 分析結果",
            desc: typeof summaryData === 'string' ? summaryData : JSON.stringify(summaryData),
            bullets: []
        });
    }

    // 渲染摘要
    els.summaryMainList.innerHTML = "";
    summaries.forEach(s => {
        const card = document.createElement('div');
        card.className = 'slide-summary-card';
        let bulletsHtml = s.bullets.map(b => `<li>${b}</li>`).join('');
        card.innerHTML = `
            <div class="slide-num-badge">${s.slideNum}</div>
            <h3>${s.title}</h3>
            <p>${s.desc}</p>
            <ul>${bulletsHtml}</ul>
        `;
        els.summaryMainList.appendChild(card);
    });

    // 渲染閃卡（從 glossary 中提取名詞與定義，無詞彙則退回以 key_points 渲染）
    els.flashcardGrid.innerHTML = "";
    const glossary = summaryData.glossary || [];
    if (glossary.length > 0) {
        glossary.forEach(g => {
            const wrapper = document.createElement('div');
            wrapper.className = 'flashcard-wrapper';
            wrapper.innerHTML = `
                <div class="flashcard-inner">
                    <div class="flashcard-front">
                        <h4>${g.term}</h4>
                        <span>💡 點擊翻看 AI 定義</span>
                    </div>
                    <div class="flashcard-back">
                        <p>${g.def}</p>
                    </div>
                </div>
            `;
            wrapper.addEventListener('click', () => wrapper.classList.toggle('flipped'));
            els.flashcardGrid.appendChild(wrapper);
        });
    } else {
        const keyPoints = summaryData.key_points || [];
        keyPoints.slice(0, 4).forEach((kp, i) => {
            const wrapper = document.createElement('div');
            wrapper.className = 'flashcard-wrapper';
            wrapper.innerHTML = `
                <div class="flashcard-inner">
                    <div class="flashcard-front">
                        <h4>重點 ${i + 1}</h4>
                        <span>💡 點擊翻看詳情</span>
                    </div>
                    <div class="flashcard-back">
                        <p>${kp}</p>
                    </div>
                </div>
            `;
            wrapper.addEventListener('click', () => wrapper.classList.toggle('flipped'));
            els.flashcardGrid.appendChild(wrapper);
        });
    }

    // 轉換 quiz 格式並儲存到 state
    state.backendQuiz = quizData.map((q, i) => ({
        id: i + 1,
        type: q.question_type === 'true_false' ? 'true_false' : 'single',
        question: q.question || '',
        options: q.options || [],
        correctAnswer: q.correct_answer || '',
        explanation: q.explanation || '',
        topic: q.topic || ''
    }));

    // 重置測驗狀態
    state.userAnswers = {};
    state.currentQuestionIndex = 0;
    state.quizScore = 0;

    switchScreen('dashboard');
    switchTab('summary');
}

// 建立並渲染 Dashboard 重點與測驗資料
function buildDashboardData() {
    let data = COURSE_PRESETS[state.activeCourseId || 1];
    
    // 如果是自訂輸入，我們隨機混入一些自訂的字詞提示以符合 UX 的擬真感
    let summaries = [...data.summaries];
    let glossary = [...data.glossary];
    
    if (!state.activeCourseId) {
        // 修改第一個重點的標題為使用者自訂的虛擬標題
        summaries = [
            {
                slideNum: "Slide 1",
                title: "自訂講義分析 - 核心概念結構",
                desc: "AI 已經自動為您上傳的自訂內容完成了多層次的主題分類，以下為您整理最重要的核心學習重點。",
                bullets: [
                    "講義關鍵主題摘要：此處已經將您貼上的段落精練為階層化清單。",
                    "知識關聯度分析：已自動鏈結相關的先備知識與實務應用場景。"
                ]
            },
            ...summaries.slice(1)
        ];
    }

    // 1. 渲染重點整理
    els.summaryMainList.innerHTML = "";
    summaries.forEach(s => {
        const card = document.createElement('div');
        card.className = 'slide-summary-card';
        
        let bulletsHtml = s.bullets.map(b => `<li>${b}</li>`).join('');
        
        card.innerHTML = `
            <div class="slide-num-badge">${s.slideNum}</div>
            <h3>${s.title}</h3>
            <p>${s.desc}</p>
            <ul>${bulletsHtml}</ul>
        `;
        els.summaryMainList.appendChild(card);
    });

    // 2. 渲染核心詞彙卡片 (3D 翻轉效果)
    els.flashcardGrid.innerHTML = "";
    glossary.forEach(g => {
        const wrapper = document.createElement('div');
        wrapper.className = 'flashcard-wrapper';
        
        wrapper.innerHTML = `
            <div class="flashcard-inner">
                <div class="flashcard-front">
                    <h4>${g.term}</h4>
                    <span>💡 點擊翻看 AI 定義</span>
                </div>
                <div class="flashcard-back">
                    <p>${g.def}</p>
                </div>
            </div>
        `;
        
        // 點擊事件：翻轉卡片
        wrapper.addEventListener('click', () => {
            wrapper.classList.toggle('flipped');
        });
        
        els.flashcardGrid.appendChild(wrapper);
    });

    // 3. 重置測驗作答狀態
    resetQuizState();
}

// 重置測驗狀態
function resetQuizState() {
    state.userAnswers = {};
    state.currentQuestionIndex = 0;
    state.quizScore = 0;
    
    // 清除 tabResults 狀態，並返回 quiz 頁籤
    els.scoreCircle.style.background = `conic-gradient(var(--border-color) 0%, rgba(255,255,255,0.05) 0%)`;
    els.scoreNum.innerText = "0";
    els.roadmapTimeline.innerHTML = "";
    els.reviewQuestionsList.innerHTML = "";

    switchTab('quiz');
}

// 取得當前測驗題目（後端優先，模擬資料 fallback）
function getActiveQuizQuestions() {
    if (state.useBackend && state.backendQuiz && state.backendQuiz.length > 0) {
        return state.backendQuiz;
    }
    let data = COURSE_PRESETS[state.activeCourseId || 1];
    return data.quiz;
}

// 渲染當前測驗問題
function renderQuizQuestion() {
    let questions = getActiveQuizQuestions();
    let currentQ = questions[state.currentQuestionIndex];
    
    // 渲染進度條
    const progress = ((state.currentQuestionIndex) / questions.length) * 100;
    els.quizProgressBar.style.width = `${progress}%`;
    
    els.quizCurrentNum.innerText = state.currentQuestionIndex + 1;
    els.quizTotalNum.innerText = questions.length;

    // 清空並繪製題目卡
    els.quizQuestionContainer.innerHTML = "";
    
    const card = document.createElement('div');
    card.className = 'question-card';
    
    let isMulti = currentQ.type === 'multiple';
    let qTypeBadge = isMulti ? '<span style="color: var(--secondary); font-size: 0.8rem; font-weight:700;">【複選題】</span>' : '';
    
    card.innerHTML = `
        <div class="question-text">${qTypeBadge}${currentQ.question}</div>
        <div class="options-container" id="options-box"></div>
    `;
    els.quizQuestionContainer.appendChild(card);

    const optionsBox = document.getElementById('options-box');
    const userAns = state.userAnswers[currentQ.id];

    currentQ.options.forEach((opt, idx) => {
        const btn = document.createElement('button');
        btn.className = 'option-btn';
        
        let isSelected = false;
        if (isMulti) {
            isSelected = Array.isArray(userAns) && userAns.includes(idx);
        } else {
            isSelected = userAns === idx;
        }

        if (isSelected) {
            btn.classList.add('selected');
        }

        const optionLetter = String.fromCharCode(65 + idx); // A, B, C, D...
        btn.innerHTML = `
            <div class="option-badge">${optionLetter}</div>
            <div class="option-label-text">${opt}</div>
        `;

        btn.addEventListener('click', () => handleOptionClick(currentQ.id, idx, isMulti));
        optionsBox.appendChild(btn);
    });

    // 調整按鈕顯示狀態
    els.btnPrevQuestion.style.visibility = state.currentQuestionIndex === 0 ? 'hidden' : 'visible';
    
    if (state.currentQuestionIndex === questions.length - 1) {
        els.btnNextQuestion.style.display = 'none';
        els.btnSubmitQuiz.style.display = 'inline-flex';
    } else {
        els.btnNextQuestion.style.display = 'inline-flex';
        els.btnSubmitQuiz.style.display = 'none';
    }
}

// 選擇答案處理
function handleOptionClick(qId, optionIdx, isMulti) {
    if (isMulti) {
        if (!Array.isArray(state.userAnswers[qId])) {
            state.userAnswers[qId] = [];
        }
        const indexInArr = state.userAnswers[qId].indexOf(optionIdx);
        if (indexInArr > -1) {
            state.userAnswers[qId].splice(indexInArr, 1); // 取消選取
        } else {
            state.userAnswers[qId].push(optionIdx); // 點選
        }
    } else {
        state.userAnswers[qId] = optionIdx;
    }
    
    renderQuizQuestion(); // 重新渲染更新選取狀態
}

// 切換上/下一題
function navigateQuestion(direction) {
    state.currentQuestionIndex += direction;
    renderQuizQuestion();
}

// 提交測驗與統計結果
async function submitQuiz() {
    let questions = getActiveQuizQuestions();
    
    // 檢查是否所有題目都作答了，若有漏寫則提示
    let unansweredCount = 0;
    questions.forEach(q => {
        const ans = state.userAnswers[q.id];
        if (ans === undefined || (Array.isArray(ans) && ans.length === 0)) {
            unansweredCount++;
        }
    });

    if (unansweredCount > 0) {
        alert(`您還有 ${unansweredCount} 題尚未作答，請完成所有題目後再提交！`);
        return;
    }

    if (state.useBackend) {
        // ── 後端真實 AI 批改與複習路徑生成 ─────────────────────────────
        els.btnSubmitQuiz.disabled = true;
        els.btnSubmitQuiz.innerText = "提交批改中...";
        
        try {
            const answers = questions.map((q, idx) => {
                const userAnsIdx = state.userAnswers[q.id];
                return {
                    quiz_index: idx,
                    student_answer: q.options[userAnsIdx] || ''
                };
            });

            const headers = { 'Content-Type': 'application/json' };
            if (AUTH_TOKEN) {
                headers['Authorization'] = `Bearer ${AUTH_TOKEN}`;
            }
            const res = await fetch(`${API_BASE}/grade`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    task_id: state.taskId,
                    student_id: STUDENT_ID,
                    answers: answers
                })
            });
            const json = await res.json();
            if (json.status !== 'success') throw new Error(json.error?.message || '批改服務錯誤');

            const gradeData = json.data;
            const score = Math.round(gradeData.accuracy * 100);
            state.quizScore = score;

            // 更新結果畫面
            els.scoreNum.innerText = score;
            els.scoreCircle.style.background = `conic-gradient(var(--primary) ${score}%, rgba(255, 255, 255, 0.05) ${score}%)`;

            // 渲染批改細節
            let reviewHtml = "";
            gradeData.grading_results.forEach((r, idx) => {
                const statusClass = r.is_correct ? 'correct' : 'incorrect';
                const statusBadge = r.is_correct ? '<span style="color: var(--accent); font-weight:700;">✓ 正確</span>' : '<span style="color: var(--danger); font-weight:700;">✗ 錯誤</span>';
                reviewHtml += `
                    <div class="review-question-item ${statusClass}">
                        <div class="review-q-title">第 ${idx + 1} 題：${r.question}</div>
                        <div class="review-q-answers">
                            您的作答：<span style="font-weight:600; color: ${r.is_correct ? 'var(--accent)' : 'var(--danger)'};">${r.student_answer}</span> | 
                            標準答案：<span style="font-weight:600; color: var(--primary);">${r.correct_answer}</span> &nbsp;&nbsp; ${statusBadge}
                        </div>
                        <div class="review-q-explanation">
                            <strong>AI 解析提示：</strong>${r.explanation}
                        </div>
                    </div>
                `;
            });
            els.reviewQuestionsList.innerHTML = reviewHtml;

            // 顯示載入動畫並開始呼叫後端生成個人化複習計畫
            switchTab('results');
            await generateBackendStudyPlan(gradeData.updated_weak_topics);

        } catch (err) {
            console.error("後端批改失敗:", err);
            alert(`後端批改失敗：${err.message}，將切換至本地模擬批改。`);
            state.useBackend = false;
            // 回退到本地批改
            els.btnSubmitQuiz.disabled = false;
            els.btnSubmitQuiz.innerText = "📤 提交測驗答案";
            submitQuiz();
        }
    } else {
        // ── 本地模擬批改與複習路徑生成 ─────────────────────────────────
        let correctCount = 0;
        let reviewHtml = "";
        let wrongTopics = [];

        questions.forEach((q, idx) => {
            const userAns = state.userAnswers[q.id];
            let isCorrect = false;

            if (q.type === 'multiple') {
                if (Array.isArray(userAns) && Array.isArray(q.correctIndex)) {
                    const sortedUser = [...userAns].sort();
                    const sortedCorrect = [...q.correctIndex].sort();
                    isCorrect = sortedUser.length === sortedCorrect.length && sortedUser.every((v, i) => v === sortedCorrect[i]);
                }
            } else {
                isCorrect = userAns === q.correctIndex;
            }

            if (isCorrect) {
                correctCount++;
            } else {
                wrongTopics.push(q);
            }

            let userAnsStr = "";
            let correctAnsStr = "";

            if (q.type === 'multiple') {
                userAnsStr = Array.isArray(userAns) ? userAns.map(i => String.fromCharCode(65 + i)).join(', ') : '無';
                correctAnsStr = q.correctIndex.map(i => String.fromCharCode(65 + i)).join(', ');
            } else {
                userAnsStr = userAns !== undefined ? String.fromCharCode(65 + userAns) : '無';
                correctAnsStr = String.fromCharCode(65 + q.correctIndex);
            }

            const statusClass = isCorrect ? 'correct' : 'incorrect';
            const statusBadge = isCorrect ? '<span style="color: var(--accent); font-weight:700;">✓ 正確</span>' : '<span style="color: var(--danger); font-weight:700;">✗ 錯誤</span>';

            reviewHtml += `
                <div class="review-question-item ${statusClass}">
                    <div class="review-q-title">第 ${idx + 1} 題：${q.question}</div>
                    <div class="review-q-answers">
                        您的作答：<span style="font-weight:600; color: ${isCorrect ? 'var(--accent)' : 'var(--danger)'};">${userAnsStr}</span> | 
                        標準答案：<span style="font-weight:600; color: var(--primary);">${correctAnsStr}</span> &nbsp;&nbsp; ${statusBadge}
                    </div>
                    <div class="review-q-explanation">
                        <strong>AI 解析提示：</strong>${q.explanation}
                    </div>
                </div>
            `;
        });

        const score = Math.round((correctCount / questions.length) * 100);
        state.quizScore = score;

        // 更新結果畫面
        els.scoreNum.innerText = score;
        els.scoreCircle.style.background = `conic-gradient(var(--primary) ${score}%, rgba(255, 255, 255, 0.05) ${score}%)`;
        els.reviewQuestionsList.innerHTML = reviewHtml;

        // 生成本地模擬複習路徑
        const courseTitle = COURSE_PRESETS[state.activeCourseId || 1]?.title || '講義';
        generateRoadmap(score, wrongTopics, courseTitle);

        switchTab('results');
    }
}

// ── 生成後端 AI 個人化複習路徑 ───────────────────────────────────────
async function generateBackendStudyPlan(weakTopics) {
    els.roadmapTimeline.innerHTML = `
        <div class="roadmap-loading" style="text-align: center; padding: 30px; color: var(--text-secondary);">
            <div class="spinner" style="font-size: 24px; margin-bottom: 12px; animation: spin 1.5s linear infinite; display: inline-block;">⚙️</div>
            <p style="font-size: 0.95em; color: var(--text-secondary);">AI Agent 正在診斷您的弱點並為您規劃複習計畫...</p>
        </div>
    `;

    try {
        const headers = { 'Content-Type': 'application/json' };
        if (AUTH_TOKEN) {
            headers['Authorization'] = `Bearer ${AUTH_TOKEN}`;
        }
        const res = await fetch(`${API_BASE}/task`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                student_id: STUDENT_ID,
                document_id: state.documentId,
                instruction: "請根據我的弱點為我生成個人化複習計畫。我的弱點包含: " + JSON.stringify(weakTopics)
            })
        });
        const json = await res.json();
        if (json.status !== 'success') throw new Error(json.error?.message || '計畫建立失敗');

        const planTaskId = json.data.task_id;
        const result = await pollTaskUntilDone(planTaskId);
        if (result && result.plan) {
            state.backendResult.plan = result.plan;
            renderBackendStudyPlan(result.plan);
        } else {
            throw new Error("無法取得個人化計畫");
        }
    } catch (err) {
        console.error("生成個人化計畫失敗:", err);
        els.roadmapTimeline.innerHTML = `
            <div style="color: var(--danger); padding: 15px; border: 1px solid var(--danger); border-radius: 8px; font-size: 0.9em; background: rgba(239, 68, 68, 0.05);">
                ⚠️ 無法生成 AI 個人化計畫：${err.message}。建議您重新複習講義的摘要大綱。
            </div>
        `;
    }
}

// ── 渲染後端 AI 個人化複習計畫 ───────────────────────────────────────
function renderBackendStudyPlan(plan) {
    els.roadmapTimeline.innerHTML = "";
    
    // 渲染整體複習策略
    if (plan.summary) {
        const summaryDiv = document.createElement('div');
        summaryDiv.style.marginBottom = "20px";
        summaryDiv.style.padding = "16px";
        summaryDiv.style.borderRadius = "8px";
        summaryDiv.style.background = "rgba(255, 255, 255, 0.02)";
        summaryDiv.style.borderLeft = "4px solid var(--accent)";
        summaryDiv.innerHTML = `
            <h5 style="margin: 0 0 6px 0; color: var(--text-primary); font-size: 1.05em; font-weight: 600;">🧠 整體複習策略</h5>
            <p style="margin: 0; font-size: 0.9em; line-height: 1.6; color: var(--text-secondary);">${plan.summary}</p>
            ${plan.estimated_study_hours ? `<div style="margin-top: 10px; font-size: 0.85em; color: var(--accent); font-weight: 500;">⏳ 預估複習時間：${plan.estimated_study_hours} 小時</div>` : ''}
        `;
        els.roadmapTimeline.appendChild(summaryDiv);
    }
    
    // 渲染具體單元推薦路徑
    if (plan.recommendations && plan.recommendations.length > 0) {
        plan.recommendations.forEach((rec, idx) => {
            const timelineItem = document.createElement('div');
            timelineItem.className = 'roadmap-item';
            
            const priorityColors = {
                high: 'var(--danger)',
                medium: 'var(--warning)',
                low: 'var(--accent)'
            };
            const priorityLabels = {
                high: '🔴 高度補強',
                medium: '🟡 一般複習',
                low: '🔵 觀念確認'
            };
            const pColor = priorityColors[rec.priority] || 'var(--text-secondary)';
            const pLabel = priorityLabels[rec.priority] || rec.priority;
            
            let actionsHtml = (rec.suggested_actions || []).map(act => `<li>${act}</li>`).join('');
            
            timelineItem.innerHTML = `
                <h5 style="margin-top: 0;">步驟 ${idx + 1}: ${rec.topic} <span style="font-size: 0.75em; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.05); color: ${pColor}; font-weight: 600; margin-left: 8px;">${pLabel}</span></h5>
                <p style="margin-bottom: 8px; font-size: 0.9em;"><strong>弱點診斷：</strong>${rec.reason}</p>
                <ul style="margin: 0; padding-left: 20px; font-size: 0.85em; line-height: 1.6; color: var(--text-secondary);">
                    ${actionsHtml}
                </ul>
            `;
            els.roadmapTimeline.appendChild(timelineItem);
        });
    } else {
        els.roadmapTimeline.innerHTML += `
            <div class="roadmap-item">
                <h5 style="color: var(--accent);">🏅 觀念極致掌握！</h5>
                <p>您在本次測驗中拿到了滿分，基礎觀念非常紮實！建議保持良好的學習習慣並繼續挑戰進階題目。</p>
            </div>
        `;
    }
}

// 依據得分與錯題生成本地客製化複習路徑
function generateRoadmap(score, wrongQuestions, courseTitle) {
    els.roadmapTimeline.innerHTML = "";
    
    let roadmapItems = [];

    if (score === 100) {
        roadmapItems = [
            {
                title: "🏅 觀念極致掌握！",
                desc: `您在『${courseTitle}』的所有小測驗中拿到了滿分，基礎觀念非常紮實！`
            },
            {
                title: "🚀 進階挑戰建議",
                desc: "建議可前往閱讀更深入的實務專案部署或進階演算法推導，以擴展您的知識邊界。"
            }
        ];
    } else {
        // 有錯題，AI Agent 提供診斷複習路徑
        roadmapItems.push({
            title: `✍️ 重點觀念補強 (${courseTitle})`,
            desc: `您在此測驗中獲得了 ${score} 分。AI Agent 根據您的錯題，規劃了以下客製化複習指南。`
        });

        // 依據錯題針對性給予複習指示
        wrongQuestions.forEach((q, idx) => {
            let topicName = "";
            let actionText = "";
            
            if (q.question.includes("過擬合") || q.question.includes("L2") || q.question.includes("L1")) {
                topicName = "投影片 Slide 3: 過擬合與正規化機制";
                actionText = "重新複習 Lasso (L1) 會產生稀疏矩陣、Ridge (L2) 平滑參數的幾何意義與公式特點。";
            } else if (q.question.includes("學習率") || q.question.includes("梯度")) {
                topicName = "投影片 Slide 2: 損失函數與梯度下降法";
                actionText = "深入理解學習率 (α) 大小對模型權重調整步伐的具體影響及收斂條件。";
            } else if (q.question.includes("監督式")) {
                topicName = "投影片 Slide 1: 機器學習分類與監督式學習";
                actionText = "區分有標籤的 Regression/Classification 與無標籤分群法 (Clustering) 的本質差異。";
            } else if (q.question.includes("走訪") || q.question.includes("中序")) {
                topicName = "投影片 Slide 1: BST 的基本性質與搜尋";
                actionText = "動態追蹤 BST 中序走訪的順序：『左子樹 -> 根節點 -> 右子樹』所產生的遞增數列。";
            } else if (q.question.includes("時間複雜度") || q.question.includes("退化")) {
                topicName = "投影片 Slide 2: BST 節點插入與退化問題";
                actionText = "理解極端有序輸入會導致 BST 退化為鏈結串列，使得搜尋效率退化至 O(N) 的成因。";
            } else if (q.question.includes("雙子節點") || q.question.includes("刪除")) {
                topicName = "投影片 Slide 3: BST 節點刪除演算法";
                actionText = "練習手繪尋找『右子樹最小值 (Successor)』或『左子樹最大值 (Predecessor)』的移動路徑並進行替換。";
            } else if (q.question.includes("等待時間") || q.question.includes("週轉時間")) {
                topicName = "投影片 Slide 1: CPU 排程績效指標";
                actionText = "重溫週轉時間 (Turnaround Time = 完成 - 抵達) 與等待時間的公式計算，並學會畫甘特圖。";
            } else if (q.question.includes("輪轉排程") || q.question.includes("時間配額")) {
                topicName = "投影片 Slide 3: 輪轉排程 (Round Robin)";
                actionText = "掌握時間片 q 大小對系統績效的影響：太小導致頻繁內文切換，太大退化成 FCFS。";
            } else if (q.question.includes("多級回饋")) {
                topicName = "投影片 Slide 3: 多級回饋佇列 (MLFQ)";
                actionText = "複習 MLFQ 的動態升降級邏輯與老化機制 (Aging)，了解其如何兼顧響應速度與防飢餓。";
            } else {
                topicName = "講義延伸主題";
                actionText = "建議重新翻閱對應章節，並利用 AI 重點整理重新梳理名詞定義。";
            }

            roadmapItems.push({
                title: `步驟 ${idx + 1}: 補強「${topicName}」`,
                desc: actionText
            });
        });

        // 結尾鼓勵與重測建議
        roadmapItems.push({
            title: "🔄 複習完畢後自我檢測",
            desc: "建議點擊下方的『回到講義重點』重新瀏覽，並在對應重點卡片中點擊翻牌記憶詞彙，最後再次進行測驗以驗證成效。"
        });
    }

    // 渲染 roadmap
    roadmapItems.forEach(item => {
        const timelineItem = document.createElement('div');
        timelineItem.className = 'roadmap-item';
        timelineItem.innerHTML = `
            <h5>${item.title}</h5>
            <p>${item.desc}</p>
        `;
        els.roadmapTimeline.appendChild(timelineItem);
    });
}

// 匯出複習報告 (實體文字匯出)
function exportReviewReport() {
    let reportContent = `--------------------------------------------\n`;
    reportContent += `StudyAgent AI 學習複習報告書\n`;
    reportContent += `報告產出時間：${new Date().toLocaleString()}\n`;
    reportContent += `本次小測驗得分：${state.quizScore} 分\n`;
    reportContent += `--------------------------------------------\n\n`;

    if (state.useBackend && state.backendResult) {
        const result = state.backendResult;
        const summary = result.summary || {};
        const title = summary.topic || "AI 講義重點摘要";
        
        reportContent += `單元主題：${title}\n\n`;
        reportContent += `【重點整理摘要】\n`;
        reportContent += `- 核心：${summary.summary || '無'}\n\n`;
        
        if (summary.key_points && summary.key_points.length > 0) {
            reportContent += `【核心關鍵要點】\n`;
            summary.key_points.forEach((kp, idx) => {
                reportContent += `${idx + 1}. ${kp}\n`;
            });
            reportContent += `\n`;
        }
        
        if (result.plan) {
            reportContent += `【AI 個人化複習計畫】\n`;
            reportContent += `整體策略：${result.plan.summary || ''}\n`;
            if (result.plan.estimated_study_hours) {
                reportContent += `預計所需時間：${result.plan.estimated_study_hours} 小時\n`;
            }
            if (result.plan.recommendations) {
                result.plan.recommendations.forEach((rec, idx) => {
                    reportContent += `\n單元 ${idx + 1}: ${rec.topic} (${rec.priority === 'high' ? '高優先級' : rec.priority === 'medium' ? '中優先級' : '低優先級'})\n`;
                    reportContent += `  * 診斷原因: ${rec.reason}\n`;
                    (rec.suggested_actions || []).forEach(act => {
                        reportContent += `  * 行動建議: ${act}\n`;
                    });
                });
            }
        }
    } else {
        let data = COURSE_PRESETS[state.activeCourseId || 1];
        reportContent += `單元主題：${data.title}\n\n`;
        reportContent += `【重點整理摘要】\n`;
        
        data.summaries.forEach((s, idx) => {
            reportContent += `${idx + 1}. ${s.title}\n`;
            reportContent += `   - 核心：${s.desc}\n`;
            s.bullets.forEach(b => {
                reportContent += `   * ${b}\n`;
            });
            reportContent += `\n`;
        });

        reportContent += `【核心名詞解釋】\n`;
        data.glossary.forEach(g => {
            reportContent += `* ${g.term}：${g.def}\n`;
        });
    }

    // 建立 Blob 並觸發下載
    const blob = new Blob([reportContent], { type: 'text/plain;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    const fileNameTitle = state.useBackend ? (state.backendResult?.summary?.topic || "AI_Summary") : (COURSE_PRESETS[state.activeCourseId || 1]?.title || "Report");
    link.download = `StudyAgent_Report_${fileNameTitle.replace(/\s+/g, '_')}.txt`;
    link.click();
    URL.revokeObjectURL(link.href);
}

// 重置回上傳頁面
function resetToUpload() {
    selectPreset(1);
    state.documentId = null;
    state.taskId = null;
    state.backendResult = null;
    state.useBackend = false;
    // 恢復 Submit 按鈕狀態
    els.btnSubmitQuiz.disabled = false;
    els.btnSubmitQuiz.innerText = "📤 提交測驗答案";
    switchScreen('upload');
}

// ── 會員登入註冊輔助功能 ──────────────────────────────────────────────────
let isRegisterMode = false;

function updateAuthUI() {
    if (AUTH_TOKEN && CURRENT_USER) {
        if (els.authLoggedOut) els.authLoggedOut.style.display = 'none';
        if (els.authLoggedIn) {
            els.authLoggedIn.style.display = 'flex';
            els.userDisplay.innerText = `👤 ${CURRENT_USER}`;
        }
    } else {
        if (els.authLoggedOut) els.authLoggedOut.style.display = 'block';
        if (els.authLoggedIn) els.authLoggedIn.style.display = 'none';
    }
}

function openAuthModal() {
    isRegisterMode = false;
    resetAuthForm();
    if (els.authModal) {
        els.authModal.style.display = 'flex';
        setTimeout(() => els.authModal.classList.add('active'), 10);
    }
}

function closeAuthModal() {
    if (els.authModal) {
        els.authModal.classList.remove('active');
        setTimeout(() => els.authModal.style.display = 'none', 300);
    }
}

function resetAuthForm() {
    if (els.authForm) els.authForm.reset();
    if (els.authErrorMsg) {
        els.authErrorMsg.style.display = 'none';
        els.authErrorMsg.innerText = '';
    }
    isRegisterMode = false;
    updateAuthModalLabels();
}

function updateAuthModalLabels() {
    if (isRegisterMode) {
        if (els.authModalTitle) els.authModalTitle.innerText = '註冊會員';
        if (els.btnAuthSubmit) els.btnAuthSubmit.innerText = '註冊並登入';
        if (els.authSwitchText) els.authSwitchText.innerText = '已經有帳號了？';
        if (els.authSwitchLink) els.authSwitchLink.innerText = '立即登入';
        document.querySelectorAll('.register-only').forEach(el => el.style.display = 'flex');
        if (els.authStudentName) els.authStudentName.required = false;
    } else {
        if (els.authModalTitle) els.authModalTitle.innerText = '會員登入';
        if (els.btnAuthSubmit) els.btnAuthSubmit.innerText = '登入';
        if (els.authSwitchText) els.authSwitchText.innerText = '還沒有帳號嗎？';
        if (els.authSwitchLink) els.authSwitchLink.innerText = '立即註冊';
        document.querySelectorAll('.register-only').forEach(el => el.style.display = 'none');
    }
}

function switchAuthMode() {
    isRegisterMode = !isRegisterMode;
    if (els.authErrorMsg) {
        els.authErrorMsg.style.display = 'none';
        els.authErrorMsg.innerText = '';
    }
    updateAuthModalLabels();
}

async function handleAuthSubmit(e) {
    e.preventDefault();
    if (els.authErrorMsg) els.authErrorMsg.style.display = 'none';
    
    const username = els.authUsername.value.trim();
    const password = els.authPassword.value;
    const studentName = isRegisterMode ? els.authStudentName.value.trim() : '';
    
    if (username.length < 3) {
        showAuthError('帳號長度至少需為 3 個字元');
        return;
    }
    if (password.length < 6) {
        showAuthError('密碼長度至少需為 6 個字元');
        return;
    }
    
    const url = isRegisterMode ? `${API_BASE}/auth/register` : `${API_BASE}/auth/login`;
    const body = {
        username,
        password
    };
    
    if (isRegisterMode) {
        body.student_name = studentName || username;
        // 如果原本是訪客模式，把當前的 STUDENT_ID 傳過去進行綁定升級
        body.student_id = STUDENT_ID;
    }
    
    try {
        if (els.btnAuthSubmit) els.btnAuthSubmit.disabled = true;
        
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const json = await res.json();
        
        if (json.status === 'success') {
            const data = json.data;
            localStorage.setItem('studyagent_token', data.token);
            localStorage.setItem('studyagent_username', data.username);
            localStorage.setItem('studyagent_student_id', data.student_id);
            
            // 登入成功，關閉彈窗並刷新頁面以完全重置狀態
            closeAuthModal();
            window.location.reload();
        } else {
            showAuthError(json.error?.message || '驗證失敗，請稍後重試');
        }
    } catch (err) {
        console.error('Auth 請求出錯:', err);
        showAuthError('無法連線至伺服器');
    } finally {
        if (els.btnAuthSubmit) els.btnAuthSubmit.disabled = false;
    }
}

function showAuthError(msg) {
    if (els.authErrorMsg) {
        els.authErrorMsg.innerText = `⚠️ ${msg}`;
        els.authErrorMsg.style.display = 'flex';
    }
}

function handleLogout() {
    if (confirm('確定要登出嗎？登出後將返回訪客帳號模式。')) {
        localStorage.removeItem('studyagent_token');
        localStorage.removeItem('studyagent_username');
        // 登出後自動生成新的訪客 UUID
        localStorage.setItem('studyagent_student_id', crypto.randomUUID());
        window.location.reload();
    }
}
