from datetime import datetime
from typing import List, Tuple
from uuid import uuid4

from app.config import Settings
from app.extraction.jd_extractor import extract_jd_facts
from app.extraction.llm_jd_extractor import extract_jd_with_llm
from app.extraction.llm_resume_extractor import extract_resume_with_llm
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
        jd_profile, jd_extraction_facts = self._extract_jd(jd_text, warnings)
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

    def _extract_jd(self, text: str, warnings: List[str]) -> Tuple[JDProfile, List[ExtractedFact]]:
        if self.llm.available:
            llm_result = extract_jd_with_llm(self.llm, text)
            if llm_result is not None:
                profile, facts = llm_result
                if facts:
                    return profile, facts
                warnings.append("JD 的 LLM 抽取未返回可用事实，已回退本地规则结果。")
            else:
                warnings.append("JD 的 LLM 抽取失败，已回退本地规则结果。")
        return self._extract_jd_with_rules(text)

    def _extract_jd_with_rules(self, text: str) -> Tuple[JDProfile, List[ExtractedFact]]:
        profile = extract_jd_profile(text)
        facts = extract_jd_facts(text, profile)
        return profile, facts

    def _extract_candidate(
        self, text: str, source_name: str, warnings: List[str]
    ) -> Tuple[CandidateProfile, List[ExtractedFact]]:
        initial_result = extract_resume_profile(text, source_name)
        initial_profile = initial_result.profile
        if self.llm.available:
            masked = mask_pii(text, candidate_name=initial_profile.name)
            llm_result = extract_resume_with_llm(self.llm, masked.text, source_name)
            if llm_result is not None:
                processed_profile, processed_facts = llm_result
                restored_profile = restore_pii_in_data(processed_profile.model_dump(mode="json"), masked.replacements)
                restored_facts = restore_pii_in_data(
                    [fact.model_dump(mode="json") for fact in processed_facts],
                    masked.replacements,
                )
                profile = CandidateProfile.model_validate(restored_profile)
                extraction_facts = [ExtractedFact.model_validate(fact) for fact in restored_facts]
                return _merge_candidate_profile(profile, initial_profile), extraction_facts
            warnings.append(f"{source_name} 的 LLM 简历抽取失败，已使用本地规则结果。")
        return initial_profile, initial_result.facts


def _merge_candidate_profile(profile: CandidateProfile, fallback: CandidateProfile) -> CandidateProfile:
    if profile.name in {"候选人", "未知候选人", "简历候选人"} and fallback.name:
        profile.name = fallback.name
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
