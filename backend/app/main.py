import json
from typing import List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.config import Settings, settings_from_env
from app.extraction.document_parser import DocumentParseError, extract_text_from_bytes
from app.interview_followup import generate_interview_answer_followup
from app.interview_session import create_interview_session, finalize_interview_session, submit_interview_turn
from app.llm_client import LLMClient
from app.model_providers import ModelProviderService, ModelProviderSpec
from app.pipeline import RecruitingPipeline
from app.schemas import (
    InterviewAnswerFollowUpRequest,
    InterviewStartRequest,
    InterviewTurnRequest,
    ModelProviderApiKeyRequest,
    ModelProviderDefaultRequest,
    ModelProviderSettingsResponse,
)


def create_app(settings: Settings = None) -> FastAPI:
    app_settings = settings or settings_from_env()
    pipeline = RecruitingPipeline(app_settings)
    model_provider_service = ModelProviderService(
        app_settings,
        pipeline.storage.get_setting,
        pipeline.storage.set_setting,
    )
    _apply_model_provider(pipeline, model_provider_service.default_provider())
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
            "model_provider": model_provider_service.current_provider_id(
                pipeline.settings.llm_base_url,
                pipeline.settings.llm_model,
            ),
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
        default_id = model_provider_service.current_provider_id(
            pipeline.settings.llm_base_url,
            pipeline.settings.llm_model,
        )
        return model_provider_service.settings_response(default_id)

    @app.put("/api/settings/model-providers/default")
    def update_default_model_provider(request: ModelProviderDefaultRequest) -> ModelProviderSettingsResponse:
        try:
            provider = model_provider_service.set_default(request.provider_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="未知模型服务。")
        _apply_model_provider(pipeline, provider)
        return model_provider_service.settings_response(provider.id)

    @app.put("/api/settings/model-providers/{provider_id}/api-key")
    def update_model_provider_api_key(
        provider_id: str,
        request: ModelProviderApiKeyRequest,
    ) -> ModelProviderSettingsResponse:
        try:
            provider = model_provider_service.set_api_key(provider_id, request.api_key)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        current_provider_id = model_provider_service.current_provider_id(
            pipeline.settings.llm_base_url,
            pipeline.settings.llm_model,
        )
        if current_provider_id == provider.id:
            _apply_model_provider(pipeline, provider)
        return model_provider_service.settings_response(current_provider_id)

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


def _apply_model_provider(pipeline: RecruitingPipeline, provider: ModelProviderSpec) -> None:
    pipeline.settings.llm_base_url = provider.base_url
    pipeline.settings.llm_api_key = provider.api_key
    pipeline.settings.llm_model = provider.model
    pipeline.llm = LLMClient(provider.base_url, provider.api_key, provider.model)


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
