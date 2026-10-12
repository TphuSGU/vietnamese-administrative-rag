"""
Input validation for RAG LLM Core System.

Implements Requirement 16 (Input Validation) from requirements document.
Validates file uploads, queries, and retrieval parameters.
"""
import os
import re
from pathlib import Path
from typing import Optional

from app.models.exceptions import ValidationError


class InputValidator:
    """
    Validates all user inputs to the RAG system.
    
    Implements:
    - Requirement 16.1: File size validation (≤50MB)
    - Requirement 16.2: File extension validation (.pdf, .docx, .txt)
    - Requirement 16.3: Query validation (UTF-8, length 10-500 chars)
    - Requirement 16.4: K parameter validation (1-20)
    - Requirement 16.5: Descriptive error messages
    - Requirement 16.6: Path sanitization (prevent directory traversal)
    """
    
    # Supported file formats from Requirement 16.2
    SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.txt'}
    
    # File size limit from Requirement 16.1 (50MB)
    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
    
    # Query length constraints from Requirement 7.2 and 16.3
    MIN_QUERY_LENGTH = 10
    MAX_QUERY_LENGTH = 500
    
    # K parameter constraints from Requirement 8.3 and 16.4
    MIN_K = 1
    MAX_K = 20
    
    @classmethod
    def validate_file_upload(cls, filename: str, file_size: int) -> None:
        """
        Validate uploaded file meets requirements.
        
        Implements Requirements 16.1, 16.2, 16.5.
        
        Args:
            filename: Name of the uploaded file
            file_size: Size of the file in bytes
            
        Raises:
            ValidationError: If file is invalid with descriptive message
        """
        # Validate filename is not empty
        if not filename or not filename.strip():
            raise ValidationError("Filename cannot be empty")
        
        # Validate file extension (Requirement 16.2)
        file_ext = Path(filename).suffix.lower()
        if file_ext not in cls.SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(cls.SUPPORTED_EXTENSIONS))
            raise ValidationError(
                f"Unsupported file format '{file_ext}'. "
                f"Supported formats: {supported}"
            )
        
        # Validate file size (Requirement 16.1)
        if file_size <= 0:
            raise ValidationError("File size must be greater than 0 bytes")
        
        if file_size > cls.MAX_FILE_SIZE_BYTES:
            max_mb = cls.MAX_FILE_SIZE_BYTES / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            raise ValidationError(
                f"File size ({actual_mb:.2f} MB) exceeds maximum allowed "
                f"size of {max_mb:.0f} MB"
            )
    
    @classmethod
    def validate_query(cls, query: str) -> None:
        """
        Validate user query meets requirements.
        
        Implements Requirements 7.2, 16.3, 16.5.
        
        Args:
            query: User query string
            
        Raises:
            ValidationError: If query is invalid with descriptive message
        """
        # Validate query is not None or empty
        if query is None:
            raise ValidationError("Query cannot be None")
        
        if not query or not query.strip():
            raise ValidationError("Query cannot be empty")
        
        # Validate UTF-8 encoding (Requirement 16.3)
        try:
            query.encode('utf-8')
        except UnicodeEncodeError as e:
            raise ValidationError(
                f"Query contains invalid UTF-8 characters: {str(e)}"
            )
        
        # Validate query length (Requirement 7.2)
        query_length = len(query.strip())
        
        if query_length < cls.MIN_QUERY_LENGTH:
            raise ValidationError(
                f"Query is too short ({query_length} characters). "
                f"Minimum length is {cls.MIN_QUERY_LENGTH} characters"
            )
        
        if query_length > cls.MAX_QUERY_LENGTH:
            raise ValidationError(
                f"Query is too long ({query_length} characters). "
                f"Maximum length is {cls.MAX_QUERY_LENGTH} characters"
            )
    
    @classmethod
    def validate_k_parameter(cls, k: int) -> None:
        """
        Validate retrieval K parameter.
        
        Implements Requirements 8.3, 16.4, 16.5.
        
        Args:
            k: Number of chunks to retrieve
            
        Raises:
            ValidationError: If K is invalid with descriptive message
        """
        # Validate K is an integer
        if not isinstance(k, int):
            raise ValidationError(
                f"K parameter must be an integer, got {type(k).__name__}"
            )
        
        # Validate K is within allowed range (Requirement 8.3, 16.4)
        if k < cls.MIN_K or k > cls.MAX_K:
            raise ValidationError(
                f"K parameter ({k}) must be between {cls.MIN_K} and {cls.MAX_K}"
            )
    
    @classmethod
    def sanitize_filepath(cls, filepath: str) -> str:
        """
        Sanitize file path to prevent directory traversal attacks.
        
        Implements Requirement 16.6.
        
        Args:
            filepath: Path to sanitize
            
        Returns:
            Sanitized filename (basename only)
            
        Raises:
            ValidationError: If filepath is invalid
        """
        if not filepath or not filepath.strip():
            raise ValidationError("Filepath cannot be empty")
        
        # Check for suspicious patterns BEFORE extracting basename
        if '..' in filepath:
            raise ValidationError(
                "Filepath contains directory traversal patterns"
            )
        
        # Remove any directory components to prevent traversal
        sanitized = os.path.basename(filepath)
        
        # Validate sanitized filename is not empty or special names
        if not sanitized or sanitized.strip() in ('', '.', '..'):
            raise ValidationError("Invalid filename after sanitization")
        
        return sanitized
    
    @classmethod
    def validate_file_path_for_security(cls, filepath: str, 
                                       allowed_directory: Optional[str] = None) -> None:
        """
        Validate file path for security concerns.
        
        Implements Requirement 16.6.
        
        Args:
            filepath: Full path to validate
            allowed_directory: Optional directory constraint
            
        Raises:
            ValidationError: If path is suspicious or outside allowed directory
        """
        if not filepath:
            raise ValidationError("Filepath cannot be empty")
        
        # Resolve to absolute path to detect traversal
        try:
            abs_path = Path(filepath).resolve()
        except Exception as e:
            raise ValidationError(f"Invalid filepath: {str(e)}")
        
        # Check if path tries to escape allowed directory
        if allowed_directory:
            try:
                allowed_abs = Path(allowed_directory).resolve()
                # Check if file is within allowed directory
                abs_path.relative_to(allowed_abs)
            except ValueError:
                raise ValidationError(
                    f"File path is outside allowed directory: {allowed_directory}"
                )
        
        # Check for suspicious patterns
        path_str = str(abs_path)
        if '..' in filepath or '~' in filepath:
            raise ValidationError(
                "Filepath contains suspicious traversal patterns"
            )
