"""
RAG 效能與品質評估 CLI 工具。
用於單獨測試講義解析、智慧切分、ChromaDB 向量庫索引與 RAG 檢索效果。

使用方式：
    # 智慧解析與切分講義，並建立索引
    python test_rag_pipeline.py --file path/to/lecture.pdf

    # 針對已索引的文件進行測試檢索
    python test_rag_pipeline.py --doc_id <DOCUMENT_UUID> --query "什麼是 TF-IDF？"
"""

import argparse
import asyncio
import os
import sys
import time
import uuid

# 確保可以 import backend 下的模組
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import get_settings
from core.llm_client import get_llm_client
from repositories.vector_repo import get_vector_repo
from tools.document_parser import DocumentParser
from tools.rag_retriever import RAGRetriever


async def run_pipeline(args):
    settings = get_settings()
    llm_client = get_llm_client()
    vector_repo = get_vector_repo()
    parser = DocumentParser()
    retriever = RAGRetriever(vector_repo, llm_client)

    print("=" * 60)
    print("📊 RAG 智慧切分與檢索評估工具")
    print(f"LLM 供應商: {settings.llm_provider}")
    print(f"ChromaDB 目錄: {settings.chroma_db_dir}")
    print(f"預設 Chunk Size: {settings.chunk_size} | Overlap: {settings.chunk_overlap}")
    print("=" * 60)

    document_id = args.doc_id
    student_id = args.student_id or str(uuid.uuid4())

    if args.file:
        file_path = args.file
        if not os.path.exists(file_path):
            print(f"❌ 錯誤：找不到檔案 {file_path}")
            return

        filename = os.path.basename(file_path)
        print(f"📖 正在讀取並解析講義：{filename} ...")
        
        # 判斷 MIME Type
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext == "pdf":
            content_type = "application/pdf"
        elif ext in ["ppt", "pptx"]:
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        else:
            print(f"❌ 錯誤：不支援的檔案格式 .{ext}")
            return

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        # Step 1: 解析文件並寫入 SQLite
        start_time = time.time()
        try:
            document_id = await parser.save_and_parse(
                file_bytes=file_bytes,
                filename=filename,
                student_id=student_id,
                content_type=content_type
            )
            print(f"✅ 1. 解析完成並寫入 SQLite！")
            print(f"   Document ID: {document_id}")
            print(f"   耗時: {(time.time() - start_time) * 1000:.1f} ms")
        except Exception as e:
            print(f"❌ 解析失敗：{e}")
            return

        # Step 2: 取得智慧切分的 Chunks
        print("\n✂️ 2. 正在進行智慧遞迴切分與頁碼關聯...")
        chunks = await parser.get_chunks(document_id)
        print(f"✅ 切分完成！共生成 {len(chunks)} 個 Chunks。")

        # 打印 Chunks 分佈與預覽
        print("-" * 60)
        print(f"{'Index':<6} | {'Page':<6} | {'Length':<8} | {'Preview':<40}")
        print("-" * 60)
        for i, c in enumerate(chunks[:15]):  # 最多印出前 15 個
            text_preview = c["text"].replace("\n", " ")[:35] + "..."
            print(f"{i:<6} | {c['page_num']:<6} | {len(c['text']):<8} | {text_preview}")
        if len(chunks) > 15:
            print(f"... 以及其他 {len(chunks) - 15} 個 Chunks ...")
        print("-" * 60)

        # Step 3: 建立 ChromaDB 向量索引
        print("\n💾 3. 正在建立 ChromaDB 向量索引...")
        start_time = time.time()
        try:
            indexed_count = await vector_repo.index_document(document_id, student_id, chunks)
            print(f"✅ ChromaDB 索引建立成功！共寫入 {indexed_count} 筆向量。")
            print(f"   耗時: {(time.time() - start_time) * 1000:.1f} ms")
        except Exception as e:
            print(f"❌ 建立索引失敗：{e}")
            return

    # Step 4: 測試查詢
    if args.query:
        if not document_id:
            print("\n❌ 錯誤：若要進行查詢，請指定 --file 或 --doc_id 以限定範圍。")
            return

        print(f"\n🔍 4. 正在執行 RAG 檢索...")
        print(f"   使用者問題: \"{args.query}\"")
        
        start_time = time.time()
        try:
            passages = await retriever.retrieve(
                instruction=args.query,
                document_id=document_id,
                top_k=args.top_k
            )
            duration_ms = (time.time() - start_time) * 1000
            print(f"✅ 檢索完成！共召回 {len(passages)} 個相關段落（耗時 {duration_ms:.1f} ms）：")

            for idx, p in enumerate(passages, 1):
                print("\n" + "=" * 50)
                print(f"📌 段落 {idx} | 相似度分數: {p['score']:.4f}")
                print(f"   來源頁碼: 第 {p['page_num']} 頁/張投影片")
                print(f"   Chunk Index: {p['chunk_index']}")
                print("-" * 50)
                print(p["text"])
            print("=" * 50)

        except Exception as e:
            print(f"❌ RAG 檢索失敗：{e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG 智慧切分與檢索評估工具")
    parser.add_argument("--file", type=str, help="本地 PDF 或 PPTX 檔案路徑")
    parser.add_argument("--doc_id", type=str, help="已存在資料庫的文件 UUID")
    parser.add_argument("--query", type=str, help="測試用的檢索查詢問題")
    parser.add_argument("--top_k", type=int, default=3, help="檢索返回的段落數 (預設: 3)")
    parser.add_argument("--student_id", type=str, help="測試用的學生 UUID")

    args = parser.parse_args()

    if not args.file and not args.doc_id:
        parser.print_help()
        sys.exit(0)

    # 執行非同步 pipeline
    asyncio.run(run_pipeline(args))
