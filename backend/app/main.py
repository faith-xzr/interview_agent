import asyncio
import json
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool

from app.config import Settings, settings_from_env
from app.extraction.document_parser import DocumentParseError, extract_text_from_bytes
from app.interview_followup import generate_interview_answer_followup
from app.interview_session import create_interview_session, finalize_interview_session, submit_interview_turn
from app.llm_client import LLMClient
from app.resume_standalone import (
    analyze_resume_in_background,
    build_upload_storage_payload,
    file_hash,
    validate_resume_content,
)
from app.model_providers import ModelProviderService, ModelProviderSpec
from app.pipeline import RecruitingPipeline, ResumeSource
from app.schemas import (
    ResumeAnalysisHistoryItem,
    InterviewAnswerFollowUpRequest,
    ResumeFileSummary,
    InterviewStartRequest,
    InterviewTurnRequest,
    InterviewTurnInputMetadata,
    ModelProviderApiKeyRequest,
    ModelProviderDefaultRequest,
    ModelProviderSettingsResponse,
    ResumeListItem,
    ResumeQualityScoreDetail,
    ResumeQualitySuggestion,
    ResumeQualityReport,
    ResumeUploadResponse,
    ResumeAnalysisStatus,
    ResumeDetailResponse,
    VoiceInterviewCreateRequest,
    VoiceInterviewSession,
    VoiceSettingsResponse,
    VoiceSettingsUpdateRequest,
)
from app.scoring import score_resume_quality
from app.skills import route_skill_for_jd
from app.voice import DashScopeAsrStream, DashScopeTtsClient


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

        existing_run = pipeline.get_latest_run_for_jd(jd_content)
        if existing_run is not None:
            report = await run_in_threadpool(
                pipeline.run,
                jd_content,
                resumes,
                warnings,
                existing_run,
            )
        else:
            report = await run_in_threadpool(pipeline.run, jd_content, resumes, warnings)
        return report

    @app.post("/api/resume-score", response_model=ResumeQualityReport)
    async def score_resume_only(
        resume_file: Optional[UploadFile] = File(None),
        resume_text: Optional[str] = Form(None),
    ):
        resume_text_value = await _collect_single_resume(resume_file, resume_text)
        if not resume_text_value:
            raise HTTPException(status_code=400, detail="未提供简历内容，请上传简历或粘贴简历文本。")

        profile, extraction_facts = pipeline._extract_candidate(resume_text_value, "standalone_resume", [])
        report = score_resume_quality(pipeline.llm, resume_text_value, profile, extraction_facts)
        return report.model_copy(update={"original_text": resume_text_value})

    @app.post("/api/resumes/upload", response_model=ResumeUploadResponse)
    async def upload_resume_with_async_analysis(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
    ):
        content = await file.read()
        filename = file.filename or "resume"
        try:
            validate_resume_content(content)
            file_hash_value = file_hash(content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        existing = pipeline.storage.get_resume_by_hash(file_hash_value)
        if existing is not None:
            resume_id = int(existing["resume_id"])
            pipeline.storage.increment_resume_access_count(resume_id)
            latest = pipeline.storage.get_latest_resume_analysis(resume_id)
            return ResumeUploadResponse(
                resume=_resume_row_to_file_summary(existing),
                analysis=_analysis_row_to_report(latest),
                storage=build_upload_storage_payload(resume_id),
                duplicate=True,
            )

        try:
            parsed_text = extract_text_from_bytes(filename, content)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"解析简历失败：{exc}") from exc
        if not parsed_text.strip():
            raise HTTPException(status_code=400, detail="未检测到可分析的简历文本内容，请检查文件是否可读。")

        resume_id = pipeline.storage.save_resume_record(
            file_hash_value,
            filename,
            len(content),
            file.content_type,
            parsed_text,
            "",
            "",
        )
        background_tasks.add_task(analyze_resume_in_background, pipeline, resume_id)

        return ResumeUploadResponse(
            resume=ResumeFileSummary(
                id=resume_id,
                filename=filename,
                analyze_status=ResumeAnalysisStatus.PENDING,
            ),
            analysis=None,
            storage=build_upload_storage_payload(resume_id),
            duplicate=False,
        )

    @app.get("/api/resumes", response_model=List[ResumeListItem])
    def list_resumes():
        return [_resume_row_to_list_item(item) for item in pipeline.storage.list_resumes()]

    @app.get("/api/resumes/{resume_id}/detail", response_model=ResumeDetailResponse)
    def get_resume_detail(resume_id: int):
        record = pipeline.storage.get_resume(resume_id)
        if record is None:
            raise HTTPException(status_code=404, detail="未找到对应简历记录。")
        analyses = pipeline.storage.get_resume_analyses(resume_id)
        return ResumeDetailResponse(
            id=int(record["resume_id"]),
            filename=str(record["filename"]),
            file_size=int(record["file_size"]),
            content_type=record.get("content_type"),
            uploaded_at=datetime.fromisoformat(record["uploaded_at"]),
            access_count=int(record["access_count"]),
            analyze_status=str(record["analyze_status"]),
            analyze_error=record.get("analyze_error"),
            resume_text=record["resume_text"],
            analyses=[
                _analysis_row_to_history_item(item)
                for item in analyses
            ],
        )

    @app.post("/api/resumes/{resume_id}/reanalyze")
    async def reanalyze_resume(resume_id: int, background_tasks: BackgroundTasks):
        record = pipeline.storage.get_resume(resume_id)
        if record is None:
            raise HTTPException(status_code=404, detail="未找到对应简历记录。")
        pipeline.storage.set_resume_analysis_status(
            resume_id,
            ResumeAnalysisStatus.PENDING,
            None,
        )
        background_tasks.add_task(analyze_resume_in_background, pipeline, resume_id)
        return {"status": "submitted", "resume_id": resume_id}

    @app.get("/api/resumes/health")
    def resume_health():
        return {
            "status": "UP",
            "service": "AI Interview Platform - Resume Service",
        }

    @app.delete("/api/resumes/{resume_id}")
    def delete_resume(resume_id: int):
        if not pipeline.storage.delete_resume(resume_id):
            raise HTTPException(status_code=404, detail="未找到对应简历记录。")
        return Response(status_code=204)

    @app.delete("/api/resumes")
    def delete_all_resumes():
        pipeline.storage.delete_all_resumes()
        return Response(status_code=204)

    @app.get("/api/resumes/{resume_id}/export")
    def export_resume_report(resume_id: int):
        latest = pipeline.storage.get_latest_resume_analysis(resume_id)
        if latest is None:
            raise HTTPException(status_code=404, detail="该简历尚未完成分析，无法导出报告。")
        report_payload = _analysis_row_to_report(latest)
        payload = {
            "resume_id": resume_id,
            "report": report_payload.model_dump(mode="json") if report_payload is not None else None,
        }
        return Response(
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="resume-analysis-{resume_id}.json"'},
        )

    @app.get("/api/runs")
    def list_runs():
        return pipeline.storage.list_runs()

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        report = pipeline.get_run(run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="未找到该运行记录。")
        return report

    @app.get("/api/runs/{run_id}/candidates/{candidate_id}/source-file")
    def get_run_candidate_source_file(run_id: str, candidate_id: str):
        report = pipeline.get_run(run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="未找到该运行记录。")
        candidate = next((item for item in report.candidates if item.candidate_id == candidate_id), None)
        if candidate is None or candidate.source_file is None:
            raise HTTPException(status_code=404, detail="未找到该候选人的源文件。")
        file_path = pipeline.get_candidate_source_file_path(run_id, candidate_id, candidate.source_file)
        if file_path is None:
            raise HTTPException(status_code=404, detail="源文件不存在。")
        return FileResponse(
            file_path,
            media_type=candidate.source_file.content_type or "application/octet-stream",
            filename=candidate.source_file.filename,
            content_disposition_type="inline",
        )

    @app.delete("/api/runs/{run_id}/candidates/{candidate_id}")
    def delete_run_candidate(run_id: str, candidate_id: str):
        report = pipeline.get_run(run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="未找到该运行记录。")
        if not any(item.candidate_id == candidate_id for item in report.candidates):
            raise HTTPException(status_code=404, detail="未找到该候选人。")
        updated = pipeline.remove_candidate(run_id, candidate_id)
        if updated is None:
            return Response(status_code=204)
        return updated

    @app.delete("/api/runs", status_code=204)
    def delete_all_runs():
        pipeline.remove_all_runs()
        return Response(status_code=204)

    @app.get("/api/runs/{run_id}/skill-route")
    def get_skill_route(run_id: str):
        report = pipeline.get_run(run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="未找到该运行记录。")
        return route_skill_for_jd(
            pipeline.llm,
            report.jd_profile,
            report.jd_extraction_facts,
            pipeline.skill_repository,
        )

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
        session = create_interview_session(
            report,
            candidate,
            request.mode,
            pipeline.skill_repository,
            skill_id=request.skill_id,
        )
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
                request.answer_metadata,
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

    @app.get("/api/settings/voice")
    def get_voice_settings() -> VoiceSettingsResponse:
        return _voice_settings_response(app_settings, pipeline.storage)

    @app.put("/api/settings/voice")
    def update_voice_settings(request: VoiceSettingsUpdateRequest) -> VoiceSettingsResponse:
        _save_voice_settings(pipeline.storage, request)
        return _voice_settings_response(app_settings, pipeline.storage)

    @app.post("/api/voice-interviews")
    def create_voice_interview(request: VoiceInterviewCreateRequest) -> VoiceInterviewSession:
        interview_session = pipeline.storage.get_interview_session(request.interview_session_id)
        if interview_session is None:
            raise HTTPException(status_code=404, detail="未找到该面试会话。")
        now = datetime.utcnow()
        voice_session_id = uuid4().hex
        voice_session = VoiceInterviewSession(
            voice_session_id=voice_session_id,
            interview_session_id=interview_session.session_id,
            status="active",
            websocket_url=f"/ws/voice-interviews/{voice_session_id}",
            created_at=now,
            updated_at=now,
        )
        pipeline.storage.save_voice_interview_session(voice_session)
        return voice_session

    @app.get("/api/voice-interviews/{voice_session_id}")
    def get_voice_interview(voice_session_id: str) -> VoiceInterviewSession:
        voice_session = pipeline.storage.get_voice_interview_session(voice_session_id)
        if voice_session is None:
            raise HTTPException(status_code=404, detail="未找到该语音面试会话。")
        return voice_session

    @app.websocket("/ws/voice-interviews/{voice_session_id}")
    async def voice_interview_socket(websocket: WebSocket, voice_session_id: str):
        await websocket.accept()
        voice_session = pipeline.storage.get_voice_interview_session(voice_session_id)
        if voice_session is None:
            await websocket.send_json({"type": "error", "message": "未找到该语音面试会话。"})
            await websocket.close(code=1008)
            return
        outbound_queue: asyncio.Queue = asyncio.Queue()
        sender_task = asyncio.create_task(_send_voice_socket_messages(websocket, outbound_queue))
        await outbound_queue.put({
            "type": "control",
            "action": "ready",
            "message": "语音面试通道已连接。",
        })
        voice_settings = _voice_settings_response(app_settings, pipeline.storage)
        dashscope_api_key = _dashscope_api_key(app_settings, pipeline.storage)
        asr_stream = None
        initial_tts_task = None

        async def handle_asr_subtitle(subtitle: dict) -> None:
            await outbound_queue.put(subtitle)
            if subtitle.get("isFinal"):
                await _submit_voice_transcript_and_stream_tts(
                    voice_session.interview_session_id,
                    str(subtitle.get("text") or ""),
                    pipeline,
                    outbound_queue,
                    dashscope_api_key,
                    voice_settings,
                )

        async def handle_asr_error(message: str) -> None:
            await outbound_queue.put({"type": "error", "message": message})

        if dashscope_api_key:
            asr_stream = DashScopeAsrStream(
                dashscope_api_key,
                voice_settings.asr,
                handle_asr_subtitle,
                handle_asr_error,
            )
            try:
                await asr_stream.connect()
            except Exception as exc:
                asr_stream = None
                await outbound_queue.put({
                    "type": "control",
                    "action": "cloud_voice_unavailable",
                    "message": f"百炼实时语音连接失败：{exc}",
                })
        interview_session = pipeline.storage.get_interview_session(voice_session.interview_session_id)
        if interview_session is not None:
            initial_tts_task = asyncio.create_task(
                _stream_current_question_tts(
                    interview_session,
                    outbound_queue,
                    dashscope_api_key,
                    voice_settings,
                )
            )
        try:
            while True:
                message = await websocket.receive_json()
                message_type = str(message.get("type", "")).strip()
                if message_type == "control" and message.get("action") == "submit_text":
                    text = str(message.get("text", "")).strip()
                    if not text:
                        await outbound_queue.put({"type": "error", "message": "识别文本不能为空。"})
                        continue
                    await outbound_queue.put({"type": "subtitle", "text": text, "isFinal": True})
                    try:
                        updated_session = await _submit_voice_transcript(
                            voice_session.interview_session_id,
                            text,
                            pipeline,
                        )
                    except ValueError as exc:
                        await outbound_queue.put({"type": "error", "message": str(exc)})
                        continue
                    except HTTPException as exc:
                        await outbound_queue.put({"type": "error", "message": str(exc.detail)})
                        continue
                    await outbound_queue.put({
                        "type": "interview_session",
                        "session": updated_session.model_dump(mode="json"),
                    })
                elif message_type == "control" and message.get("action") == "speak_current_question":
                    current_session = pipeline.storage.get_interview_session(voice_session.interview_session_id)
                    if current_session is None:
                        await outbound_queue.put({"type": "error", "message": "未找到该面试会话。"})
                        continue
                    await _stream_current_question_tts(
                        current_session,
                        outbound_queue,
                        dashscope_api_key,
                        voice_settings,
                    )
                elif message_type == "audio":
                    audio_base64 = str(message.get("data") or "").strip()
                    if not audio_base64:
                        await outbound_queue.put({"type": "error", "message": "音频数据不能为空。"})
                    elif asr_stream is None:
                        await outbound_queue.put({
                            "type": "control",
                            "action": "cloud_voice_unavailable",
                            "message": "未检测到可用的百炼实时语音连接，请先配置百炼 API Key 或使用文本提交。",
                        })
                    else:
                        await asr_stream.append_audio(audio_base64)
                elif message_type == "control" and message.get("action") in {"stop", "close"}:
                    await websocket.close(code=1000)
                    return
                else:
                    await outbound_queue.put({"type": "error", "message": "不支持的语音消息类型。"})
        except WebSocketDisconnect:
            return
        finally:
            if initial_tts_task is not None and not initial_tts_task.done():
                initial_tts_task.cancel()
            if asr_stream is not None:
                await asr_stream.close()
            await outbound_queue.put(None)
            try:
                await sender_task
            except Exception:
                pass

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


async def _submit_voice_transcript(
    interview_session_id: str,
    text: str,
    pipeline: RecruitingPipeline,
):
    session = pipeline.storage.get_interview_session(interview_session_id)
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
    metadata = InterviewTurnInputMetadata(
        source="speech",
        transcript=text,
        locale="zh-CN",
        finalized=True,
        raw_text=text,
    )
    updated = await run_in_threadpool(
        submit_interview_turn,
        pipeline.llm,
        report,
        candidate,
        session,
        text,
        metadata,
        pipeline.skill_repository,
    )
    pipeline.storage.save_interview_session(updated)
    return updated


async def _submit_voice_transcript_and_stream_tts(
    interview_session_id: str,
    text: str,
    pipeline: RecruitingPipeline,
    outbound_queue: asyncio.Queue,
    dashscope_api_key: Optional[str],
    voice_settings: VoiceSettingsResponse,
) -> None:
    try:
        updated_session = await _submit_voice_transcript(interview_session_id, text, pipeline)
    except ValueError as exc:
        await outbound_queue.put({"type": "error", "message": str(exc)})
        return
    except HTTPException as exc:
        await outbound_queue.put({"type": "error", "message": str(exc.detail)})
        return

    await outbound_queue.put({
        "type": "interview_session",
        "session": updated_session.model_dump(mode="json"),
    })
    next_question = updated_session.current_question.question if updated_session.current_question else ""
    if not dashscope_api_key or not next_question:
        return
    await _stream_tts_audio(outbound_queue, dashscope_api_key, voice_settings, next_question)


async def _stream_current_question_tts(
    session,
    outbound_queue: asyncio.Queue,
    dashscope_api_key: Optional[str],
    voice_settings: VoiceSettingsResponse,
) -> None:
    if not dashscope_api_key or session.current_question is None:
        return
    await _stream_tts_audio(
        outbound_queue,
        dashscope_api_key,
        voice_settings,
        session.current_question.question,
    )


async def _stream_tts_audio(
    outbound_queue: asyncio.Queue,
    dashscope_api_key: str,
    voice_settings: VoiceSettingsResponse,
    text: str,
) -> None:
    index = 0
    try:
        async for audio_delta in DashScopeTtsClient(dashscope_api_key, voice_settings.tts).synthesize(text):
            await outbound_queue.put({
                "type": "audio_chunk",
                "data": audio_delta,
                "index": index,
                "isLast": False,
            })
            index += 1
        await outbound_queue.put({
            "type": "audio_chunk",
            "data": "",
            "index": index,
            "isLast": True,
        })
    except Exception as exc:
        await outbound_queue.put({"type": "error", "message": f"百炼 TTS 生成失败：{exc}"})


async def _send_voice_socket_messages(websocket: WebSocket, outbound_queue: asyncio.Queue) -> None:
    while True:
        message = await outbound_queue.get()
        if message is None:
            return
        await websocket.send_json(message)


def _voice_settings_response(app_settings: Settings, storage) -> VoiceSettingsResponse:
    saved_dashscope_key = storage.get_setting("model_provider_api_key:dashscope")
    if saved_dashscope_key and saved_dashscope_key.strip():
        api_key_configured = True
        api_key_source = "saved"
    elif app_settings.dashscope_api_key:
        api_key_configured = True
        api_key_source = "env"
    else:
        api_key_configured = False
        api_key_source = "none"
    response = VoiceSettingsResponse(
        api_key_configured=api_key_configured,
        api_key_source=api_key_source,
    )
    response.asr.model = _setting_or_default(storage, "voice.asr.model", response.asr.model)
    response.asr.sample_rate = _int_setting_or_default(storage, "voice.asr.sample_rate", response.asr.sample_rate)
    response.asr.input_audio_format = _setting_or_default(
        storage,
        "voice.asr.input_audio_format",
        response.asr.input_audio_format,
    )
    response.asr.language = _setting_or_default(storage, "voice.asr.language", response.asr.language)
    response.asr.server_vad = _bool_setting_or_default(storage, "voice.asr.server_vad", response.asr.server_vad)
    response.asr.silence_duration_ms = _int_setting_or_default(
        storage,
        "voice.asr.silence_duration_ms",
        response.asr.silence_duration_ms,
    )
    response.tts.model = _setting_or_default(storage, "voice.tts.model", response.tts.model)
    response.tts.voice = _setting_or_default(storage, "voice.tts.voice", response.tts.voice)
    response.tts.response_format = _setting_or_default(
        storage,
        "voice.tts.response_format",
        response.tts.response_format,
    )
    response.tts.sample_rate = _int_setting_or_default(storage, "voice.tts.sample_rate", response.tts.sample_rate)
    return response


def _dashscope_api_key(app_settings: Settings, storage) -> Optional[str]:
    saved = storage.get_setting("model_provider_api_key:dashscope")
    if saved and saved.strip():
        return saved.strip()
    return app_settings.dashscope_api_key


def _save_voice_settings(storage, request: VoiceSettingsUpdateRequest) -> None:
    if request.asr is not None:
        storage.set_setting("voice.asr.model", request.asr.model)
        storage.set_setting("voice.asr.sample_rate", str(request.asr.sample_rate))
        storage.set_setting("voice.asr.input_audio_format", request.asr.input_audio_format)
        storage.set_setting("voice.asr.language", request.asr.language)
        storage.set_setting("voice.asr.server_vad", "true" if request.asr.server_vad else "false")
        storage.set_setting("voice.asr.silence_duration_ms", str(request.asr.silence_duration_ms))
    if request.tts is not None:
        storage.set_setting("voice.tts.model", request.tts.model)
        storage.set_setting("voice.tts.voice", request.tts.voice)
        storage.set_setting("voice.tts.response_format", request.tts.response_format)
        storage.set_setting("voice.tts.sample_rate", str(request.tts.sample_rate))


def _setting_or_default(storage, key: str, default: str) -> str:
    value = storage.get_setting(key)
    return value.strip() if value and value.strip() else default


def _int_setting_or_default(storage, key: str, default: int) -> int:
    value = storage.get_setting(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _bool_setting_or_default(storage, key: str, default: bool) -> bool:
    value = storage.get_setting(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
) -> List[ResumeSource]:
    resumes: List[ResumeSource] = []
    for index, text in enumerate(resume_texts or []):
        if text and text.strip():
            resumes.append(ResumeSource(source_name=f"文本简历 {index + 1}", text=text.strip()))
    for upload in resume_files or []:
        if upload is None or not upload.filename:
            continue
        try:
            content = await upload.read()
            parsed = extract_text_from_bytes(upload.filename, content)
            if parsed:
                resumes.append(
                    ResumeSource(
                        source_name=upload.filename,
                        text=parsed,
                        file_content=content,
                        content_type=upload.content_type,
                    )
                )
        except DocumentParseError as exc:
            warnings.append(str(exc))
    return resumes


async def _collect_single_resume(
    resume_file: Optional[UploadFile], resume_text: Optional[str]
) -> Optional[str]:
    if resume_file is not None and resume_file.filename:
        try:
            content = await resume_file.read()
            parsed = extract_text_from_bytes(resume_file.filename, content)
            if parsed:
                return parsed
        except DocumentParseError:
            pass
    if resume_text and resume_text.strip():
        return resume_text.strip()
    return None


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if value is None:
        raise ValueError("empty datetime")
    return datetime.fromisoformat(str(value))


def _coerce_str_list(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [item.strip() for item in value.split("|") if item.strip()]
    elif isinstance(value, list):
        parsed = value
    else:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _coerce_suggestion_list(value: object) -> List[ResumeQualitySuggestion]:
    if value is None:
        return []

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
    elif isinstance(value, list):
        parsed = value
    else:
        return []

    if not isinstance(parsed, list):
        return []
    suggestions: List[ResumeQualitySuggestion] = []
    for raw in parsed:
        if isinstance(raw, ResumeQualitySuggestion):
            suggestions.append(raw)
            continue
        if isinstance(raw, dict):
            try:
                suggestions.append(ResumeQualitySuggestion.model_validate(raw))
            except Exception:
                continue
    return suggestions


def _analysis_row_to_report(analysis_row: Optional[dict[str, object]]) -> Optional[ResumeQualityReport]:
    if analysis_row is None:
        return None
    return ResumeQualityReport(
        overall_score=int(analysis_row["overall_score"]),
        score_detail=ResumeQualityScoreDetail(
            project_score=int(analysis_row["project_score"]),
            skill_match_score=int(analysis_row["skill_match_score"]),
            content_score=int(analysis_row["content_score"]),
            structure_score=int(analysis_row["structure_score"]),
            expression_score=int(analysis_row["expression_score"]),
        ),
        summary=str(analysis_row.get("summary", "")),
        original_text=analysis_row.get("original_text"),
        strengths=_coerce_str_list(analysis_row.get("strengths_json")),
        suggestions=_coerce_suggestion_list(analysis_row.get("suggestions_json")),
    )


def _analysis_row_to_history_item(analysis_row: dict[str, object]) -> ResumeAnalysisHistoryItem:
    report = _analysis_row_to_report(analysis_row)
    if report is None:
        raise ValueError("无效的分析记录")
    return ResumeAnalysisHistoryItem(
        analysis_id=int(analysis_row["analysis_id"]),
        created_at=_coerce_datetime(analysis_row["created_at"]),
        overall_score=report.overall_score,
        score_detail=report.score_detail,
        summary=report.summary,
        strengths=report.strengths,
        suggestions=report.suggestions,
        original_text=analysis_row.get("original_text"),  # type: ignore[arg-type]
    )


def _resume_row_to_list_item(resume_row: dict[str, object]) -> ResumeListItem:
    last_analyzed_at = None
    if resume_row.get("last_analyzed_at") is not None:
        last_analyzed_at = _coerce_datetime(resume_row["last_analyzed_at"])

    return ResumeListItem(
        id=int(resume_row["resume_id"]),
        filename=str(resume_row["filename"]),
        file_size=int(resume_row["file_size"]),
        uploaded_at=_coerce_datetime(resume_row["uploaded_at"]),
        access_count=int(resume_row["access_count"]),
        latest_score=(
            int(resume_row["latest_score"]) if resume_row.get("latest_score") is not None else None
        ),
        last_analyzed_at=last_analyzed_at,
        analyze_status=str(resume_row["analyze_status"]),
        analyze_error=resume_row.get("analyze_error"),
    )


def _resume_row_to_file_summary(resume_row: dict[str, object]) -> ResumeFileSummary:
    return ResumeFileSummary(
        id=int(resume_row["resume_id"]),
        filename=str(resume_row["filename"]),
        analyze_status=str(resume_row["analyze_status"]),
    )


app = create_app()
