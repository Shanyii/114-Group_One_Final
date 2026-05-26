import os
from pathlib import Path
from .base import BaseAgent

class DocumentReaderAgent(BaseAgent):
    """
    DocumentReaderAgent: Responsible for reading and parsing PDF/PPT lecture files.
    Input: Path to a lecture file.
    Output: Raw text content extracted from the file.
    """
    def __init__(self):
        super().__init__()
        # Predefined mock data for testing so Jing-en can test TF-IDF lecture immediately
        self.mock_slides = {
            "nlp_chapter3.pdf": """自然語言處理 (Natural Language Processing)
第三章：詞頻與向量空間模型 (Vector Space Models)

第1頁：
本章主題：資訊檢索與文本向量化。如何將文字轉換為機器可以理解的數字？

第5頁：
詞頻 (Term Frequency, TF)
- 定義：一個詞彙在單一文件中出現的頻率。
- 公式：
  TF(t, d) = f_t,d / sum_t'(f_t',d)
  其中 f_t,d 代表詞彙 t 在文件 d 中的出現次數。分母是該文件所有詞彙的出現次數總和。
- 概念：在單一文件中出現越多次的詞，代表在該文件中的重要性可能越高。

第12頁：
逆文件頻率 (Inverse Document Frequency, IDF)
- 定義：用來評估一個詞彙在所有文件集合中具有多少資訊量。如果一個詞在所有文件中都出現（例如：的、是、and），它的區別力就很低。
- 公式：
  IDF(t, D) = log( N / |{d in D : t in d}| )
  其中 N 是文件集合中的總文件數。分母是出現過詞彙 t 的文件數量。
- 概念：如果一個詞在很少的文件中出現，代表它具有很高的獨特性與代表性，IDF 值就會很大。

第15頁：
TF-IDF 權重 (TF-IDF Weight)
- 公式：
  TF-IDF(t, d, D) = TF(t, d) * IDF(t, D)
- 概念：結合 TF 與 IDF，同時考慮詞彙在單一文件中的重要性與在整個文件庫中的代表性。這是搜尋引擎與文本分類最經典的基礎特徵。
""",
            "nlp_chapter4.pdf": """自然語言處理 (Natural Language Processing)
第四章：機率上下文無關文法 (PCFG)

第1頁：
本章主題：句法分析 (Syntactic Parsing)。如何分析句子的語法結構？

第10頁：
上下文無關文法 (Context-Free Grammar, CFG)
- 定義：一種描述語言句法結構的數學系統。由非終端符號 (Non-terminals, 如 S, NP, VP) 與終端符號 (Terminals, 如單字) 組成。
- 規則範例：
  S -> NP VP
  NP -> Det N

第20頁：
機率上下文無關文法 (Probabilistic CFG, PCFG)
- 定義：為 CFG 的每條規則賦予一個機率值 P，使得所有相同左側非終端符號的規則機率總和為 1。
- 規則與機率範例：
  S -> NP VP  [1.0]
  NP -> Det N [0.7]
  NP -> Pronoun [0.3]
- 應用：用來解決歧義句子的句法分析問題。機率最高的語法樹即為最合理的句法結構。
"""
        }

    def read_document(self, filepath: str) -> str:
        """
        Reads a document. If it matches a mocked filename, it returns mock slide content.
        Otherwise, if it is a text or markdown file, it reads it from the filesystem.
        """
        path = Path(filepath)
        filename_lower = path.name.lower()
        
        # Check mock database first
        if filename_lower in self.mock_slides:
            return self.mock_slides[filename_lower]
        
        # Check if actual file exists
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}. Available mock files for testing: {list(self.mock_slides.keys())}")
        
        # Read plain text or markdown files
        if path.suffix.lower() in [".txt", ".md"]:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return f"[DocumentReaderAgent] 已讀取非純文字檔案 {path.name}，但由於尚未接上組員 PDF/PPT 解析器，暫時無法提取內容。"
