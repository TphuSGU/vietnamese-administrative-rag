"""
Unit tests for InputValidator.

Tests Requirements 16.1-16.6 from requirements document.
"""
import pytest
from app.core.validators import InputValidator
from app.models.exceptions import ValidationError


class TestFileUploadValidation:
    """Test file upload validation (Requirements 16.1, 16.2)."""
    
    def test_valid_pdf_file(self):
        """Valid PDF file should pass validation."""
        InputValidator.validate_file_upload("document.pdf", 1024 * 1024)  # 1MB
    
    def test_valid_docx_file(self):
        """Valid DOCX file should pass validation."""
        InputValidator.validate_file_upload("document.docx", 5 * 1024 * 1024)  # 5MB
    
    def test_valid_txt_file(self):
        """Valid TXT file should pass validation."""
        InputValidator.validate_file_upload("document.txt", 100 * 1024)  # 100KB
    
    def test_empty_filename(self):
        """Empty filename should raise ValidationError."""
        with pytest.raises(ValidationError, match="Filename cannot be empty"):
            InputValidator.validate_file_upload("", 1024)
    
    def test_whitespace_filename(self):
        """Whitespace-only filename should raise ValidationError."""
        with pytest.raises(ValidationError, match="Filename cannot be empty"):
            InputValidator.validate_file_upload("   ", 1024)
    
    def test_unsupported_file_extension(self):
        """Unsupported file extension should raise ValidationError."""
        with pytest.raises(ValidationError, match="Unsupported file format"):
            InputValidator.validate_file_upload("document.exe", 1024)
    
    def test_unsupported_extension_case_insensitive(self):
        """File extension check should be case-insensitive."""
        # These should pass (case variations of supported formats)
        InputValidator.validate_file_upload("document.PDF", 1024)
        InputValidator.validate_file_upload("document.DOCX", 1024)
        InputValidator.validate_file_upload("document.TxT", 1024)
    
    def test_file_size_zero(self):
        """Zero file size should raise ValidationError."""
        with pytest.raises(ValidationError, match="File size must be greater than 0"):
            InputValidator.validate_file_upload("document.pdf", 0)
    
    def test_file_size_negative(self):
        """Negative file size should raise ValidationError."""
        with pytest.raises(ValidationError, match="File size must be greater than 0"):
            InputValidator.validate_file_upload("document.pdf", -100)
    
    def test_file_size_exceeds_limit(self):
        """File size exceeding limit should raise ValidationError."""
        max_size = 50 * 1024 * 1024  # 50MB
        oversized = max_size + 1
        with pytest.raises(ValidationError, match="exceeds maximum allowed size"):
            InputValidator.validate_file_upload("document.pdf", oversized)
    
    def test_file_size_at_limit(self):
        """File size exactly at limit should pass."""
        max_size = 50 * 1024 * 1024  # 50MB
        InputValidator.validate_file_upload("document.pdf", max_size)
    
    def test_descriptive_error_messages(self):
        """Error messages should be descriptive (Requirement 16.5)."""
        # Test unsupported format error message
        try:
            InputValidator.validate_file_upload("test.xyz", 1024)
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            error_msg = str(e)
            assert "Unsupported file format" in error_msg
            assert ".xyz" in error_msg
            assert "Supported formats" in error_msg
        
        # Test file size error message
        try:
            oversized = 100 * 1024 * 1024  # 100MB
            InputValidator.validate_file_upload("test.pdf", oversized)
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            error_msg = str(e)
            assert "exceeds maximum allowed size" in error_msg
            assert "MB" in error_msg


class TestQueryValidation:
    """Test query validation (Requirements 7.2, 16.3)."""
    
    def test_valid_query(self):
        """Valid query should pass validation."""
        InputValidator.validate_query("Thủ tục đăng ký kinh doanh như thế nào?")
    
    def test_valid_query_minimum_length(self):
        """Query at minimum length should pass."""
        query = "a" * 10  # Exactly 10 characters
        InputValidator.validate_query(query)
    
    def test_valid_query_maximum_length(self):
        """Query at maximum length should pass."""
        query = "a" * 500  # Exactly 500 characters
        InputValidator.validate_query(query)
    
    def test_query_none(self):
        """None query should raise ValidationError."""
        with pytest.raises(ValidationError, match="Query cannot be None"):
            InputValidator.validate_query(None)
    
    def test_query_empty_string(self):
        """Empty query should raise ValidationError."""
        with pytest.raises(ValidationError, match="Query cannot be empty"):
            InputValidator.validate_query("")
    
    def test_query_whitespace_only(self):
        """Whitespace-only query should raise ValidationError."""
        with pytest.raises(ValidationError, match="Query cannot be empty"):
            InputValidator.validate_query("   \n\t  ")
    
    def test_query_too_short(self):
        """Query shorter than minimum should raise ValidationError."""
        short_query = "abc"  # Less than 10 characters
        with pytest.raises(ValidationError, match="Query is too short"):
            InputValidator.validate_query(short_query)
    
    def test_query_too_long(self):
        """Query longer than maximum should raise ValidationError."""
        long_query = "a" * 501  # More than 500 characters
        with pytest.raises(ValidationError, match="Query is too long"):
            InputValidator.validate_query(long_query)
    
    def test_query_utf8_encoding(self):
        """Query with valid UTF-8 Vietnamese characters should pass."""
        vietnamese_query = "Điều kiện để được cấp giấy phép xây dựng là gì?"
        InputValidator.validate_query(vietnamese_query)
    
    def test_query_special_characters(self):
        """Query with special characters should pass if UTF-8."""
        query = "Thủ tục A, B & C - phần (1) [test]?"
        InputValidator.validate_query(query)
    
    def test_descriptive_query_error_messages(self):
        """Query error messages should be descriptive (Requirement 16.5)."""
        # Test too short
        try:
            InputValidator.validate_query("abc")
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            error_msg = str(e)
            assert "too short" in error_msg
            assert "characters" in error_msg
            assert "Minimum length" in error_msg
        
        # Test too long
        try:
            InputValidator.validate_query("a" * 501)
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            error_msg = str(e)
            assert "too long" in error_msg
            assert "characters" in error_msg
            assert "Maximum length" in error_msg


class TestKParameterValidation:
    """Test K parameter validation (Requirements 8.3, 16.4)."""
    
    def test_valid_k_minimum(self):
        """K at minimum value should pass."""
        InputValidator.validate_k_parameter(1)
    
    def test_valid_k_maximum(self):
        """K at maximum value should pass."""
        InputValidator.validate_k_parameter(20)
    
    def test_valid_k_middle(self):
        """K in middle of range should pass."""
        InputValidator.validate_k_parameter(5)
        InputValidator.validate_k_parameter(10)
    
    def test_k_below_minimum(self):
        """K below minimum should raise ValidationError."""
        with pytest.raises(ValidationError, match="must be between"):
            InputValidator.validate_k_parameter(0)
    
    def test_k_above_maximum(self):
        """K above maximum should raise ValidationError."""
        with pytest.raises(ValidationError, match="must be between"):
            InputValidator.validate_k_parameter(21)
    
    def test_k_negative(self):
        """Negative K should raise ValidationError."""
        with pytest.raises(ValidationError, match="must be between"):
            InputValidator.validate_k_parameter(-5)
    
    def test_k_not_integer(self):
        """Non-integer K should raise ValidationError."""
        with pytest.raises(ValidationError, match="must be an integer"):
            InputValidator.validate_k_parameter(5.5)
    
    def test_k_string(self):
        """String K should raise ValidationError."""
        with pytest.raises(ValidationError, match="must be an integer"):
            InputValidator.validate_k_parameter("5")
    
    def test_descriptive_k_error_messages(self):
        """K error messages should be descriptive (Requirement 16.5)."""
        try:
            InputValidator.validate_k_parameter(25)
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            error_msg = str(e)
            assert "K parameter" in error_msg
            assert "must be between" in error_msg
            assert "1" in error_msg
            assert "20" in error_msg


class TestPathSanitization:
    """Test path sanitization (Requirement 16.6)."""
    
    def test_sanitize_simple_filename(self):
        """Simple filename should be returned as-is."""
        result = InputValidator.sanitize_filepath("document.pdf")
        assert result == "document.pdf"
    
    def test_sanitize_removes_directory(self):
        """Directory components should be removed."""
        result = InputValidator.sanitize_filepath("/tmp/uploads/document.pdf")
        assert result == "document.pdf"
        assert "/" not in result
    
    def test_sanitize_removes_parent_traversal(self):
        """Parent directory traversal should raise error."""
        with pytest.raises(ValidationError, match="directory traversal"):
            InputValidator.sanitize_filepath("../../etc/passwd")
    
    def test_sanitize_removes_relative_path(self):
        """Relative path should be sanitized."""
        result = InputValidator.sanitize_filepath("uploads/subfolder/document.pdf")
        assert result == "document.pdf"
    
    def test_sanitize_empty_path(self):
        """Empty path should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            InputValidator.sanitize_filepath("")
    
    def test_sanitize_dot_filename(self):
        """Dot filename should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid filename"):
            InputValidator.sanitize_filepath(".")
    
    def test_sanitize_dotdot_filename(self):
        """Dot-dot filename should raise ValidationError."""
        with pytest.raises(ValidationError, match="directory traversal"):
            InputValidator.sanitize_filepath("..")
    
    def test_validate_file_path_security(self):
        """File path security validation should prevent traversal."""
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Valid path within directory
            valid_path = os.path.join(tmpdir, "document.pdf")
            InputValidator.validate_file_path_for_security(valid_path, tmpdir)
            
            # Path outside directory should fail
            outside_path = "/etc/passwd"
            with pytest.raises(ValidationError, match="outside allowed directory"):
                InputValidator.validate_file_path_for_security(outside_path, tmpdir)
    
    def test_validate_suspicious_patterns(self):
        """Suspicious path patterns should be rejected."""
        with pytest.raises(ValidationError, match="suspicious"):
            InputValidator.validate_file_path_for_security("~/secret/file.txt")
