import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # App configuration
    APP_NAME: str = "Wingman API"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"
    
    # CORS Settings
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"]
    
    # OpenAI Config
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")
    FAST_MODEL: str = "gpt-4o-mini" 
    REASONING_MODEL: str = "o3-mini"
    
    # Default generation parameters
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2048
    REASONING_EFFORT: str = "low" # Options: low, medium, high
    
    # MongoDB Config
    MONGODB_URL: str = Field(default="mongodb://root:example@mongodb:27017/")
    MONGODB_DB_NAME: str = "wingman"
    
    # Redis Config
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    
    # Neo4j Config
    NEO4J_URI: str = Field(default="bolt://neo4j:7687")
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = Field(default="password")
    NEO4J_DATABASE: str = Field(default="neo4j")
    
    # ChromaDB Config
    CHROMA_SERVER_URL: str = Field(default="http://chromadb:8000")
    CHROMA_COLLECTION_NAME: str = "wingman_memory"
    CHROMA_EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    
    # Scheduler Config
    CONSOLIDATION_HOUR: int = 0  # Midnight local time
    
    # Credentials Security
    ENCRYPTION_KEY: str = Field(default="generate-your-fernet-key-here")
    FALLBACK_ENCRYPTION_KEYS: str = Field(default="") # Comma-separated rotational fallbacks

    # External Service Credentials
    GOOGLE_CLIENT_ID: str = Field(default="")
    GOOGLE_CLIENT_SECRET: str = Field(default="")
    GOOGLE_REDIRECT_URI: str = Field(default="http://localhost:8000/api/v1/auth/google/callback")

    SLACK_BOT_TOKEN: str = Field(default="")
    SLACK_SIGNING_SECRET: str = Field(default="")

    # Vision OCR Config
    OCR_MODEL: str = "gpt-4o-mini"
    USE_VISION_OCR: bool = True

    # Tool API Keys
    WEATHER_API_KEY: str = Field(default="")
    YOUTUBE_API_KEY: str = Field(default="")
    GOOGLE_MAPS_API_KEY: str = Field(default="")
    TAVILY_API_KEY: str = Field(default="")

    # Logging
    LOG_LEVEL: str = "INFO"

# Load Settings
settings = Settings()
