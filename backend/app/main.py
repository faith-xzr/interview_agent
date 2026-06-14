from dataclasses import dataclass, replace
import json
from typing import Callable, List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.config import Settings, settings_from_env
from app.extraction.document_parser import DocumentParseError, extract_text_from_bytes
from app.interview_followup import generate_interview_answer_followup
from app.interview_session import create_interview_session, finalize_interview_session, submit_interview_turn
from app.llm_client import LLMClient
from app.pipeline import RecruitingPipeline
from app.schemas import (
    InterviewAnswerFollowUpRequest,
    InterviewStartRequest,
    InterviewTurnRequest,
    ModelProviderApiKeyRequest,
    ModelProviderDefaultRequest,
    ModelProviderSettingsResponse,
)


MODEL_PROVIDER_SETTING_KEY = "default_model_provider_id"
MODEL_PROVIDER_API_KEY_SETTING_PREFIX = "model_provider_api_key:"


@dataclass(frozen=True)
class ModelProviderSpec:
    id: str
    name: str
    model: str
    base_url: str
    api_key: Optional[str] = None
    api_key_source: str = "none"


def create_app(settings: Settings = None) -> FastAPI:
    app_settings = settings or settings_from_env()
    pipeline = RecruitingPipeline(app_settings)
    model_providers = _model_provider_specs(app_settings, pipeline.storage.get_setting)
    stored_provider_id = _normalized_stored_model_provider_id(
        pipeline.storage.get_setting(MODEL_PROVIDER_SETTING_KEY),
        app_settings,
    )
    default_provider_id = _valid_model_provider_id(
        stored_provider_id,
        model_providers,
        fallback_provider_id=_preferred_model_provider_id(app_settings),
    )
    if stored_provider_id != default_provider_id:
        pipeline.storage.set_setting(MODEL_PROVIDER_SETTING_KEY, default_provider_id)
    _apply_model_provider(pipeline, model_providers[default_provider_id])
    app = FastAPI(title="AI 招聘演示系统", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "llm_enabled": pipeline.llm.available,
            "model_provider": _current_model_provider_id(pipeline, model_providers),
            "llm_model": pipeline.settings.llm_model,
        }

    @app.post("/api/runs")
    async def create_run(
        jd_file: Optional[UploadFile] = File(None),
        resume_files: Optional[List[UploadFile]] = File(None),
        jd_text: Optional[str] = Form(None),
        resume_texts: Optional[List[str]] = Form(None),
    ):
        jd_content, warnings = await _collect_jd(jd_file, jd_text)
        resumes = await _collect_resumes(resume_files, resume_texts, warnings)
        if not jd_content.strip():
            raise HTTPException(status_code=400, detail="JD 内容不能为空，请上传 JD 文件或粘贴 JD 文本。")
        if not resumes:
            raise HTTPException(status_code=400, detail="至少需要一份有效简历内容。")
        report = await run_in_threadpool(pipeline.run, jd_content, resumes, warnings)
        return report

    @app.get("/api/runs")
    def list_runs():
        return pipeline.storage.list_runs()

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        report = pipeline.get_run(run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="未找到该运行记录。")
        return report

    @app.post("/api/runs/{run_id}/answer-followup")
    async def create_answer_followup(run_id: str, request: InterviewAnswerFollowUpRequest):
        report = pipeline.get_run(run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="未找到该运行记录。")
        candidate = next(
            (item for item in report.candidates if item.candidate_id == request.candidate_id),
            None,
        )
        if candidate is None:
            raise HTTPException(status_code=404, detail="未找到该候选人。")
        if not request.candidate_answer.strip():
            raise HTTPException(status_code=400, detail="候选人回答不能为空。")
        if request.question_index < 0 or request.question_index >= len(candidate.match_report.interview_questions):
            raise HTTPException(status_code=400, detail="面试题序号无效。")
        return await run_in_threadpool(
            generate_interview_answer_followup,
            pipeline.llm,
            report.jd_profile,
            candidate,
            request.question_index,
            request.candidate_answer,
        )

    @app.post("/api/runs/{run_id}/interviews")
    def start_interview(run_id: str, request: InterviewStartRequest):
        report = pipeline.get_run(run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="未找到该运行记录。")
        candidate = next(
            (item for item in report.candidates if item.candidate_id == request.candidate_id),
            None,
        )
        if candidate is None:
            raise HTTPException(status_code=404, detail="未找到该候选人。")
        session = create_interview_session(report, candidate, request.mode, pipeline.skill_repository)
        pipeline.storage.save_interview_session(session)
        return session

    @app.get("/api/interviews")
    def list_interviews(run_id: Optional[str] = None):
        return pipeline.storage.list_interview_sessions(run_id=run_id)

    @app.get("/api/interviews/{session_id}")
    def get_interview(session_id: str):
        session = pipeline.storage.get_interview_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="未找到该面试会话。")
        return session

    @app.post("/api/interviews/{session_id}/turns")
    async def create_interview_turn(session_id: str, request: InterviewTurnRequest):
        session = pipeline.storage.get_interview_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="未找到该面试会话。")
        report = pipeline.get_run(session.run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="未找到该运行记录。")
        candidate = next(
            (item for item in report.candidates if item.candidate_id == session.candidate_id),
            None,
        )
        if candidate is None:
            raise HTTPException(status_code=404, detail="未找到该候选人。")
        try:
            updated = await run_in_threadpool(
                submit_interview_turn,
                pipeline.llm,
                report,
                candidate,
                session,
                request.candidate_answer,
                pipeline.skill_repository,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        pipeline.storage.save_interview_session(updated)
        return updated

    @app.post("/api/interviews/{session_id}/final-report")
    def create_interview_final_report(session_id: str):
        session = pipeline.storage.get_interview_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="未找到该面试会话。")
        updated = finalize_interview_session(session)
        pipeline.storage.save_interview_session(updated)
        return updated

    @app.delete("/api/interviews/{session_id}", status_code=204)
    def delete_interview(session_id: str):
        deleted = pipeline.storage.delete_interview_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="未找到该面试会话。")
        return Response(status_code=204)

    @app.get("/api/settings/model-providers")
    def get_model_providers() -> ModelProviderSettingsResponse:
        default_id = _current_model_provider_id(pipeline, model_providers)
        return _model_provider_response(model_providers, default_id)

    @app.put("/api/settings/model-providers/default")
    def update_default_model_provider(request: ModelProviderDefaultRequest) -> ModelProviderSettingsResponse:
        provider_id = request.provider_id.strip()
        if provider_id not in model_providers:
            raise HTTPException(status_code=400, detail="未知模型服务。")
        pipeline.storage.set_setting(MODEL_PROVIDER_SETTING_KEY, provider_id)
        _apply_model_provider(pipeline, model_providers[provider_id])
        return _model_provider_response(model_providers, provider_id)

    @app.put("/api/settings/model-providers/{provider_id}/api-key")
    def update_model_provider_api_key(
        provider_id: str,
        request: ModelProviderApiKeyRequest,
    ) -> ModelProviderSettingsResponse:
        provider_id = provider_id.strip()
        if provider_id not in model_providers:
            raise HTTPException(status_code=400, detail="未知模型服务。")
        api_key = request.api_key.strip()
        if not api_key:
            raise HTTPException(status_code=400, detail="API Key 不能为空。")

        pipeline.storage.set_setting(_api_key_setting_key(provider_id), api_key)
        model_providers[provider_id] = replace(
            model_providers[provider_id],
            api_key=api_key,
            api_key_source="saved",
        )
        current_provider_id = _current_model_provider_id(pipeline, model_providers)
        if current_provider_id == provider_id:
            _apply_model_provider(pipeline, model_providers[provider_id])
        return _model_provider_response(model_providers, current_provider_id)

    @app.get("/api/runs/{run_id}/export")
    def export_run(run_id: str) -> Response:
        report = pipeline.get_run(run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="未找到该运行记录。")
        payload = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
        return Response(
            content=payload,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="recruiting-report-{run_id}.json"'},
        )

    return app


def _api_key_setting_key(provider_id: str) -> str:
    return f"{MODEL_PROVIDER_API_KEY_SETTING_PREFIX}{provider_id}"


def _model_provider_specs(
    settings: Settings,
    setting_reader: Optional[Callable[[str], Optional[str]]] = None,
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


def _apply_model_provider(pipeline: RecruitingPipeline, provider: ModelProviderSpec) -> None:
    pipeline.settings.llm_base_url = provider.base_url
    pipeline.settings.llm_api_key = provider.api_key
    pipeline.settings.llm_model = provider.model
    pipeline.llm = LLMClient(provider.base_url, provider.api_key, provider.model)


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


def _current_model_provider_id(
    pipeline: RecruitingPipeline,
    providers: dict[str, ModelProviderSpec],
) -> str:
    stored = pipeline.storage.get_setting(MODEL_PROVIDER_SETTING_KEY)
    if stored in providers:
        stored_provider = providers[stored]
        if stored_provider.base_url == pipeline.settings.llm_base_url and stored_provider.model == pipeline.settings.llm_model:
            return stored
    for provider_id, provider in providers.items():
        if provider.base_url == pipeline.settings.llm_base_url and provider.model == pipeline.settings.llm_model:
            return provider_id
    return "openai-compatible"


def _model_provider_response(
    providers: dict[str, ModelProviderSpec],
    default_provider_id: str,
) -> ModelProviderSettingsResponse:
    return ModelProviderSettingsResponse(
        default_provider_id=default_provider_id,
        providers=[
            {
                "id": provider.id,
                "name": provider.name,
                "model": provider.model,
                "base_url": provider.base_url,
                "api_key_configured": bool(provider.api_key),
                "api_key_source": provider.api_key_source,
                "is_default": provider.id == default_provider_id,
            }
            for provider in providers.values()
        ],
    )


async def _collect_jd(jd_file: Optional[UploadFile], jd_text: Optional[str]) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    parts: List[str] = []
    if jd_text and jd_text.strip():
        parts.append(jd_text.strip())
    if jd_file is not None and jd_file.filename:
        try:
            content = await jd_file.read()
            parsed = extract_text_from_bytes(jd_file.filename, content)
            if parsed:
                parts.insert(0, parsed)
        except DocumentParseError as exc:
            warnings.append(str(exc))
    return "\n\n".join(parts), warnings


async def _collect_resumes(
    resume_files: Optional[List[UploadFile]], resume_texts: Optional[List[str]], warnings: List[str]
) -> List[Tuple[str, str]]:
    resumes: List[Tuple[str, str]] = []
    for index, text in enumerate(resume_texts or []):
        if text and text.strip():
            resumes.append((f"文本简历 {index + 1}", text.strip()))
    for upload in resume_files or []:
        if upload is None or not upload.filename:
            continue
        try:
            content = await upload.read()
            parsed = extract_text_from_bytes(upload.filename, content)
            if parsed:
                resumes.append((upload.filename, parsed))
        except DocumentParseError as exc:
            warnings.append(str(exc))
    return resumes


app = create_app()
