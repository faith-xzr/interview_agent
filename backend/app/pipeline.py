from datetime import datetime
from typing import List, Tuple
from uuid import uuid4

from app.config import Settings
from app.extraction.jd_extractor import extract_jd_facts
from app.extraction.resume_extractor import extract_resume_profile
from app.fallback_ai import extract_jd_profile
from app.followups import generate_followups
from app.llm_client import LLMClient
from app.privacy import mask_pii, restore_pii_in_data
from app.question_generation import generate_interview_questions
from app.schemas import CandidateProfile, CandidateReport, ExtractedFact, JDProfile, RunReport
from app.scoring import score_candidate
from app.storage import RunStorage
from app.vector_store import VectorStore


class RecruitingPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage = RunStorage(settings.database_path)
        self.vector_store = VectorStore(settings.vector_dir, enable_chroma=settings.enable_chroma)
        self.llm = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)

    def run(self, jd_text: str, resumes: List[Tuple[str, str]]) -> RunReport:
        run_id = uuid4().hex
        warnings: List[str] = []
        jd_profile = self._extract_jd(jd_text, warnings)
        jd_extraction_facts = extract_jd_facts(jd_text, jd_profile)
        query_text = " ".join(jd_profile.required_skills + jd_profile.responsibilities + [jd_profile.job_title])
        candidates: List[CandidateReport] = []

        self.vector_store.add_document(run_id, "jd", "JD", jd_text)
        for index, (source_name, resume_text) in enumerate(resumes):
            candidate_id = f"candidate-{index + 1}"
            profile, extraction_facts = self._extract_candidate(resume_text, source_name, warnings)
            self.vector_store.add_document(run_id, candidate_id, source_name, resume_text)
            evidence_texts = self.vector_store.query(run_id, candidate_id, query_text or jd_text, limit=5)
            match = score_candidate(jd_profile, profile, evidence_texts, extraction_facts)
            match.interview_questions = generate_interview_questions(jd_profile, profile, match)
            match.followup_questions = generate_followups(profile, match)
            candidates.append(
                CandidateReport(
                    candidate_id=candidate_id,
                    source_name=source_name,
                    profile=profile,
                    match_report=match,
                    extraction_facts=extraction_facts,
                )
            )

        candidates.sort(key=lambda item: item.match_report.total_score, reverse=True)
        report = RunReport(
            run_id=run_id,
            created_at=datetime.utcnow(),
            jd_profile=jd_profile,
            jd_extraction_facts=jd_extraction_facts,
            candidates=candidates,
            warnings=warnings,
        )
        self.storage.save_run(report)
        return report

    def get_run(self, run_id: str) -> RunReport:
        return self.storage.get_run(run_id)

    def _extract_jd(self, text: str, warnings: List[str]) -> JDProfile:
        llm_payload = self.llm.complete_json(
            "你是招聘 JD 结构化解析助手，只输出 JSON。",
            f"请解析以下 JD，字段包括 job_title responsibilities required_skills nice_to_have_skills seniority years_required industry_background hard_requirements。\n{text}",
        )
        if llm_payload:
            try:
                return JDProfile.model_validate(llm_payload)
            except Exception:
                warnings.append("LLM JD 解析结果结构不合法，已使用本地规则兜底。")
        elif self.llm.available:
            warnings.append("LLM JD 解析失败，已使用本地规则兜底。")
        return extract_jd_profile(text)

    def _extract_candidate(
        self, text: str, source_name: str, warnings: List[str]
    ) -> Tuple[CandidateProfile, List[ExtractedFact]]:
        initial_result = extract_resume_profile(text, source_name)
        initial_profile = initial_result.profile
        masked = mask_pii(text, candidate_name=initial_profile.name)
        llm_payload = self.llm.complete_json(
            "你是简历结构化解析助手，只输出 JSON。",
            "请解析以下已脱敏简历，字段包括 name target_role contacts location education work_experiences projects skills certifications highlights risk_points ambiguous_points。\n"
            + masked.text,
        )
        if llm_payload:
            try:
                restored = restore_pii_in_data(llm_payload, masked.replacements)
                profile = CandidateProfile.model_validate(restored)
                profile = _merge_candidate_profile(profile, initial_profile)
                return profile, initial_result.facts
            except Exception:
                warnings.append(f"{source_name} 的 LLM 简历解析结果结构不合法，已使用本地规则兜底。")
        elif self.llm.available:
            warnings.append(f"{source_name} 的 LLM 简历解析失败，已使用本地规则兜底。")
        return initial_profile, initial_result.facts


def _merge_candidate_profile(profile: CandidateProfile, fallback: CandidateProfile) -> CandidateProfile:
    if not profile.target_role:
        profile.target_role = fallback.target_role
    if not profile.contacts:
        profile.contacts = fallback.contacts
    if not profile.location:
        profile.location = fallback.location
    for field_name in (
        "education",
        "work_experiences",
        "projects",
        "skills",
        "certifications",
        "highlights",
        "risk_points",
        "ambiguous_points",
    ):
        if not getattr(profile, field_name):
            setattr(profile, field_name, getattr(fallback, field_name))
    return profile
