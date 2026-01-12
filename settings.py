from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    TELEGRAM_TOKEN: str
    OPENAI_API_KEY: str
    
    OPENAI_BASE_URL: str = "https://api.groq.com/openai/v1"
    AI_MODEL: str = "llama-3.3-70b-versatile"
    
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'


settings = Settings()