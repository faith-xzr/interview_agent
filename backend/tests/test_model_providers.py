from app.config import Settings
from app.model_providers import ModelProviderService
from app.storage import RunStorage


def test_model_provider_service_persists_default_and_api_keys(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "demo.sqlite3",
        vector_dir=tmp_path / "vectors",
        llm_api_key=None,
        llm_base_url=None,
        llm_model="demo-offline",
    )
    storage = RunStorage(settings.database_path)
    service = ModelProviderService(settings, storage.get_setting, storage.set_setting)

    response = service.settings_response()

    assert response.default_provider_id == "openai-compatible"
    assert [provider.id for provider in response.providers] == [
        "dashscope",
        "deepseek",
        "kimi",
        "glm",
        "openai-compatible",
    ]

    deepseek = service.set_default("deepseek")

    assert deepseek.id == "deepseek"
    assert storage.get_setting("default_model_provider_id") == "deepseek"

    service.set_api_key("deepseek", "sk-direct-deepseek")
    saved_response = service.settings_response(default_provider_id="deepseek")
    saved_deepseek = next(provider for provider in saved_response.providers if provider.id == "deepseek")

    assert storage.get_setting("model_provider_api_key:deepseek") == "sk-direct-deepseek"
    assert saved_deepseek.api_key_configured is True
    assert saved_deepseek.api_key_source == "saved"


def test_model_provider_service_rejects_unknown_provider(tmp_path):
    settings = Settings(data_dir=tmp_path)
    storage = RunStorage(settings.database_path)
    service = ModelProviderService(settings, storage.get_setting, storage.set_setting)

    try:
        service.set_default("missing-provider")
    except ValueError as exc:
        assert str(exc) == "未知模型服务。"
    else:
        raise AssertionError("Expected unknown provider to be rejected.")
