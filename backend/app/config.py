import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _optional_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _load_env_file() -> None:
    if load_dotenv is None:
        return
    here = Path(__file__).resolve()
    seen: set[Path] = set()
    for parent in [Path.cwd().resolve(), *here.parents]:
        if parent in seen:
            continue
        seen.add(parent)
        candidate = parent / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return


@dataclass
class Settings:
    data_dir: Union[str, Path] = Path("data")
    database_path: Optional[Union[str, Path]] = None
    vector_dir: Optional[Union[str, Path]] = None
    skills_dir: Optional[Union[str, Path]] = None
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    dashscope_api_key: Optional[str] = None
    dashscope_model: str = "qwen3.5-flash"
    deepseek_api_key: Optional[str] = None
    deepseek_model: str = "deepseek-v4-flash"
    kimi_api_key: Optional[str] = None
    kimi_model: str = "kimi-latest"
    glm_api_key: Optional[str] = None
    glm_model: str = "glm-5"
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
        if self.skills_dir is None:
            self.skills_dir = Path(__file__).resolve().parents[1] / "skills"
        else:
            self.skills_dir = Path(self.skills_dir)


def settings_from_env() -> Settings:
    _load_env_file()
    default_skills_dir = Path(__file__).resolve().parents[1] / "skills"
    return Settings(
        data_dir=Path(os.getenv("DATA_DIR", "data")),
        database_path=Path(os.getenv("DATABASE_PATH", "data/recruiting_demo.sqlite3")),
        vector_dir=Path(os.getenv("VECTOR_DIR", "data/vectors")),
        skills_dir=Path(os.getenv("SKILLS_DIR", default_skills_dir)),
        llm_base_url=_optional_env("LLM_BASE_URL"),
        llm_api_key=_optional_env("LLM_API_KEY"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        dashscope_api_key=_optional_env("AI_BAILIAN_API_KEY") or _optional_env("DASHSCOPE_API_KEY"),
        dashscope_model=os.getenv("AI_MODEL", "qwen3.5-flash"),
        deepseek_api_key=_optional_env("PROVIDER_DEEPSEEK_API_KEY"),
        deepseek_model=os.getenv("PROVIDER_DEEPSEEK_MODEL", "deepseek-v4-flash"),
        kimi_api_key=_optional_env("PROVIDER_KIMI_API_KEY"),
        kimi_model=os.getenv("PROVIDER_KIMI_MODEL", "kimi-latest"),
        glm_api_key=_optional_env("PROVIDER_GLM_API_KEY"),
        glm_model=os.getenv("PROVIDER_GLM_MODEL", "glm-5"),
        enable_chroma=os.getenv("ENABLE_CHROMA", "true").lower() not in {"0", "false", "no"},
    )
