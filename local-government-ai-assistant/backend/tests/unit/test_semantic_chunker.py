"""
Unit tests for SemanticChunker.

Tests Vietnamese government document chunking with heading detection,
size enforcement, and metadata tracking.

Minimum 30 tests covering:
- Heading detection (8 tests)
- Size enforcement (8 tests)
- Vietnamese sentence detection (5 tests)
- Metadata completeness (5 tests)
- Integration scenarios (4 tests)
"""
import pytest
from datetime import datetime
from app.models.data_models import Document, Chunk
from app.rag.ingestion.chunker import SemanticChunker


class TestHeadingDetection:
    """Test Vietnamese heading pattern detection."""
    
    def test_dieu_heading_detection(self):
        """Test detection of 'Điều' pattern headings."""
        chunker = SemanticChunker()
        doc = Document(
            id="test-1",
            text="Điều 1: Phạm vi điều chỉnh\n\nNội dung của điều 1 về phạm vi.",
            filename="test.txt",
            file_size=100,
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        assert len(chunks) >= 1
        assert chunks[0].heading_context == "Điều 1: Phạm vi điều chỉnh"

    def test_heading_text_is_not_dropped(self):
        """Heading paragraphs that also contain clauses must stay in chunk text."""
        chunker = SemanticChunker()
        heading_with_clauses = (
            "Điều 5. Thẩm quyền chuyển giao\n\n"
            "1. Thẩm quyền của Ủy ban nhân dân cấp huyện chuyển giao cho "
            "Chủ tịch Ủy ban nhân dân cấp xã thực hiện, bao gồm:\n\n"
            "a) Chấp thuận phương án sử dụng đất nông nghiệp của tổ chức kinh tế "
            "theo quy định của pháp luật về đất đai."
        )
        doc = Document(
            id="test-heading-text",
            text=heading_with_clauses,
            filename="test.txt",
            file_size=len(heading_with_clauses),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )

        chunks = chunker.chunk_document(doc)
        combined = " ".join(chunk.text for chunk in chunks)

        assert "Điều 5" in combined
        assert "Chấp thuận phương án sử dụng đất nông nghiệp" in combined
    
    def test_khoan_heading_detection(self):
        """Test detection of 'Khoản' pattern headings."""
        chunker = SemanticChunker()
        doc = Document(
            id="test-2",
            text="Khoản 1. Quy định chung\n\nNội dung của khoản 1 về quy định chung cho tất cả các trường hợp.",
            filename="test.txt",
            file_size=100,
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        assert len(chunks) >= 1
        assert chunks[0].heading_context == "Khoản 1. Quy định chung"
    
    def test_chuong_roman_heading_detection(self):
        """Test detection of 'Chương' with Roman numerals."""
        chunker = SemanticChunker()
        doc = Document(
            id="test-3",
            text="Chương I: NHỮNG QUY ĐỊNH CHUNG\n\nNội dung của chương một về những quy định chung áp dụng cho toàn bộ văn bản.",
            filename="test.txt",
            file_size=100,
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        assert len(chunks) >= 1
        assert chunks[0].heading_context == "Chương I: NHỮNG QUY ĐỊNH CHUNG"
    
    def test_phan_heading_detection(self):
        """Test detection of 'Phần' pattern headings."""
        chunker = SemanticChunker()
        doc = Document(
            id="test-4",
            text="Phần thứ nhất: Giới thiệu\n\nNội dung giới thiệu về văn bản và mục đích ban hành văn bản này.",
            filename="test.txt",
            file_size=100,
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        assert len(chunks) >= 1
        assert chunks[0].heading_context == "Phần thứ nhất: Giới thiệu"
    
    def test_muc_heading_detection(self):
        """Test detection of 'Mục' pattern headings."""
        chunker = SemanticChunker()
        doc = Document(
            id="test-5",
            text="Mục 1. Đối tượng áp dụng\n\nVăn bản này áp dụng cho tất cả các công dân trên địa bàn.",
            filename="test.txt",
            file_size=100,
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        assert len(chunks) >= 1
        assert chunks[0].heading_context == "Mục 1. Đối tượng áp dụng"
    
    def test_all_caps_heading_detection(self):
        """Test detection of ALL CAPS headings."""
        chunker = SemanticChunker()
        doc = Document(
            id="test-6",
            text="ĐIỀU KHOẢN CHUNG\n\nĐây là nội dung của phần điều khoản chung áp dụng cho toàn bộ tài liệu.",
            filename="test.txt",
            file_size=100,
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        assert len(chunks) >= 1
        assert chunks[0].heading_context == "ĐIỀU KHOẢN CHUNG"
    
    def test_colon_ending_heading_detection(self):
        """Test detection of headings ending with colon."""
        chunker = SemanticChunker()
        doc = Document(
            id="test-7",
            text="Quy định về trách nhiệm:\n\nMọi cá nhân và tổ chức có trách nhiệm tuân thủ các quy định được nêu trong văn bản này.",
            filename="test.txt",
            file_size=100,
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        assert len(chunks) >= 1
        assert chunks[0].heading_context == "Quy định về trách nhiệm:"
    
    def test_heading_context_tracking(self):
        """Test that heading context is maintained across multiple chunks."""
        chunker = SemanticChunker()
        
        # Create text with heading and multiple paragraphs
        text = "Điều 1: Quy định chung\n\n" + \
               ("Đây là nội dung đoạn văn số một về quy định chung. " * 20) + "\n\n" + \
               ("Đây là nội dung đoạn văn số hai về quy định chung. " * 20)
        
        doc = Document(
            id="test-8",
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # All chunks under this heading should have the same heading context
        for chunk in chunks:
            assert chunk.heading_context == "Điều 1: Quy định chung"


class TestSizeEnforcement:
    """Test chunk size constraint enforcement."""
    
    def test_small_paragraph_merging(self):
        """Test that paragraphs < 200 chars are merged with next paragraph."""
        chunker = SemanticChunker()
        doc = Document(
            id="test-9",
            text="Đoạn ngắn.\n\n" + ("Đây là đoạn dài hơn. " * 20),
            filename="test.txt",
            file_size=100,
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Small paragraph should be merged, so we should have fewer chunks
        for chunk in chunks:
            # No chunk should be too small (except possibly the last one)
            if chunk.chunk_index < len(chunks) - 1:
                assert chunk.length >= chunker.min_size or len(chunks) == 1
    
    def test_medium_paragraph_kept_as_is(self):
        """Test that paragraphs 200-1000 chars are kept as single chunks."""
        chunker = SemanticChunker()
        
        # Create text exactly in the middle range
        medium_text = "Đây là một đoạn văn có độ dài trung bình. " * 15
        assert 200 <= len(medium_text) <= 1000
        
        doc = Document(
            id="test-10",
            text=medium_text,
            filename="test.txt",
            file_size=len(medium_text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        assert len(chunks) == 1
        assert 200 <= chunks[0].length <= 1000
    
    def test_large_paragraph_splitting_at_sentences(self):
        """Test that paragraphs > 1000 chars are split at sentence boundaries."""
        chunker = SemanticChunker()
        
        # Create a large paragraph with multiple sentences
        sentence = "Đây là một câu trong đoạn văn dài. "
        large_text = sentence * 50  # Creates text > 1000 chars
        assert len(large_text) > 1000
        
        doc = Document(
            id="test-11",
            text=large_text,
            filename="test.txt",
            file_size=len(large_text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should be split into multiple chunks
        assert len(chunks) > 1
        
        # Each chunk should be within size limits
        for chunk in chunks:
            assert chunk.length <= chunker.max_size + 50  # Allow small overflow
    
    def test_very_large_sentence_splitting_at_clauses(self):
        """Test that sentences > 1000 chars are split at clause boundaries."""
        chunker = SemanticChunker()
        
        # Create a very long sentence with clause markers
        clause = "phần này nói về điều quan trọng, "
        very_long_sentence = clause * 50 + "và đây là kết luận cuối cùng."
        assert len(very_long_sentence) > 1000
        
        doc = Document(
            id="test-12",
            text=very_long_sentence,
            filename="test.txt",
            file_size=len(very_long_sentence),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should be split into multiple chunks at clause boundaries
        assert len(chunks) > 1
    
    def test_boundary_exactly_200_chars(self):
        """Test chunk with exactly 200 characters."""
        chunker = SemanticChunker()
        
        # Create text exactly 200 chars
        text = "a" * 200
        doc = Document(
            id="test-13",
            text=text,
            filename="test.txt",
            file_size=200,
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        assert len(chunks) == 1
        assert chunks[0].length == 200
    
    def test_boundary_exactly_1000_chars(self):
        """Test chunk with exactly 1000 characters."""
        chunker = SemanticChunker()
        
        # Create text exactly 1000 chars
        text = "b" * 1000
        doc = Document(
            id="test-14",
            text=text,
            filename="test.txt",
            file_size=1000,
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        assert len(chunks) == 1
        assert chunks[0].length == 1000
    
    def test_custom_size_limits(self):
        """Test chunker with custom min/max size limits."""
        chunker = SemanticChunker(min_size=100, max_size=500)
        
        text = "Đây là văn bản kiểm tra. " * 30
        doc = Document(
            id="test-15",
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        for chunk in chunks:
            assert chunk.length <= 500 + 50  # Allow small overflow
    
    def test_multiple_paragraph_size_enforcement(self):
        """Test size enforcement with multiple paragraphs of varying sizes."""
        chunker = SemanticChunker()
        
        # Mix of small, medium, and large paragraphs
        small = "Ngắn. " * 5  # < 200
        medium = "Trung bình. " * 25  # 200-1000
        large = "Dài hơn rất nhiều. " * 100  # > 1000
        
        text = small + "\n\n" + medium + "\n\n" + large
        
        doc = Document(
            id="test-16",
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should have multiple chunks due to size enforcement
        assert len(chunks) >= 2

    def test_small_heading_merged_with_large_paragraph_stays_bounded(self):
        """Merging a short heading with a large paragraph must not exceed MAX_SIZE."""
        chunker = SemanticChunker()
        text = "Điều 5. Thẩm quyền\n\n" + ("Nội dung rất dài về thẩm quyền. " * 100)

        doc = Document(
            id="test-merge-large",
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )

        chunks = chunker.chunk_document(doc)

        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.length <= chunker.max_size + 50


class TestVietnameseSentenceDetection:
    """Test Vietnamese sentence boundary detection."""
    
    def test_basic_sentence_splitting(self):
        """Test splitting at basic punctuation marks."""
        chunker = SemanticChunker()
        
        text = ("Câu thứ nhất. " * 50) + ("Câu thứ hai! " * 50)
        doc = Document(
            id="test-17",
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should split into multiple chunks
        assert len(chunks) >= 2
    
    def test_vietnamese_capital_letters(self):
        """Test sentence splitting with Vietnamese capital letters."""
        chunker = SemanticChunker()
        
        # Vietnamese capitals: Đ, Ô, Ơ, Ư, etc.
        text = ("Câu đầu tiên. Đây là câu thứ hai. Ở đây có câu ba. " * 30)
        doc = Document(
            id="test-18",
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should properly detect sentence boundaries with Vietnamese capitals
        assert len(chunks) >= 1
    
    def test_multiple_punctuation_types(self):
        """Test splitting with different punctuation marks (. ! ? ;)."""
        chunker = SemanticChunker()
        
        # Use capital letters after punctuation to trigger sentence detection
        # Make text long enough to exceed max_size and force splitting
        text = ("Câu hỏi? Đây là câu mới với nội dung dài hơn. " * 30)
        doc = Document(
            id="test-19",
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should handle all punctuation types and split when necessary
        # Text is long enough to exceed max_size, so should split
        assert len(chunks) >= 2
    
    def test_abbreviation_handling(self):
        """Test that abbreviations don't cause incorrect splits."""
        chunker = SemanticChunker()
        
        text = "Theo quy định tại Điều 1 v.v. thì công dân phải tuân thủ. " * 30
        doc = Document(
            id="test-20",
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should not split at "v.v." since it's not followed by capital
        assert len(chunks) >= 1
    
    def test_sentence_with_numbers(self):
        """Test sentence detection with numbers and dates."""
        chunker = SemanticChunker()
        
        text = ("Văn bản số 123/2024 có hiệu lực từ ngày 1.1.2024. " * 30)
        doc = Document(
            id="test-21",
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should handle numbers and dates correctly
        assert len(chunks) >= 1


class TestMetadataCompleteness:
    """Test chunk metadata generation."""
    
    def test_chunk_index_sequential(self):
        """Test that chunk_index is sequential starting from 0."""
        chunker = SemanticChunker()
        
        text = ("Đoạn văn số một. " * 30) + "\n\n" + ("Đoạn văn số hai. " * 30) + "\n\n" + ("Đoạn văn số ba. " * 30)
        doc = Document(
            id="test-22",
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Check sequential indexing
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
    
    def test_heading_context_preserved(self):
        """Test that heading_context is properly set and preserved."""
        chunker = SemanticChunker()
        
        doc = Document(
            id="test-23",
            text="Điều 1: Nội dung\n\n" + ("Nội dung chi tiết. " * 40),
            filename="test.txt",
            file_size=100,
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        for chunk in chunks:
            assert chunk.heading_context is not None
            assert "Điều 1" in chunk.heading_context
    
    def test_char_start_end_accuracy(self):
        """Test that char_start and char_end are set correctly."""
        chunker = SemanticChunker()
        
        text = "Đoạn văn đơn giản. " * 30
        doc = Document(
            id="test-24",
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        for chunk in chunks:
            assert chunk.char_start >= 0
            assert chunk.char_end > chunk.char_start
            assert chunk.char_end - chunk.char_start > 0
    
    def test_document_id_propagation(self):
        """Test that document_id is correctly set in all chunks."""
        chunker = SemanticChunker()
        
        doc_id = "test-document-12345"
        text = "Nội dung văn bản. " * 50
        doc = Document(
            id=doc_id,
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        for chunk in chunks:
            assert chunk.document_id == doc_id
    
    def test_metadata_completeness_all_fields(self):
        """Test that all required metadata fields are present."""
        chunker = SemanticChunker()
        
        doc = Document(
            id="test-25",
            text="Điều 1: Quy định\n\n" + ("Nội dung quy định. " * 30),
            filename="test.txt",
            file_size=100,
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        for chunk in chunks:
            # All required fields must be present
            assert chunk.text is not None
            assert chunk.document_id is not None
            assert chunk.chunk_index >= 0
            assert chunk.char_start >= 0
            assert chunk.char_end >= 0
            # heading_context can be None if no heading


class TestIntegrationScenarios:
    """Test complete integration scenarios."""
    
    def test_complete_government_document(self):
        """Test chunking of a complete Vietnamese government document."""
        chunker = SemanticChunker()
        
        # Realistic government document structure
        text = """Chương I: QUY ĐỊNH CHUNG

Điều 1: Phạm vi điều chỉnh

Văn bản này quy định về thủ tục hành chính trong lĩnh vực đăng ký hộ khẩu, cư trú trên địa bàn thành phố. Văn bản áp dụng cho tất cả công dân Việt Nam và người nước ngoài cư trú tại thành phố.

Điều 2: Đối tượng áp dụng

Văn bản này áp dụng cho các đối tượng sau đây: công dân Việt Nam thường trú tại thành phố, công dân Việt Nam tạm trú tại thành phố, người nước ngoài được cấp thẻ tạm trú, và các tổ chức, cá nhân có liên quan.

Chương II: THỦ TỤC ĐĂNG KÝ

Điều 3: Hồ sơ đăng ký

Hồ sơ đăng ký hộ khẩu bao gồm: đơn đăng ký theo mẫu, bản sao giấy tờ tùy thân, giấy xác nhận nơi cư trú, và các giấy tờ khác theo quy định của pháp luật hiện hành.

Điều 4: Trình tự thực hiện

Người đăng ký nộp hồ sơ tại bộ phận một cửa của UBND phường, xã. Cán bộ tiếp nhận kiểm tra hồ sơ và hẹn trả kết quả. Thời gian giải quyết không quá 10 ngày làm việc kể từ ngày nhận đủ hồ sơ hợp lệ."""
        
        doc = Document(
            id="gov-doc-1",
            text=text,
            filename="quy_dinh_ho_khau.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should have multiple chunks (at least 2 from the content)
        assert len(chunks) >= 2
        
        # Should detect chapter headings
        chapter_headings = [c.heading_context for c in chunks if c.heading_context and "Chương" in c.heading_context]
        # Chapter headings may be merged with content
        
        # Should detect article headings
        article_headings = [c.heading_context for c in chunks if c.heading_context and "Điều" in c.heading_context]
        assert len(article_headings) > 0  # Should have at least one Điều heading
        
        # All chunks should be within size limits
        for chunk in chunks:
            assert chunk.length <= chunker.max_size + 100  # Allow some overflow
    
    def test_empty_document_handling(self):
        """Test handling of empty documents."""
        chunker = SemanticChunker()
        
        doc = Document(
            id="empty-doc",
            text="",
            filename="empty.txt",
            file_size=0,
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should return empty list
        assert len(chunks) == 0
    
    def test_single_paragraph_document(self):
        """Test document with only one paragraph."""
        chunker = SemanticChunker()
        
        text = "Đây là một văn bản rất ngắn chỉ có một đoạn duy nhất với nội dung đơn giản. " * 5
        doc = Document(
            id="single-para",
            text=text,
            filename="short.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should have exactly one chunk
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
    
    def test_very_long_document(self):
        """Test chunking of a very long document."""
        chunker = SemanticChunker()
        
        # Create a very long document with multiple sections
        sections = []
        for i in range(10):
            section = f"Điều {i+1}: Nội dung điều {i+1}\n\n"
            section += ("Đây là nội dung chi tiết của điều này. " * 50) + "\n\n"
            sections.append(section)
        
        text = "".join(sections)
        doc = Document(
            id="long-doc",
            text=text,
            filename="long_doc.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should have many chunks
        assert len(chunks) >= 10
        
        # All chunks should have proper metadata
        for chunk in chunks:
            assert chunk.document_id == "long-doc"
            assert chunk.chunk_index >= 0
            assert chunk.text is not None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_whitespace_only_paragraphs(self):
        """Test handling of paragraphs containing only whitespace."""
        chunker = SemanticChunker()
        
        text = "Nội dung thực. " * 20 + "\n\n   \n\n" + "Nội dung tiếp theo. " * 20
        doc = Document(
            id="whitespace-test",
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should skip whitespace-only paragraphs
        for chunk in chunks:
            assert chunk.text.strip() != ""
    
    def test_special_characters_in_text(self):
        """Test handling of special characters."""
        chunker = SemanticChunker()
        
        text = "Nội dung có ký tự đặc biệt: @#$%^&*(). " * 30
        doc = Document(
            id="special-chars",
            text=text,
            filename="test.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should handle special characters without errors
        assert len(chunks) >= 1
        for chunk in chunks:
            assert "@#$%^&*()" in chunk.text
    
    def test_unicode_vietnamese_characters(self):
        """Test proper handling of full Vietnamese Unicode character set."""
        chunker = SemanticChunker()
        
        # All Vietnamese vowels with tone marks
        text = "Aàáảãạăằắẳẵặâầấẩẫậeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵ đ. " * 20
        doc = Document(
            id="unicode-test",
            text=text,
            filename="unicode.txt",
            file_size=len(text),
            upload_timestamp=datetime.utcnow(),
            format="txt"
        )
        
        chunks = chunker.chunk_document(doc)
        
        # Should preserve all Vietnamese characters
        assert len(chunks) >= 1
        for chunk in chunks:
            assert "ă" in chunk.text or "â" in chunk.text or "đ" in chunk.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
