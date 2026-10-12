"""
Unit tests for TextCleaner component.

Tests Requirements 2.1-2.5:
- NFC normalization
- Whitespace normalization
- Diacritics preservation
- Control character removal
- Lowercase conversion
- Edge cases and idempotence
"""
import pytest
import unicodedata

from app.rag.ingestion.cleaner import TextCleaner


class TestTextCleanerBasic:
    """Basic functionality tests for TextCleaner."""
    
    def test_clean_empty_text(self):
        """Test cleaning empty text returns empty string."""
        cleaner = TextCleaner()
        result = cleaner.clean("")
        assert result == ""
    
    def test_clean_whitespace_only(self):
        """Test cleaning whitespace-only text returns empty string."""
        cleaner = TextCleaner()
        result = cleaner.clean("   \n\n   \t\t   ")
        assert result == ""
    
    def test_clean_simple_text(self):
        """Test cleaning simple Vietnamese text."""
        cleaner = TextCleaner()
        result = cleaner.clean("Xin chào Việt Nam")
        assert result == "xin chào việt nam"


class TestUnicodeNormalization:
    """Tests for Unicode NFC normalization (Requirement 2.1)."""
    
    def test_nfc_normalization_basic(self):
        """Test basic NFC normalization."""
        cleaner = TextCleaner()
        # Using composed form (already NFC)
        text = "Thủ tục đăng ký"
        result = cleaner.clean(text)
        # Should preserve Vietnamese characters
        assert "thủ tục đăng ký" == result
    
    def test_nfc_normalization_decomposed(self):
        """Test NFC normalization on decomposed Vietnamese text."""
        cleaner = TextCleaner()
        # Create decomposed form (NFD) manually
        text_nfd = unicodedata.normalize('NFD', "Thủ tục đăng ký")
        result = cleaner.clean(text_nfd)
        # Should be normalized to NFC (composed form) and lowercased
        expected = unicodedata.normalize('NFC', "thủ tục đăng ký")
        assert result == expected
    
    def test_nfc_idempotence(self):
        """Test Property 3: normalize(normalize(x)) == normalize(x)."""
        cleaner = TextCleaner()
        text = "Hướng dẫn thủ tục hành chính"
        result_once = cleaner.clean(text)
        result_twice = cleaner.clean(result_once)
        assert result_once == result_twice
    
    def test_nfc_all_vietnamese_diacritics(self):
        """Test NFC normalization preserves all Vietnamese diacritics."""
        cleaner = TextCleaner()
        # All Vietnamese vowels with tones
        text = "àáảãạ ằắẳẵặ ầấẩẫậ đ èéẻẽẹ ềếểễệ ìíỉĩị òóỏõọ ồốổỗộ ờớởỡợ ùúủũụ ừứửữự ỳýỷỹỵ"
        result = cleaner.clean(text)
        # All diacritics should be preserved (in lowercase)
        assert "àáảãạ ằắẳẵặ ầấẩẫậ đ èéẻẽẹ ềếểễệ ìíỉĩị òóỏõọ ồốổỗộ ờớởỡợ ùúủũụ ừứửữự ỳýỷỹỵ" == result


class TestWhitespaceNormalization:
    """Tests for whitespace normalization (Requirement 2.2)."""
    
    def test_collapse_multiple_spaces(self):
        """Test multiple spaces collapsed to single space."""
        cleaner = TextCleaner()
        result = cleaner.clean("Thủ    tục     đăng    ký")
        assert result == "thủ tục đăng ký"
    
    def test_preserve_paragraph_breaks(self):
        """Test paragraph breaks (double newlines) are preserved."""
        cleaner = TextCleaner()
        result = cleaner.clean("Đoạn một\n\nĐoạn hai")
        assert result == "đoạn một\n\nđoạn hai"
    
    def test_single_newline_becomes_space(self):
        """Test single newlines are converted to spaces."""
        cleaner = TextCleaner()
        result = cleaner.clean("Dòng một\nDòng hai")
        assert result == "dòng một dòng hai"
    
    def test_multiple_newlines_become_paragraph_break(self):
        """Test 3+ newlines become paragraph break (\\n\\n)."""
        cleaner = TextCleaner()
        result = cleaner.clean("Đoạn một\n\n\n\nĐoạn hai")
        assert result == "đoạn một\n\nđoạn hai"
    
    def test_leading_trailing_whitespace_removed(self):
        """Test leading and trailing whitespace is removed."""
        cleaner = TextCleaner()
        result = cleaner.clean("   Văn bản   ")
        assert result == "văn bản"
    
    def test_tabs_preserved_in_content(self):
        """Test tabs within content are preserved."""
        cleaner = TextCleaner()
        result = cleaner.clean("Mục 1:\tNội dung")
        assert "\t" in result
        assert result == "mục 1:\tnội dung"
    
    def test_complex_whitespace_mix(self):
        """Test complex mix of spaces, tabs, and newlines."""
        cleaner = TextCleaner()
        text = "  Tiêu đề  \n\n  Đoạn một   với  nhiều   khoảng  trắng.  \n\n  Đoạn hai.  "
        result = cleaner.clean(text)
        assert result == "tiêu đề\n\nđoạn một với nhiều khoảng trắng.\n\nđoạn hai."


class TestDiacriticsPreservation:
    """Tests for Vietnamese diacritics preservation (Requirement 2.3)."""
    
    def test_preserve_all_tones(self):
        """Test all 5 Vietnamese tones are preserved."""
        cleaner = TextCleaner()
        # Five tones: level (a), acute (á), grave (à), hook (ả), tilde (ã), dot below (ạ)
        text = "ma má mà mả mã mạ"
        result = cleaner.clean(text)
        assert result == "ma má mà mả mã mạ"
    
    def test_preserve_complex_diacritics(self):
        """Test complex Vietnamese vowels with diacritics."""
        cleaner = TextCleaner()
        text = "tôi thường ăn ở đây"
        result = cleaner.clean(text)
        assert result == "tôi thường ăn ở đây"
    
    def test_sample_government_text(self):
        """Test with realistic government document text."""
        cleaner = TextCleaner()
        text = "Thủ tục đăng ký hộ khẩu tại địa phương"
        result = cleaner.clean(text)
        assert result == "thủ tục đăng ký hộ khẩu tại địa phương"
        # Verify all diacritics preserved
        assert cleaner.verify_diacritics_preserved(text, result)
    
    def test_diacritics_with_uppercase(self):
        """Test diacritics preserved when converting uppercase to lowercase."""
        cleaner = TextCleaner()
        text = "THÀNH PHỐ HỒ CHÍ MINH"
        result = cleaner.clean(text)
        assert result == "thành phố hồ chí minh"
        assert cleaner.verify_diacritics_preserved(text, result)
    
    def test_mixed_case_diacritics(self):
        """Test mixed case Vietnamese text."""
        cleaner = TextCleaner()
        text = "Hướng DẪn THỦ tục"
        result = cleaner.clean(text)
        assert result == "hướng dẫn thủ tục"
        assert cleaner.verify_diacritics_preserved(text, result)


class TestControlCharacterRemoval:
    """Tests for control character removal (Requirement 2.4)."""
    
    def test_remove_null_bytes(self):
        """Test null bytes (\\x00) are removed."""
        cleaner = TextCleaner()
        result = cleaner.clean("Văn\x00bản")
        assert "\x00" not in result
        assert result == "văn bản"
    
    def test_preserve_newline(self):
        """Test single newlines are converted to spaces (not preserved)."""
        cleaner = TextCleaner()
        result = cleaner.clean("Dòng 1\nDòng 2")
        # Single newlines become spaces per requirement
        assert result == "dòng 1 dòng 2"
    
    def test_preserve_tab(self):
        """Test tab (\\t) is preserved."""
        cleaner = TextCleaner()
        result = cleaner.clean("Cột 1\tCột 2")
        assert "\t" in result
        assert result == "cột 1\tcột 2"
    
    def test_remove_bell_character(self):
        """Test bell character (\\x07) is removed."""
        cleaner = TextCleaner()
        result = cleaner.clean("Văn\x07bản")
        assert "\x07" not in result
        assert result == "văn bản"
    
    def test_remove_delete_character(self):
        """Test delete character (\\x7F) is removed."""
        cleaner = TextCleaner()
        result = cleaner.clean("Văn\x7Fbản")
        assert "\x7F" not in result
        assert result == "văn bản"
    
    def test_remove_multiple_control_chars(self):
        """Test multiple control characters are removed."""
        cleaner = TextCleaner()
        result = cleaner.clean("Văn\x01\x02\x03bản\x1F\x7F")
        # Should only contain printable chars (no control chars except \n, \t)
        assert result == "văn bản"
    
    def test_no_control_chars_in_output(self):
        """Test Property 6: Output has no control chars except \\n and \\t."""
        cleaner = TextCleaner()
        text = "Test\x00\x01\x02\x07\x08\x0B\x0C\x0E\x1F\x7FText"
        result = cleaner.clean(text)
        # Check no forbidden control characters
        for i in range(32):
            if i == ord('\n') or i == ord('\t'):
                continue  # These are allowed
            assert chr(i) not in result
        assert chr(127) not in result  # DEL character


class TestLowercaseConversion:
    """Tests for lowercase conversion (Requirement 2.5)."""
    
    def test_basic_lowercase(self):
        """Test basic uppercase to lowercase conversion."""
        cleaner = TextCleaner()
        result = cleaner.clean("HELLO WORLD")
        assert result == "hello world"
    
    def test_vietnamese_lowercase(self):
        """Test Vietnamese uppercase to lowercase."""
        cleaner = TextCleaner()
        result = cleaner.clean("VIỆT NAM")
        assert result == "việt nam"
    
    def test_mixed_case(self):
        """Test mixed case conversion."""
        cleaner = TextCleaner()
        result = cleaner.clean("Văn Bản Chính Quyền")
        assert result == "văn bản chính quyền"
    
    def test_uppercase_with_diacritics(self):
        """Test uppercase Vietnamese letters with diacritics."""
        cleaner = TextCleaner()
        result = cleaner.clean("HƯỚNG DẪN")
        assert result == "hướng dẫn"
    
    def test_no_uppercase_remains(self):
        """Test Property 7: No uppercase characters after conversion."""
        cleaner = TextCleaner()
        text = "HỘI ĐỒNG NHÂN DÂN Thành Phố"
        result = cleaner.clean(text)
        # Check no uppercase letters remain
        assert result == result.lower()
        assert result.isupper() is False


class TestEdgeCases:
    """Edge case tests."""
    
    def test_only_numbers(self):
        """Test text with only numbers."""
        cleaner = TextCleaner()
        result = cleaner.clean("12345")
        assert result == "12345"
    
    def test_only_punctuation(self):
        """Test text with only punctuation."""
        cleaner = TextCleaner()
        result = cleaner.clean(".,;:!?")
        assert result == ".,;:!?"
    
    def test_mixed_vietnamese_english(self):
        """Test mixed Vietnamese and English text."""
        cleaner = TextCleaner()
        result = cleaner.clean("Văn bản PDF document")
        assert result == "văn bản pdf document"
    
    def test_numbers_with_text(self):
        """Test numbers mixed with text."""
        cleaner = TextCleaner()
        result = cleaner.clean("Điều 123 của Luật")
        assert result == "điều 123 của luật"
    
    def test_special_chars_preserved(self):
        """Test special characters are preserved."""
        cleaner = TextCleaner()
        result = cleaner.clean("Giá: 1.000.000đ (50%)")
        assert result == "giá: 1.000.000đ (50%)"
    
    def test_very_long_text(self):
        """Test cleaning very long text."""
        cleaner = TextCleaner()
        text = "Văn bản " * 1000  # 8000 characters
        result = cleaner.clean(text)
        assert len(result) > 0
        assert result.startswith("văn bản")


class TestIntegration:
    """Integration tests for complete cleaning pipeline."""
    
    def test_complete_cleaning_pipeline(self):
        """Test all cleaning steps work together correctly."""
        cleaner = TextCleaner()
        # Complex text with all issues
        text = "  THÀNH  PHỐ  \x00HỒ  CHÍ  MINH  \n\n  Hướng  dẫn   thủ  tục  \x07\x1F  "
        result = cleaner.clean(text)
        # Should be: normalized, control chars removed, whitespace normalized, lowercased
        assert result == "thành phố hồ chí minh\n\nhướng dẫn thủ tục"
    
    def test_realistic_government_document(self):
        """Test with realistic government document text."""
        cleaner = TextCleaner()
        text = """
        THÀNH PHỐ HỒ CHÍ MINH
        
        HƯỚNG DẪN THỦ TỤC ĐĂNG KÝ HỘ KHẨU
        
        Căn cứ Luật Cư trú số 81/2006/QH11 ngày 29 tháng 11 năm 2006;
        Căn cứ Nghị định số 78/2007/NĐ-CP ngày 10 tháng 5 năm 2007.
        
        Điều 1: Đối tượng áp dụng
        Công dân Việt Nam cư trú tại địa phương.
        """
        result = cleaner.clean(text)
        
        # Verify key properties
        assert "thành phố hồ chí minh" in result
        assert "hướng dẫn thủ tục đăng ký hộ khẩu" in result
        assert "điều 1: đối tượng áp dụng" in result
        # Paragraph breaks preserved
        assert "\n\n" in result
        # All lowercase
        assert result == result.lower()
        # No extra spaces
        assert "  " not in result
    
    def test_idempotence_complete(self):
        """Test that cleaning twice produces same result as once."""
        cleaner = TextCleaner()
        text = "  HƯỚNG   DẪN\x00\n\nNỘI  DUNG  "
        result_once = cleaner.clean(text)
        result_twice = cleaner.clean(result_once)
        result_thrice = cleaner.clean(result_twice)
        
        assert result_once == result_twice
        assert result_twice == result_thrice
