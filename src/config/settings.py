"""Application settings via pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    """Environment-based configuration."""

    database_url: str = f"sqlite:///{DATA_DIR / 'cpbl.db'}"
    api_key: str = ""
    debug: bool = False

    # CPBL API
    cpbl_base_url: str = "https://cpbl.com.tw"
    cpbl_rate_limit_seconds: float = 2.0

    # Rebas Open Data
    rebas_data_dir: str = str(DATA_DIR / "rebas_raw")

    # Analysis defaults
    min_pa_for_analysis: int = 50
    min_ip_for_analysis: float = 20.0
    fatigue_bucket_size: int = 15

    model_config = {"env_file": str(PROJECT_ROOT / ".env"), "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()
