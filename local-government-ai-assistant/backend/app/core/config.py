"""
Configuration management for RAG LLM Core System.

Uses Pydantic Settings for environment variable management with validation.
Supports Google Gemini API (not OpenAI) and vietnamese-bi-encoder (not VietAI).
"""
from typing import Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings
import logging
from pathlib import Path


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    # Google Gemini Configuration (replaces OpenAI)
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-2.0-flash-exp", env="GEMINI_MODEL")
    
    # Vietnamese Embedding Model (bkai-foundation-models/vietnamese-bi-encoder)
    embedding_model_name: str = Field(
        "bkai-foundation-models/vietnamese-bi-encoder",
        env="EMBEDDING_MODEL_NAME"
    )
    embedding_model_path: Optional[str] = Field(None, env="EMBEDDING_MODEL_PATH")
    embedding_dim: int = Field(768, env="EMBEDDING_DIM")
    
    # Chunking Parameters
    chunk_min_size: int = Field(200, env="CHUNK_MIN_SIZE")
    chunk_max_size: int = Field(1000, env="CHUNK_MAX_SIZE")
    
    # Retrieval Parameters
    default_k: int = Field(5, env="DEFAULT_K")
    max_k: int = Field(20, env="MAX_K")
    min_k: int = Field(1, env="MIN_K")
    
    # Vector Store Configuration (ChromaDB)
    chroma_db_path: str = Field("./chroma_db", env="CHROMA_DB_PATH")
    chroma_collection: str = Field("documents", env="CHROMA_COLLECTION")
    
    # API Configuration
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")
    
    # Logging Configuration
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    # File Upload Limits
    max_file_size_mb: int = Field(50, env="MAX_FILE_SIZE_MB")
    
    # Query Constraints
    min_query_length: int = Field(10, env="MIN_QUERY_LENGTH")
    max_query_length: int = Field(500, env="MAX_QUERY_LENGTH")
    
    # LLM Generation Parameters
    max_tokens: int = Field(500, env="MAX_TOKENS")
    temperature: float = Field(0.3, env="TEMPERATURE")
    
    # Concurrency
    max_concurrent_ingestion: int = Field(4, env="MAX_CONCURRENT_INGESTION")
    embedding_batch_size: int = Field(32, env="EMBEDDING_BATCH_SIZE")
    
    @validator("chunk_min_size")
    def validate_chunk_min_size(cls, v, values):
        """Validate chunk_min_size is positive."""
        if v <= 0:
            raise ValueError("CHUNK_MIN_SIZE must be positive")
        return v
    
    @validator("chunk_max_size")
    def validate_chunk_max_size(cls, v, values):
        """Validate chunk_max_size is greater than chunk_min_size."""
        if "chunk_min_size" in values and v <= values["chunk_min_size"]:
            raise ValueError(
                f"CHUNK_MAX_SIZE ({v}) must be greater than "
                f"CHUNK_MIN_SIZE ({values['chunk_min_size']})"
            )
        return v
    
    @validator("default_k")
    def validate_default_k(cls, v, values):
        """Validate default_k is within min_k and max_k range."""
        min_k = values.get("min_k", 1)
        max_k = values.get("max_k", 20)
        if not (min_k <= v <= max_k):
            raise ValueError(
                f"DEFAULT_K ({v}) must be between MIN_K ({min_k}) and MAX_K ({max_k})"
            )
        return v
    
    @validator("gemini_api_key")
    def validate_gemini_api_key(cls, v):
        """Validate Gemini API key is not empty."""
        if not v or v.strip() == "":
            raise ValueError("GEMINI_API_KEY is required and cannot be empty")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"LOG_LEVEL must be one of {valid_levels}, got {v}"
            )
        return v_upper
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def validate_configuration(settings: Settings) -> None:
    """
    Validate configuration and fail fast on startup.
    
    Args:
        settings: Settings instance to validate
        
    Raises:
        ValueError: If configuration is invalid
    """
    errors = []
    
    # Check Gemini API key
    if not settings.gemini_api_key or settings.gemini_api_key.strip() == "":
        errors.append("GEMINI_API_KEY is required")
    
    # Check chunk sizes
    if settings.chunk_min_size >= settings.chunk_max_size:
        errors.append(
            f"CHUNK_MIN_SIZE ({settings.chunk_min_size}) must be less than "
            f"CHUNK_MAX_SIZE ({settings.chunk_max_size})"
        )
    
    # Check K values
    if settings.default_k > settings.max_k:
        errors.append(
            f"DEFAULT_K ({settings.default_k}) cannot exceed "
            f"MAX_K ({settings.max_k})"
        )
    
    if settings.min_k > settings.max_k:
        errors.append(
            f"MIN_K ({settings.min_k}) cannot exceed MAX_K ({settings.max_k})"
        )
    
    # Check embedding model path if provided
    if settings.embedding_model_path:
        model_path = Path(settings.embedding_model_path)
        if not model_path.exists():
            errors.append(
                f"Embedding model path does not exist: {settings.embedding_model_path}"
            )
    
    # Check ChromaDB path is writable
    chroma_path = Path(settings.chroma_db_path)
    try:
        chroma_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append(f"Cannot create ChromaDB directory: {e}")
    
    if errors:
        error_msg = "\n".join(f"  - {e}" for e in errors)
        raise ValueError(f"Invalid configuration:\n{error_msg}")


# Global settings instance
settings = Settings()
