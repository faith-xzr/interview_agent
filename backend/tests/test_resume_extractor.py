from pathlib import Path

from app.extraction.document_parser import extract_text_from_bytes
from app.extraction.resume_extractor import extract_resume_profile


SAMPLE_RESUME = (
    Path(__file__).resolve().parents[2]
    / "samples"
    / "resumes"
    / "小陈_深度实战版_vFinal.docx"
)


def test_section_aware_extractor_preserves_sample_resume_structure():
    text = extract_text_from_bytes(SAMPLE_RESUME.name, SAMPLE_RESUME.read_bytes())

    result = extract_resume_profile(text, SAMPLE_RESUME.name)

    assert result.profile.name == "小陈"
    assert result.profile.target_role == "高级翻译（AI 辅助）"
    assert "Prompt Engineering" in result.profile.skills
    assert "AI 译后编辑 (MTPE)" in result.profile.skills
    assert any("AI 独角兽企业 | 提示词工程师" in item for item in result.profile.work_experiences)
    assert any("某外国语大学" in item and "硕士" in item for item in result.profile.education)


def test_section_aware_extractor_emits_evidence_backed_facts():
    text = extract_text_from_bytes(SAMPLE_RESUME.name, SAMPLE_RESUME.read_bytes())

    result = extract_resume_profile(text, SAMPLE_RESUME.name)

    assert any(
        fact.fact_type == "metric"
        and fact.value == "25%"
        and fact.section == "experience"
        and fact.line_start == 19
        and "Prompt 调优" in fact.evidence
        for fact in result.facts
    )
    assert any(
        fact.fact_type == "skill"
        and fact.value == "Trados/MemoQ"
        and fact.section == "skills"
        and fact.line_start == 26
        for fact in result.facts
    )
    assert any("起止时间" in item for item in result.profile.ambiguous_points)
