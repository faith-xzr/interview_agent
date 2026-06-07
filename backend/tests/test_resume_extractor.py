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


def test_section_split_supports_decorated_resume_headers():
    text = """
小周
求职意向：AI产品经理 / Agent 应用架构师
【个人评价】
• 精通 Agent 编排与 RAG 链路设计，曾主导多个企业级智能助手从0到1的落地。
【教育背景】
• 某重点理工类大学（985）| 计算机科学与技术 | 本科 | 2022.09-2026.06
【项目经验】
• 企业级智能助手项目：负责需求拆解、RAG 召回评估和上线验收。
【专业技能】
Python | SQL | RAG | Agent 编排
"""

    result = extract_resume_profile(text, "decorated.pdf")

    assert "summary" in result.sections
    assert "education" in result.sections
    assert "projects" in result.sections
    assert "skills" in result.sections
    assert any(fact.section == "summary" for fact in result.facts)
    assert any(fact.section == "education" and fact.fact_type == "education" for fact in result.facts)
    assert any(fact.section == "projects" and fact.fact_type == "project" for fact in result.facts)
    assert any(fact.section == "skills" and fact.value == "Agent 编排" for fact in result.facts)
