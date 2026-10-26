"""
Semantic Chunker for Vietnamese Government Documents.

Splits documents into semantically meaningful chunks while preserving context.
Implements Requirement 3 specifications with Vietnamese-specific heading detection.
"""
import re
import logging
from typing import List, Optional, Tuple
from app.models.data_models import Document, Chunk

logger = logging.getLogger(__name__)


class SemanticChunker:
    """
    Splits text into semantic chunks with metadata.
    
    Implements Vietnamese government document-aware chunking with:
    - Heading detection (Điều, Khoản, Chương, Phần, Mục)
    - Paragraph-based primary splitting
    - Size enforcement (200-1000 characters)
    - Sentence and clause-level splitting for large paragraphs
    
    Validates: Requirements 3.1-3.7
    """
    
    MIN_CHUNK_SIZE = 200  # characters
    MAX_CHUNK_SIZE = 1000  # characters
    
    # Vietnamese heading patterns
    HEADING_PATTERNS = [
        r'^Điều\s+\d+',  # Điều 1, Điều 2, etc.
        r'^Khoản\s+\d+',  # Khoản 1, Khoản 2, etc.
        r'^Chương\s+[IVX]+',  # Chương I, Chương II, etc.
        r'^Chương\s+\d+',  # Chương 1, Chương 2, etc.
        r'^Phần\s+thứ\s+\w+',  # Phần thứ nhất, Phần thứ hai, etc.
        r'^Phần\s+[IVX]+',  # Phần I, Phần II, etc.
        r'^Mục\s+\d+',  # Mục 1, Mục 2, etc.
    ]
    
    # Vietnamese sentence ending pattern (capital letter aware)
    SENTENCE_PATTERN = r'[.!?;]\s+(?=[A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ])'
    
    # Clause boundaries for very large sentences
    CLAUSE_BOUNDARIES = [', ', '; ', ' và ', ' hoặc ', ' nhưng ', ' nên ', ' để ']
    
    def __init__(self, min_size: int = MIN_CHUNK_SIZE, max_size: int = MAX_CHUNK_SIZE):
        """
        Initialize semantic chunker.
        
        Args:
            min_size: Minimum chunk size in characters (default: 200)
            max_size: Maximum chunk size in characters (default: 1000)
        """
        self.min_size = min_size
        self.max_size = max_size
        
        # Compile heading patterns for efficiency
        self.heading_regexes = [re.compile(pattern, re.IGNORECASE) for pattern in self.HEADING_PATTERNS]
        self.sentence_regex = re.compile(self.SENTENCE_PATTERN)
        
        logger.info(
            f"SemanticChunker initialized",
            extra={
                "min_size": self.min_size,
                "max_size": self.max_size,
                "heading_patterns": len(self.HEADING_PATTERNS)
            }
        )
    
    def chunk_document(self, document: Document) -> List[Chunk]:
        """
        Split document into semantically meaningful chunks.
        
        Args:
            document: Document object with text and metadata
            
        Returns:
            List of Chunk objects with text and metadata
            
        Validates: Requirements 3.1-3.7
        """
        start_time = self._get_time()
        
        text = document.text
        if not text or not text.strip():
            logger.warning(f"Empty document received: {document.id}")
            return []
        
        # Step 1: Split into paragraphs
        paragraphs = self._split_into_paragraphs(text)
        
        # Step 2: Detect headings and group with content
        sections = self._detect_headings_and_group(paragraphs)

        # Fallback: a short document may consist only of heading-like lines
        # (e.g. a one-paragraph TXT). Keep the full text so it is not dropped.
        if not sections:
            sections = [(None, text.strip())]

        # Step 3: Enforce size constraints
        chunks = self._enforce_size_constraints(sections)
        
        # Step 4: Create Chunk objects with metadata
        chunk_objects = self._create_chunk_objects(chunks, document.id, text)
        
        processing_time = self._get_time() - start_time
        
        logger.info(
            f"Document chunked",
            extra={
                "document_id": document.id,
                "chunk_count": len(chunk_objects),
                "processing_time_seconds": processing_time,
                "avg_chunk_size": sum(c.length for c in chunk_objects) / len(chunk_objects) if chunk_objects else 0
            }
        )
        
        return chunk_objects
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """
        Split text at paragraph boundaries (double newlines).
        
        Args:
            text: Input text
            
        Returns:
            List of paragraph strings
        """
        # Split on double newlines (or more)
        paragraphs = re.split(r'\n\n+', text)
        
        # Clean up paragraphs: strip whitespace and filter empty
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        return paragraphs
    
    def _detect_headings_and_group(self, paragraphs: List[str]) -> List[Tuple[Optional[str], str]]:
        """
        Detect headings and group them with following content.
        
        A line is considered a heading if:
        1. It matches Vietnamese document patterns (Điều, Khoản, etc.)
        2. It's ALL CAPS (min 10 chars)
        3. It ends with ":"
        4. It's short (<60 chars) and followed by a longer paragraph
        
        Args:
            paragraphs: List of paragraph strings
            
        Returns:
            List of (heading, content) tuples
        """
        sections = []
        current_heading = None
        
        for i, para in enumerate(paragraphs):
            is_heading = self._is_heading(para, paragraphs, i)
            
            if is_heading:
                # Keep the heading text as content as well. PDF extraction often
                # folds the first clause(s) of an article into the heading
                # paragraph; dropping it silently loses substantive text.
                current_heading = para
                sections.append((current_heading, para))
                logger.debug(f"Detected heading: {para[:50]}...")
            else:
                # Regular content paragraph
                sections.append((current_heading, para))
        
        return sections
    
    def _is_heading(self, para: str, all_paragraphs: List[str], index: int) -> bool:
        """
        Determine if a paragraph is a heading.
        
        Args:
            para: Paragraph text
            all_paragraphs: All paragraphs for context
            index: Current paragraph index
            
        Returns:
            True if paragraph is a heading
        """
        # Check Vietnamese document patterns
        for regex in self.heading_regexes:
            if regex.match(para):
                return True
        
        # Check if ALL CAPS (min 10 chars)
        if len(para) >= 10 and para.isupper():
            return True
        
        # Check if ends with ":"
        if para.endswith(':'):
            return True
        
        # Check if short line followed by longer paragraph
        if len(para) < 60 and index + 1 < len(all_paragraphs):
            next_para = all_paragraphs[index + 1]
            if len(next_para) > len(para) * 2:  # Next is significantly longer
                return True
        
        return False
    
    def _enforce_size_constraints(self, sections: List[Tuple[Optional[str], str]]) -> List[Tuple[Optional[str], str]]:
        """
        Enforce MIN and MAX chunk size constraints.
        
        Algorithm:
        1. If content < MIN_SIZE: merge with next section
        2. If content MIN_SIZE to MAX_SIZE: keep as-is
        3. If content > MAX_SIZE: split at sentence boundaries
        4. If sentence > MAX_SIZE: split at clause boundaries
        
        Args:
            sections: List of (heading, content) tuples
            
        Returns:
            List of (heading, content) tuples with enforced sizes
        """
        result = []
        i = 0
        
        while i < len(sections):
            heading, content = sections[i]
            content_length = len(content)
            
            # Case 1: Too small - merge with next
            if content_length < self.min_size and i + 1 < len(sections):
                next_heading, next_content = sections[i + 1]
                # Merge contents, keep the first heading if it exists
                merged_content = content + "\n\n" + next_content
                # A small heading followed by a huge paragraph must still obey
                # MAX_SIZE; otherwise a single chunk can grow to several KB.
                if len(merged_content) <= self.max_size:
                    result.append((heading, merged_content))
                else:
                    for chunk_text in self._split_large_content(merged_content):
                        result.append((heading, chunk_text))
                i += 2  # Skip next section since we merged it
                continue
            
            # Case 2: Perfect size - keep as-is
            elif self.min_size <= content_length <= self.max_size:
                result.append((heading, content))
                i += 1
                continue
            
            # Case 3: Too large - split
            else:
                split_chunks = self._split_large_content(content)
                # Add chunks with heading context
                for chunk_text in split_chunks:
                    result.append((heading, chunk_text))
                i += 1
                continue
        
        # Handle last section if it's too small (can't merge forward)
        if result and len(result[-1][1]) < self.min_size and len(result) > 1:
            # Merge with previous
            prev_heading, prev_content = result[-2]
            last_heading, last_content = result[-1]
            merged_content = prev_content + "\n\n" + last_content
            if len(merged_content) <= self.max_size:
                result[-2] = (prev_heading, merged_content)
                result = result[:-1]
            else:
                result[-2] = (prev_heading, prev_content)
                result[-1] = (prev_heading, last_content)
        
        return result
    
    def _split_large_content(self, content: str) -> List[str]:
        """
        Split large content at sentence or clause boundaries.
        
        Args:
            content: Content string that exceeds MAX_SIZE
            
        Returns:
            List of smaller content strings
        """
        # Try splitting at sentences first
        sentences = self._split_into_sentences(content)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # If single sentence is too large, split at clauses
            if len(sentence) > self.max_size:
                # If we have accumulated content, save it first
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # Split this large sentence at clauses
                clause_chunks = self._split_at_clauses(sentence)
                chunks.extend(clause_chunks)
            
            # If adding this sentence keeps us under max_size, add it
            elif len(current_chunk) + len(sentence) + 1 <= self.max_size:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            
            # Otherwise, save current chunk and start new one
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        # Add remaining content
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using Vietnamese-aware pattern.
        
        Args:
            text: Input text
            
        Returns:
            List of sentences
        """
        # Split using the sentence pattern
        sentences = self.sentence_regex.split(text)
        
        # Re-attach punctuation to sentences
        result = []
        for i in range(len(sentences)):
            sentence = sentences[i].strip()
            if sentence:
                # If not the last sentence, add back the punctuation
                if i < len(sentences) - 1:
                    # Find the punctuation that was split
                    match = re.search(r'[.!?;]$', text[text.find(sentence):text.find(sentence) + len(sentence) + 2])
                    if match:
                        sentence += match.group()
                result.append(sentence)
        
        # Fallback: if no sentences detected, return original as single sentence
        if not result:
            result = [text]
        
        return result
    
    def _split_at_clauses(self, sentence: str) -> List[str]:
        """
        Split a very large sentence at clause boundaries.
        
        Args:
            sentence: Sentence that exceeds MAX_SIZE
            
        Returns:
            List of clause-based chunks
        """
        chunks = []
        current_chunk = ""
        
        # Split at clause boundaries
        parts = self._split_by_clause_markers(sentence)
        
        for part in parts:
            if len(part) > self.max_size:
                # Even a clause is too large, just split at max_size
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # Hard split at character boundary
                while len(part) > self.max_size:
                    chunks.append(part[:self.max_size].strip())
                    part = part[self.max_size:]
                
                if part:
                    current_chunk = part
            
            elif len(current_chunk) + len(part) <= self.max_size:
                current_chunk += part
            
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = part
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_by_clause_markers(self, text: str) -> List[str]:
        """
        Split text by Vietnamese clause boundaries.
        
        Args:
            text: Input text
            
        Returns:
            List of text segments split at clause markers
        """
        # Use a regex pattern that captures the delimiter
        pattern = '(' + '|'.join(re.escape(marker) for marker in self.CLAUSE_BOUNDARIES) + ')'
        parts = re.split(pattern, text)
        
        # Rejoin delimiter with following part
        result = []
        i = 0
        while i < len(parts):
            if i + 1 < len(parts) and parts[i + 1] in self.CLAUSE_BOUNDARIES:
                result.append(parts[i] + parts[i + 1])
                i += 2
            else:
                if parts[i]:
                    result.append(parts[i])
                i += 1
        
        return result
    
    def _create_chunk_objects(
        self, 
        sections: List[Tuple[Optional[str], str]], 
        document_id: str,
        original_text: str
    ) -> List[Chunk]:
        """
        Create Chunk objects with complete metadata.
        
        Args:
            sections: List of (heading, content) tuples
            document_id: Source document ID
            original_text: Original document text for char position tracking
            
        Returns:
            List of Chunk objects
        """
        chunks = []
        char_position = 0
        
        for chunk_index, (heading, content) in enumerate(sections):
            # Find character position in original text
            # This is approximate since we've done transformations
            char_start = original_text.find(content, char_position)
            if char_start == -1:
                # Fallback: use current position
                char_start = char_position
            
            char_end = char_start + len(content)
            char_position = char_end
            
            chunk = Chunk(
                text=content,
                document_id=document_id,
                chunk_index=chunk_index,
                heading_context=heading,
                char_start=char_start,
                char_end=char_end
            )
            
            chunks.append(chunk)
        
        return chunks
    
    def _get_time(self) -> float:
        """Get current time for performance tracking."""
        import time
        return time.time()
