import os
import logging
import sys
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class AppConfig:
    api_key: str
    model_name: str
    base_url: str
    log_level: str
    max_retries: int
    timeout: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        api_key = os.getenv("API_KEY", "")
        if not api_key:
            raise ValueError("API_KEY environment variable is not set.")
        return cls(
            api_key=api_key,
            model_name=os.getenv("MODEL_NAME", "gpt-4"),
            base_url=os.getenv("BASE_URL", "https://api.openai.com/v1"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            max_retries=int(os.getenv("MAX_RETRIES", 3)),
            timeout=int(os.getenv("TIMEOUT", 30)),
        )


def setup_logging(level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    fmt = "%(asctime)s - %(levelname)-8s  %(name)s - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # 控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    # 文件handler
    file_handler = logging.FileHandler("app.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")