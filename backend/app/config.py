import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union


def _optional_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


@dataclass
class Settings:
    data_dir: Union[str, Path] = Path("data")
    database_path: Optional[Union[str, Path]] = None
    vector_dir: Optional[Union[str, Path]] = None
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    enable_chroma: bool = True

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        if self.database_path is None:
            self.database_path = self.data_dir / "recruiting_demo.sqlite3"
        else:
            self.database_path = Path(self.database_path)
        if self.vector_dir is None:
            self.vector_dir = self.data_dir / "vectors"
        else:
            self.vector_dir = Path(self.vector_dir)


def settings_from_env() -> Settings:
    return Settings(
        data_dir=Path(os.getenv("DATA_DIR", "data")),
        database_path=Path(os.getenv("DATABASE_PATH", "data/recruiting_demo.sqlite3")),
        vector_dir=Path(os.getenv("VECTOR_DIR", "data/vectors")),
        llm_base_url=_optional_env("LLM_BASE_URL"),
        llm_api_key=_optional_env("LLM_API_KEY"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        enable_chroma=os.getenv("ENABLE_CHROMA", "true").lower() not in {"0", "false", "no"},
    )

