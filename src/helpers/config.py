from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):

    APP_NAME: str
    APP_VERSION: str
    

    # Database
    POSTGRES_USERNAME: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_MAIN_DATABASE: str

    # File processing
    FILE_ALLOWED_TYPES: list
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE: int

    # Generation — Groq
    GENERATION_BACKEND: str
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_URL: Optional[str] = None
    COHERE_API_KEY: Optional[str] = None
    GENERATION_MODEL_ID: Optional[str] = None
    GENERATION_MODEL_ID_LITERAL: Optional[List[str]] = None
    GENERATION_DAFAULT_MAX_TOKENS: int = 512
    GENERATION_DAFAULT_TEMPERATURE: float = 0.3

    # Embedding — Ollama local (URL منفصل عن Groq)
    EMBEDDING_BACKEND: str
    EMBEDDING_MODEL_ID: Optional[str] = None
    EMBEDDING_MODEL_SIZE: Optional[int] = None
    EMBEDDING_API_URL: str = "http://127.0.0.1:11434/v1"
    EMBEDDING_API_KEY: str = "ollama"

    # Input
    INPUT_DAFAULT_MAX_CHARACTERS: int = 8000

    # Vector DB
    VECTOR_DB_BACKEND: str
    VECTOR_DB_BACKEND_LITERAL: Optional[List[str]] = None
    VECTOR_DB_PATH: Optional[str] = None
    VECTOR_DB_DISTANCE_METHOD: Optional[str] = None
    VECTOR_DB_PGVEC_INDEX_THRESHOLD: int = 100

    # Languages
    PRIMARY_LANG: str = "ar"
    DEFAULT_LANG: str = "ar"

    # Agri config
    AGRO_LIB_BASE_URL: Optional[str] = None
    AGRO_LIB_CRAWL_DELAY: float = 1.0
    ADMIN_API_KEY: Optional[str] = None
    DEFAULT_KB_PROJECT_ID: int = 1

    class Config:
        
        env_file = ".env"
        


def get_settings():
    return Settings()
