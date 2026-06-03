from src.agents.document_reader_agent import DocumentReaderAgent

# Instantiate the DocumentReaderAgent to handle the actual parsing/reading
_document_reader = DocumentReaderAgent()

def read_document(filepath: str) -> str:
    """
    讀取並解析講義內容（PDF / PPT）。
    輸入：講義檔案路徑 (str)
    輸出：純文字內容 (str)
    觸發時機：使用者上傳講義時
    """
    return _document_reader.read_document(filepath)
