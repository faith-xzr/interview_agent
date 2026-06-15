from __future__ import annotations

from hashlib import sha256

from app.pipeline import RecruitingPipeline
from app.scoring import score_resume_quality
from app.schemas import ResumeAnalysisStatus


MAX_RESUME_UPLOAD_BYTES = 10 * 1024 * 1024


def file_hash(content: bytes) -> str:
    return sha256(content).hexdigest()


def validate_resume_content(content: bytes) -> None:
    if not content:
        raise ValueError("未检测到可分析的简历文本")
    if len(content) > MAX_RESUME_UPLOAD_BYTES:
        raise ValueError("上传文件大小不能超过 10MB")


def analyze_resume_in_background(pipeline: RecruitingPipeline, resume_id: int) -> None:
    """Run resume scoring in background and persist result into storage."""
    storage = pipeline.storage
    storage.set_resume_analysis_status(resume_id, ResumeAnalysisStatus.PROCESSING)
    try:
        record = storage.get_resume(resume_id)
        if record is None:
            return
        resume_text = str(record["resume_text"])
        profile, extraction_facts = pipeline._extract_candidate(resume_text, "standalone_resume", [])
        report = score_resume_quality(pipeline.llm, resume_text, profile, extraction_facts)
        report = report.model_copy(update={"original_text": resume_text})
        storage.save_resume_analysis(resume_id, report, original_text=resume_text)
        storage.set_resume_analysis_status(resume_id, ResumeAnalysisStatus.COMPLETED)
    except Exception as exc:
        storage.set_resume_analysis_status(resume_id, ResumeAnalysisStatus.FAILED, str(exc))


def build_upload_storage_payload(resume_id: int) -> dict[str, object]:
    return {
        "file_key": "",
        "file_url": "",
        "resume_id": resume_id,
    }
