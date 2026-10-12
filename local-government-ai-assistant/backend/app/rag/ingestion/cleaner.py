"""
Text cleaning and normalization for Vietnamese documents.

Implements Requirement 2: Text Preprocessing from the RAG LLM Core design.
Provides Unicode normalization, whitespace handling, control character removal,
diacritics preservation, and lowercase conversion.
"""
import re
import unicodedata
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class TextCleaner:
    """
    Cleans and normalizes Vietnamese text for consistent embedding quality.
    
    Implements Requirements 2.1-2.5:
    - 2.1: Unicode normalization to NFC form
    - 2.2: Whitespace normalization (preserve paragraph breaks)
    - 2.3: Vietnamese diacritics preservation
    - 2.4: Control character removal (except \n and \t)
    - 2.5: Lowercase conversion
    
    Properties:
    - Property 3: Unicode Normalization Idempotence
    - Property 4: Whitespace Cleaning Invariant
    - Property 5: Diacritics Preservation
    - Property 6: Control Character Filtering
    - Property 7: Lowercase Conversion Completeness
    """
    
    # Vietnamese diacritics to verify preservation
    VIETNAMESE_DIACRITICS = (
        "àáảãạăằắẳẵặâầấẩẫậ"
        "đ"
        "èéẻẽẹêềếểễệ"
        "ìíỉĩị"
        "òóỏõọôồốổỗộơờớởỡợ"
        "ùúủũụưừứửữự"
        "ỳýỷỹỵ"
    )
    
    # Control characters pattern (ASCII 0x00-0x1F and 0x7F, except \n and \t)
    CONTROL_CHARS_PATTERN = re.compile(
        r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]'
    )
    
    # Multiple spaces pattern
    MULTIPLE_SPACES_PATTERN = re.compile(r' {2,}')
    
    # Pattern to preserve paragraph breaks (2+ newlines)
    PARAGRAPH_PATTERN = re.compile(r'\n{2,}')
    
    def __init__(self):
        """Initialize the TextCleaner."""
        logger.info("TextCleaner initialized", extra={"component": "text_cleaner"})
    
    def clean(self, text: str) -> str:
        """
        Clean and normalize Vietnamese text.
        
        Processing steps (in order):
        1. Unicode normalization to NFC form
        2. Control character removal (except \\n and \\t)
        3. Whitespace normalization (collapse spaces, preserve paragraph breaks)
        4. Lowercase conversion
        
        Args:
            text: Raw text content to clean
            
        Returns:
            Cleaned and normalized text
            
        Examples:
            >>> cleaner = TextCleaner()
            >>> cleaner.clean("Thủ  tục   đăng  ký")
            'thủ tục đăng ký'
            
            >>> cleaner.clean("HƯỚNG DẪN\\n\\nNỘI DUNG")
            'hướng dẫn\\n\\nnội dung'
        """
        if not text:
            return ""
        
        try:
            # Step 1: Unicode normalization to NFC form (Requirement 2.1, Property 3)
            text = self._normalize_unicode(text)
            
            # Step 2: Remove control characters except \n and \t (Requirement 2.4, Property 6)
            text = self._remove_control_characters(text)
            
            # Step 3: Normalize whitespace (Requirement 2.2, Property 4)
            text = self._normalize_whitespace(text)
            
            # Step 4: Convert to lowercase (Requirement 2.5, Property 7)
            text = self._to_lowercase(text)
            
            # Verify diacritics preservation (Requirement 2.3, Property 5)
            # This is implicit - NFC normalization and lowercase preserve diacritics
            
            logger.debug(
                "Text cleaned successfully",
                extra={
                    "component": "text_cleaner",
                    "input_length": len(text),
                    "output_length": len(text)
                }
            )
            
            return text
            
        except Exception as e:
            logger.error(
                f"Text cleaning failed: {e}",
                extra={
                    "component": "text_cleaner",
                    "error": str(e),
                    "text_length": len(text)
                }
            )
            raise
    
    def _normalize_unicode(self, text: str) -> str:
        """
        Normalize Unicode characters to NFC (Canonical Decomposition followed by Composition).
        
        NFC is the standard normalization form for Vietnamese text that ensures
        consistent representation of accented characters.
        
        Property 3: normalize(normalize(x)) == normalize(x) (idempotent)
        
        Args:
            text: Text to normalize
            
        Returns:
            Unicode-normalized text in NFC form
        """
        return unicodedata.normalize('NFC', text)
    
    def _remove_control_characters(self, text: str) -> str:
        """
        Remove control characters except newline (\\n) and tab (\\t).
        
        Control characters are ASCII characters in ranges:
        - 0x00-0x08 (before tab)
        - 0x0B-0x0C (between tab/newline and carriage return)
        - 0x0E-0x1F (after carriage return)
        - 0x7F (delete)
        
        Property 6: Output contains no control chars except \\n and \\t
        
        Args:
            text: Text to clean
            
        Returns:
            Text with control characters removed (replaced with space to preserve word boundaries)
        """
        # Replace control chars with space to preserve word boundaries
        return self.CONTROL_CHARS_PATTERN.sub(' ', text)
    
    def _normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace while preserving paragraph boundaries and tabs.
        
        - Collapses multiple spaces to single space
        - Preserves tabs (\\t)
        - Preserves paragraph breaks (double newlines \\n\\n)
        - Removes leading and trailing whitespace
        
        Property 4: No consecutive spaces except at paragraph boundaries
        
        Args:
            text: Text to normalize
            
        Returns:
            Text with normalized whitespace
        """
        # First, protect tabs by replacing with a marker
        tab_marker = "\x00TAB\x00"
        text = text.replace('\t', tab_marker)
        
        # Identify and mark paragraph breaks
        # A paragraph break is 2+ consecutive newlines (with possible whitespace between)
        paragraph_marker = "\x00PARAGRAPH\x00"
        
        # Normalize newlines with surrounding whitespace to single newline
        text = re.sub(r' *\n *', '\n', text)
        
        # Now replace 2+ newlines with paragraph marker
        text = self.PARAGRAPH_PATTERN.sub(paragraph_marker, text)
        
        # Convert remaining single newlines to spaces
        text = text.replace('\n', ' ')
        
        # Collapse multiple spaces to single space
        text = re.sub(r' {2,}', ' ', text)
        
        # Restore paragraph breaks
        text = text.replace(paragraph_marker, '\n\n')
        
        # Restore tabs
        text = text.replace(tab_marker, '\t')
        
        # Remove leading/trailing whitespace from each paragraph
        paragraphs = text.split('\n\n')
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        text = '\n\n'.join(paragraphs)
        
        return text
    
    def _to_lowercase(self, text: str) -> str:
        """
        Convert all text to lowercase.
        
        Python's lower() method correctly handles Vietnamese diacritics,
        converting uppercase accented characters to lowercase equivalents.
        
        Property 7: No uppercase characters remain after conversion
        Property 5: Vietnamese diacritics are preserved during conversion
        
        Args:
            text: Text to convert
            
        Returns:
            Lowercase text
        """
        return text.lower()
    
    def verify_diacritics_preserved(self, original: str, cleaned: str) -> bool:
        """
        Verify that Vietnamese diacritics are preserved after cleaning.
        
        This is a testing/validation method to ensure Property 5.
        
        Args:
            original: Original text before cleaning
            cleaned: Cleaned text after processing
            
        Returns:
            True if all diacritics are preserved (accounting for case changes)
        """
        # Normalize both to lowercase for comparison
        original_lower = original.lower()
        cleaned_lower = cleaned.lower()
        
        # Count diacritics in both
        original_diacritics = sum(
            1 for char in original_lower 
            if char in self.VIETNAMESE_DIACRITICS
        )
        cleaned_diacritics = sum(
            1 for char in cleaned_lower 
            if char in self.VIETNAMESE_DIACRITICS
        )
        
        # Should have same count (diacritics preserved)
        return original_diacritics == cleaned_diacritics
