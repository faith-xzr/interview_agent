import json
from typing import List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.config import Settings, settings_from_env
from app.extraction.document_parser import DocumentParseError, extract_text_from_bytes
from app.pipeline import RecruitingPipeline


def create_app(settings: Settings = None) -> FastAPI:
    app_settings = settings or settings_from_env()
    pipeline = RecruitingPipeline(app_settings)
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
        return {"status": "ok", "llm_enabled": pipeline.llm.available}

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
        report = await run_in_threadpool(pipeline.run, jd_content, resumes)
        report.warnings.extend(warnings)
        pipeline.storage.save_run(report)
        return report

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        report = pipeline.get_run(run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="未找到该运行记录。")
        return report

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
