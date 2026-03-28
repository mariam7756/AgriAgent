from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # إعدادات التطبيق الأساسية
    APP_NAME: str = "mini-rag-app"
    APP_VERSION: str = "0.1.0"
    OPENAI_API_KEY:str
   
    # إعدادات الملفات
    FILE_ALLOWED_TYPES: list = ["application/pdf", "text/plain"]
    FILE_MAX_SIZE: int = 10
    FILE_DEFAULT_CHUNK_SIZE: int = 512000
    
    # إعدادات قاعدة البيانات (تعديل الاسم ليطابق MONGO_DB_NAME)
    MONGODB_URI: str = "mongodb://localhost:270007"
    MONGODB_DATABASE: str = "mini-rag" # قمنا بتغيير الاسم هنا
    class Config:
        env_file =".env"
        

    

def get_settings():
    return Settings()
