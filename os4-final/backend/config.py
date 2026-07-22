import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@db:5432/orders_db")
    REDIS_URL: str    = os.getenv("REDIS_URL",    "redis://redis:6379")
    REDIS_CHANNEL: str = "order_updates"

    JWT_SECRET: str         = os.getenv("JWT_SECRET",           "change-this-secret")
    JWT_ALGORITHM: str      = os.getenv("JWT_ALGORITHM",         "HS256")
    JWT_EXPIRY_MINUTES: int = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))

    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:4000,http://localhost:4001,http://localhost:4002,http://localhost:5173"
    ).split(",")

    APP_ENV: str     = os.getenv("APP_ENV", "development")
    APP_TITLE: str   = "Real-Time Order Tracking API"
    APP_VERSION: str = "1.0.0"

settings = Settings()
