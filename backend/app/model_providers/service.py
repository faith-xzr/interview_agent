from dataclasses import dataclass, replace
from typing import Callable, Optional

from app.config import Settings
from app.schemas import ModelProviderSettingsResponse


MODEL_PROVIDER_SETTING_KEY = "default_model_provider_id"
MODEL_PROVIDER_API_KEY_SETTING_PREFIX = "model_provider_api_key:"

SettingReader = Callable[[str], Optional[str]]
SettingWriter = Callable[[str, str], None]


@dataclass(frozen=True)
class ModelProviderSpec:
    id: str
    name: str
    model: str
    base_url: str
    api_key: Optional[str] = None
    api_key_source: str = "none"


class ModelProviderService:
    def __init__(
        self,
        settings: Settings,
        setting_reader: Optional[SettingReader] = None,
        setting_writer: Optional[SettingWriter] = None,
    ) -> None:
        self.settings = settings
        self.setting_reader = setting_reader
        self.setting_writer = setting_writer
        self.providers = _model_provider_specs(settings, setting_reader)
        stored_provider_id = _normalized_stored_model_provider_id(
            self._read_setting(MODEL_PROVIDER_SETTING_KEY),
            settings,
        )
        self.default_provider_id = _valid_model_provider_id(
            stored_provider_id,
            self.providers,
            fallback_provider_id=_preferred_model_provider_id(settings),
        )
        if stored_provider_id != self.default_provider_id:
            self._write_setting(MODEL_PROVIDER_SETTING_KEY, self.default_provider_id)

    def default_provider(self) -> ModelProviderSpec:
        return self.providers[self.default_provider_id]

    def current_provider_id(self, base_url: Optional[str], model: str) -> str:
        stored = self._read_setting(MODEL_PROVIDER_SETTING_KEY)
        if stored in self.providers:
            stored_provider = self.providers[stored]
            if stored_provider.base_url == base_url and stored_provider.model == model:
                return stored
        for provider_id, provider in self.providers.items():
            if provider.base_url == base_url and provider.model == model:
                return provider_id
        return "openai-compatible"

    def settings_response(self, default_provider_id: Optional[str] = None) -> ModelProviderSettingsResponse:
        resolved_default_provider_id = default_provider_id or self.default_provider_id
        return ModelProviderSettingsResponse(
            default_provider_id=resolved_default_provider_id,
            providers=[
                {
                    "id": provider.id,
                    "name": provider.name,
                    "model": provider.model,
                    "base_url": provider.base_url,
                    "api_key_configured": bool(provider.api_key),
                    "api_key_source": provider.api_key_source,
                    "is_default": provider.id == resolved_default_provider_id,
                }
                for provider in self.providers.values()
            ],
        )

    def set_default(self, provider_id: str) -> ModelProviderSpec:
        normalized_provider_id = provider_id.strip()
        provider = self._provider_or_raise(normalized_provider_id)
        self._write_setting(MODEL_PROVIDER_SETTING_KEY, normalized_provider_id)
        self.default_provider_id = normalized_provider_id
        return provider

    def set_api_key(self, provider_id: str, api_key: str) -> ModelProviderSpec:
        normalized_provider_id = provider_id.strip()
        provider = self._provider_or_raise(normalized_provider_id)
        normalized_api_key = api_key.strip()
        if not normalized_api_key:
            raise ValueError("API Key 不能为空。")
        self._write_setting(_api_key_setting_key(normalized_provider_id), normalized_api_key)
        provider = replace(provider, api_key=normalized_api_key, api_key_source="saved")
        self.providers[normalized_provider_id] = provider
        return provider

    def _provider_or_raise(self, provider_id: str) -> ModelProviderSpec:
        try:
            return self.providers[provider_id]
        except KeyError as exc:
            raise ValueError("未知模型服务。") from exc

    def _read_setting(self, key: str) -> Optional[str]:
        if self.setting_reader is None:
            return None
        return self.setting_reader(key)

    def _write_setting(self, key: str, value: str) -> None:
        if self.setting_writer is not None:
            self.setting_writer(key, value)


def _api_key_setting_key(provider_id: str) -> str:
    return f"{MODEL_PROVIDER_API_KEY_SETTING_PREFIX}{provider_id}"


def _model_provider_specs(
    settings: Settings,
    setting_reader: Optional[SettingReader] = None,
) -> dict[str, ModelProviderSpec]:
    legacy_provider_id = _provider_id_from_base_url(settings.llm_base_url)

    def saved_api_key(provider_id: str) -> Optional[str]:
        if setting_reader is None:
            return None
        value = setting_reader(_api_key_setting_key(provider_id))
        return value.strip() if value and value.strip() else None

    def provider_api_key(provider_id: str, configured_key: Optional[str]) -> tuple[Optional[str], str]:
        stored_key = saved_api_key(provider_id)
        if stored_key:
            return stored_key, "saved"
        if configured_key:
            return configured_key, "env"
        if legacy_provider_id == provider_id:
            return settings.llm_api_key, "env" if settings.llm_api_key else "none"
        return None, "none"

    def provider_model(provider_id: str, configured_model: str) -> str:
        if legacy_provider_id == provider_id and settings.llm_model:
            return settings.llm_model
        return configured_model

    openai_base_url = "https://api.openai.com/v1"
    openai_model = "gpt-4o-mini"
    openai_api_key = saved_api_key("openai-compatible")
    openai_api_key_source = "saved" if openai_api_key else "none"
    if legacy_provider_id is None:
        openai_base_url = (settings.llm_base_url or openai_base_url).rstrip("/")
        openai_model = settings.llm_model or openai_model
        if not openai_api_key:
            openai_api_key = settings.llm_api_key
            openai_api_key_source = "env" if settings.llm_api_key else "none"

    dashscope_api_key, dashscope_key_source = provider_api_key("dashscope", settings.dashscope_api_key)
    deepseek_api_key, deepseek_key_source = provider_api_key("deepseek", settings.deepseek_api_key)
    kimi_api_key, kimi_key_source = provider_api_key("kimi", settings.kimi_api_key)
    glm_api_key, glm_key_source = provider_api_key("glm", settings.glm_api_key)

    return {
        "dashscope": ModelProviderSpec(
            id="dashscope",
            name="通义千问（DashScope）",
            model=provider_model("dashscope", settings.dashscope_model),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=dashscope_api_key,
            api_key_source=dashscope_key_source,
        ),
        "deepseek": ModelProviderSpec(
            id="deepseek",
            name="DeepSeek",
            model=provider_model("deepseek", settings.deepseek_model),
            base_url="https://api.deepseek.com/v1",
            api_key=deepseek_api_key,
            api_key_source=deepseek_key_source,
        ),
        "kimi": ModelProviderSpec(
            id="kimi",
            name="Kimi",
            model=provider_model("kimi", settings.kimi_model),
            base_url="https://api.moonshot.cn/v1",
            api_key=kimi_api_key,
            api_key_source=kimi_key_source,
        ),
        "glm": ModelProviderSpec(
            id="glm",
            name="智谱 GLM",
            model=provider_model("glm", settings.glm_model),
            base_url="https://open.bigmodel.cn/api/coding/paas/v4",
            api_key=glm_api_key,
            api_key_source=glm_key_source,
        ),
        "openai-compatible": ModelProviderSpec(
            id="openai-compatible",
            name="OpenAI Compatible",
            model=openai_model,
            base_url=openai_base_url,
            api_key=openai_api_key,
            api_key_source=openai_api_key_source,
        ),
    }


def _valid_model_provider_id(
    value: Optional[str],
    providers: dict[str, ModelProviderSpec],
    fallback_provider_id: str = "openai-compatible",
) -> str:
    if value and value in providers:
        return value
    if fallback_provider_id in providers:
        return fallback_provider_id
    return "openai-compatible"


def _normalized_stored_model_provider_id(value: Optional[str], settings: Settings) -> Optional[str]:
    if value == "openai-compatible" and _provider_id_from_base_url(settings.llm_base_url):
        return None
    return value


def _provider_id_from_base_url(base_url: Optional[str]) -> Optional[str]:
    if not base_url:
        return None
    normalized = base_url.lower()
    if "dashscope.aliyuncs.com" in normalized:
        return "dashscope"
    if "deepseek.com" in normalized:
        return "deepseek"
    if "moonshot.cn" in normalized:
        return "kimi"
    if "bigmodel.cn" in normalized:
        return "glm"
    return None


def _preferred_model_provider_id(settings: Settings) -> str:
    legacy_provider_id = _provider_id_from_base_url(settings.llm_base_url)
    if legacy_provider_id:
        return legacy_provider_id
    if settings.dashscope_api_key:
        return "dashscope"
    if settings.deepseek_api_key:
        return "deepseek"
    if settings.kimi_api_key:
        return "kimi"
    if settings.glm_api_key:
        return "glm"
    return "openai-compatible"
