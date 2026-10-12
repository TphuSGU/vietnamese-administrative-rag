"""
Structured logging with JSON formatting and sensitive data redaction.

Implements Requirements 15.1, 15.2, 15.6 from design document.
"""
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """JSON formatter with sensitive data redaction."""
    
    SENSITIVE_KEYS = {
        'api_key', 'gemini_api_key', 'openai_api_key', 
        'password', 'token', 'secret', 'credential'
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with redaction."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra') and record.extra:
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Redact sensitive data
        log_data = self._redact_sensitive(log_data)
        
        return json.dumps(log_data, ensure_ascii=False)
    
    def _redact_sensitive(self, data: Any) -> Any:
        """Recursively redact sensitive information from data."""
        if isinstance(data, dict):
            return {
                k: '[REDACTED]' if self._is_sensitive_key(k) else self._redact_sensitive(v)
                for k, v in data.items()
            }
        elif isinstance(data, str):
            # Check if string contains sensitive patterns
            if self._contains_sensitive_pattern(data):
                return self._redact_in_string(data)
            return data
        elif isinstance(data, list):
            return [self._redact_sensitive(item) for item in data]
        return data
    
    def _is_sensitive_key(self, key: str) -> bool:
        """Check if key name indicates sensitive data."""
        key_lower = key.lower()
        return any(sensitive in key_lower for sensitive in self.SENSITIVE_KEYS)
    
    def _contains_sensitive_pattern(self, text: str) -> bool:
        """Check if string contains API key patterns."""
        text_lower = text.lower()
        # Check for API key patterns: "api_key:", "token:", etc.
        for sensitive in self.SENSITIVE_KEYS:
            if f"{sensitive}:" in text_lower or f"{sensitive}=" in text_lower:
                return True
        return False
    
    def _redact_in_string(self, text: str) -> str:
        """Redact sensitive values in strings."""
        # Simple redaction for key=value or key:value patterns
        import re
        pattern = r'(api_key|token|password|secret|credential)\s*[:=]\s*[^\s,})]+'
        return re.sub(pattern, r'\1=[REDACTED]', text, flags=re.IGNORECASE)


def setup_logging(log_level: str = "INFO", log_to_file: bool = False, 
                  log_file_path: str = "app.log") -> logging.Logger:
    """
    Set up structured JSON logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to also log to a file
        log_file_path: Path to log file if log_to_file is True
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("rag_system")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    # File handler if requested
    if log_to_file:
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_logger(name: str = "rag_system") -> logging.Logger:
    """Get logger instance for a specific component."""
    return logging.getLogger(name)


def redact_api_key(key: str) -> str:
    """
    Redact API key for safe logging (show first 4 and last 4 chars).
    
    Args:
        key: API key to redact
        
    Returns:
        Redacted key string
    """
    if not key:
        return "[EMPTY]"
    if len(key) < 8:
        return "[REDACTED]"
    return f"{key[:4]}...{key[-4:]}"
