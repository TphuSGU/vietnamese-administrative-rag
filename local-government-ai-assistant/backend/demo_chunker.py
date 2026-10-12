#!/usr/bin/env python3
"""
Demo script to showcase SemanticChunker with Vietnamese government document.

Run with: python demo_chunker.py
"""
from datetime import datetime
from app.models.data_models import Document
from app.rag.ingestion.chunker import SemanticChunker


def main():
    # Sample Vietnamese government document
    sample_document = """Chương I: QUY ĐỊNH CHUNG

Điều 1: Phạm vi điều chỉnh

Văn bản này quy định về thủ tục hành chính trong lĩnh vực đăng ký hộ khẩu, cư trú trên địa bàn thành phố Hồ Chí Minh. Văn bản áp dụng cho tất cả công dân Việt Nam thường trú, tạm trú tại thành phố và người nước ngoài cư trú hợp pháp trên địa bàn thành phố.

Điều 2: Đối tượng áp dụng

Văn bản này áp dụng cho các đối tượng sau đây: công dân Việt Nam thường trú tại thành phố Hồ Chí Minh, công dân Việt Nam tạm trú tại thành phố, người nước ngoài được cấp thẻ tạm trú hoặc thẻ thường trú, và các tổ chức, cá nhân có liên quan đến việc quản lý hộ khẩu, cư trú trên địa bàn.

Chương II: THỦ TỤC ĐĂNG KÝ HỘ KHẨU

Điều 3: Hồ sơ đăng ký hộ khẩu thường trú

Hồ sơ đăng ký hộ khẩu thường trú bao gồm các giấy tờ sau: đơn đăng ký thường trú theo mẫu quy định, bản sao giấy tờ tùy thân có dán ảnh, giấy xác nhận về nơi cư trú do chính quyền địa phương nơi đăng ký cấp, và các giấy tờ khác theo quy định của pháp luật hiện hành về đăng ký và quản lý cư trú.

Điều 4: Trình tự thực hiện đăng ký

Bước 1: Người đăng ký nộp hồ sơ tại bộ phận tiếp nhận và trả kết quả của Ủy ban nhân dân phường, xã nơi đăng ký thường trú. Bước 2: Cán bộ tiếp nhận kiểm tra tính đầy đủ và hợp lệ của hồ sơ, nếu hồ sơ chưa đầy đủ hoặc chưa hợp lệ thì hướng dẫn người nộp hồ sơ bổ sung, hoàn thiện. Bước 3: Sau khi nhận đủ hồ sơ hợp lệ, cơ quan có thẩm quyền tiến hành thẩm định và cấp giấy chứng nhận đăng ký thường trú trong thời hạn không quá 10 ngày làm việc kể từ ngày nhận đủ hồ sơ hợp lệ.

Điều 5: Phí và lệ phí

Việc đăng ký hộ khẩu thường trú phải nộp phí và lệ phí theo quy định của pháp luật hiện hành về phí và lệ phí. Mức thu phí và lệ phí được quy định cụ thể tại Thông tư hướng dẫn của Bộ Tài chính và được niêm yết công khai tại nơi tiếp nhận hồ sơ."""

    # Create Document object
    doc = Document(
        id="demo-gov-doc-001",
        text=sample_document,
        filename="quy_dinh_ho_khau_hcm.txt",
        file_size=len(sample_document),
        upload_timestamp=datetime.utcnow(),
        format="txt"
    )
    
    # Initialize chunker
    chunker = SemanticChunker()
    
    # Chunk the document
    print("=" * 80)
    print("VIETNAMESE GOVERNMENT DOCUMENT CHUNKING DEMO")
    print("=" * 80)
    print(f"\nDocument ID: {doc.id}")
    print(f"Document Size: {doc.file_size} characters")
    print(f"Document Format: {doc.format}")
    print("\n" + "-" * 80)
    
    chunks = chunker.chunk_document(doc)
    
    print(f"\n✅ Document chunked successfully!")
    print(f"📊 Total chunks created: {len(chunks)}")
    print(f"📏 Chunk size range: {chunker.min_size}-{chunker.max_size} characters")
    print("\n" + "=" * 80)
    print("CHUNK DETAILS")
    print("=" * 80)
    
    for i, chunk in enumerate(chunks):
        print(f"\n{'─' * 80}")
        print(f"CHUNK #{chunk.chunk_index}")
        print(f"{'─' * 80}")
        print(f"📄 Document ID: {chunk.document_id}")
        print(f"📑 Heading Context: {chunk.heading_context or '(No heading)'}")
        print(f"📏 Length: {chunk.length} characters")
        print(f"📍 Position: chars {chunk.char_start}-{chunk.char_end}")
        print(f"\n📝 Content Preview (first 200 chars):")
        print(f"{chunk.text[:200]}{'...' if len(chunk.text) > 200 else ''}")
        print()
    
    # Statistics
    print("=" * 80)
    print("STATISTICS")
    print("=" * 80)
    
    total_length = sum(c.length for c in chunks)
    avg_length = total_length / len(chunks) if chunks else 0
    min_length = min(c.length for c in chunks) if chunks else 0
    max_length = max(c.length for c in chunks) if chunks else 0
    
    # Count chunks with headings
    chunks_with_headings = sum(1 for c in chunks if c.heading_context)
    
    # Count heading types
    dieu_count = sum(1 for c in chunks if c.heading_context and "Điều" in c.heading_context)
    chuong_count = sum(1 for c in chunks if c.heading_context and "Chương" in c.heading_context)
    
    print(f"\n📊 Total text processed: {total_length} characters")
    print(f"📊 Average chunk size: {avg_length:.1f} characters")
    print(f"📊 Smallest chunk: {min_length} characters")
    print(f"📊 Largest chunk: {max_length} characters")
    print(f"\n🏷️  Chunks with heading context: {chunks_with_headings}/{len(chunks)}")
    print(f"🏷️  'Chương' headings detected: {chuong_count}")
    print(f"🏷️  'Điều' headings detected: {dieu_count}")
    
    print("\n" + "=" * 80)
    print("✨ Demo completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()
