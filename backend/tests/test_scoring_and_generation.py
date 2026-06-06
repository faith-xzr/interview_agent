from app.fallback_ai import extract_candidate_profile, extract_jd_profile
from app.question_generator import generate_followups, generate_interview_questions
from app.scoring import score_candidate
from app.schemas import CandidateProfile, ExtractedFact, JDProfile


def test_schema_accepts_complete_profiles():
    jd = JDProfile(
        job_title="高级 Python 后端工程师",
        responsibilities=["负责 RAG 平台和 API 服务建设"],
        required_skills=["Python", "FastAPI", "SQL"],
        nice_to_have_skills=["React"],
        seniority="高级",
        years_required=5,
        industry_background=["AI"],
        hard_requirements=["本科及以上"],
    )
    candidate = CandidateProfile(
        name="王五",
        contacts={"phone": "13812345678", "email": "wangwu@example.com"},
        education=["浙江大学 本科"],
        work_experiences=["7年 Python 后端经验"],
        projects=["RAG 知识库检索平台，使用 FastAPI 和 SQL"],
        skills=["Python", "FastAPI", "SQL", "React"],
        certifications=[],
        highlights=["主导过向量检索平台"],
        risk_points=[],
        ambiguous_points=["项目规模未说明"],
    )

    assert jd.job_title == "高级 Python 后端工程师"
    assert candidate.contacts["email"] == "wangwu@example.com"


def test_schema_normalizes_common_llm_jd_payload_variants():
    jd = JDProfile.model_validate(
        {
            "job_title": "高级 Python 后端工程师",
            "responsibilities": "负责招聘系统后端服务和简历解析流水线。",
            "required_skills": "Python、FastAPI、SQL、向量检索",
            "nice_to_have_skills": None,
            "seniority": "高级",
            "years_required": "5 年以上",
            "industry_background": None,
            "hard_requirements": None,
        }
    )

    assert jd.responsibilities == ["负责招聘系统后端服务和简历解析流水线。"]
    assert jd.required_skills == ["Python", "FastAPI", "SQL", "向量检索"]
    assert jd.years_required == 5
    assert jd.nice_to_have_skills == []
    assert jd.industry_background == []


def test_schema_normalizes_common_llm_resume_payload_variants():
    candidate = CandidateProfile.model_validate(
        {
            "name": None,
            "target_role": "高级 Python 后端工程师",
            "contacts": {"phone": "13800000000", "email": "zhangsan@example.com"},
            "location": "上海",
            "education": [{"school": "复旦大学", "major": "软件工程", "degree": "本科"}],
            "work_experiences": [{"company": "星河智能", "title": "后端负责人"}],
            "projects": [{"name": "AI 招聘筛选平台", "result": "覆盖 10+ 个岗位试点"}],
            "skills": "Python、FastAPI、SQL",
            "certifications": None,
            "highlights": [],
            "risk_points": None,
            "ambiguous_points": None,
        }
    )

    assert candidate.name == "未知候选人"
    assert candidate.education == ["复旦大学 软件工程 本科"]
    assert candidate.work_experiences == ["星河智能 后端负责人"]
    assert candidate.projects == ["AI 招聘筛选平台 覆盖 10+ 个岗位试点"]
    assert candidate.skills == ["Python", "FastAPI", "SQL"]
    assert candidate.certifications == []


def test_score_candidate_uses_thresholds_and_reasons():
    jd = JDProfile(
        job_title="高级 Python 后端工程师",
        responsibilities=["负责 RAG 平台和 API 服务建设"],
        required_skills=["Python", "FastAPI", "SQL"],
        nice_to_have_skills=["React"],
        seniority="高级",
        years_required=5,
        industry_background=["AI"],
        hard_requirements=[],
    )
    strong = CandidateProfile(
        name="王五",
        contacts={},
        education=["本科"],
        work_experiences=["7年 Python 后端开发经验"],
        projects=["负责 RAG 平台，使用 Python、FastAPI、SQL 和 React"],
        skills=["Python", "FastAPI", "SQL", "React"],
        certifications=[],
        highlights=[],
        risk_points=[],
        ambiguous_points=[],
    )
    weak = CandidateProfile(
        name="赵六",
        contacts={},
        education=[],
        work_experiences=["2年客服经验"],
        projects=["客户满意度运营项目"],
        skills=["Excel"],
        certifications=[],
        highlights=[],
        risk_points=[],
        ambiguous_points=[],
    )

    strong_report = score_candidate(jd, strong, ["Python FastAPI SQL RAG"])
    weak_report = score_candidate(jd, weak, ["客服 Excel"])

    assert strong_report.total_score >= 75
    assert strong_report.decision == "推荐推进"
    assert strong_report.dimension_scores["核心技能与工具"] >= 24
    assert strong_report.match_reasons
    assert weak_report.total_score < 60
    assert weak_report.decision == "暂不推进"
    assert weak_report.gap_reasons


def test_score_candidate_returns_requirement_level_explanations():
    jd = JDProfile(
        job_title="高级 Python 后端工程师",
        responsibilities=["负责 RAG 平台和 API 服务建设"],
        required_skills=["Python", "FastAPI", "SQL"],
        nice_to_have_skills=["React"],
        seniority="高级",
        years_required=5,
        industry_background=["AI"],
        hard_requirements=["本科及以上"],
    )
    candidate = CandidateProfile(
        name="王五",
        contacts={},
        education=["浙江大学 本科"],
        work_experiences=["7年 Python 后端经验"],
        projects=["负责 RAG 平台，使用 Python、FastAPI、SQL 和 React"],
        skills=["Python", "FastAPI", "SQL", "React"],
        certifications=[],
        highlights=["主导过向量检索平台"],
        risk_points=[],
        ambiguous_points=[],
    )
    facts = [
        ExtractedFact(
            fact_type="project",
            value="负责 RAG 平台，使用 Python、FastAPI、SQL 和 React",
            evidence="负责 RAG 平台，使用 Python、FastAPI、SQL 和 React",
            section="projects",
            line_start=8,
            confidence=0.9,
        ),
        ExtractedFact(
            fact_type="education",
            value="浙江大学 本科",
            evidence="浙江大学 本科",
            section="education",
            line_start=4,
            confidence=0.86,
        ),
    ]

    report = score_candidate(jd, candidate, ["Python FastAPI SQL RAG"], facts)

    python_match = next(item for item in report.requirement_matches if item.requirement == "Python")
    assert python_match.dimension == "核心技能与工具"
    assert python_match.status == "强匹配"
    assert python_match.contribution > 0
    assert python_match.evidence
    assert python_match.evidence[0].text == "负责 RAG 平台，使用 Python、FastAPI、SQL 和 React"
    assert python_match.evidence[0].section == "projects"
    assert python_match.evidence[0].line_start == 8
    assert any(item.dimension == "教育/证书/硬条件" for item in report.requirement_matches)
    assert report.dimension_explanations[0].max_score > 0


def test_question_and_followup_generation_has_required_counts():
    jd = extract_jd_profile(
        "高级 Python 后端工程师，5年以上经验。负责 FastAPI、RAG、SQL、React 相关平台建设。"
    )
    candidate = extract_candidate_profile(
        "王五\n电话 13812345678\n7年 Python 后端经验。项目：RAG 检索平台，使用 FastAPI 和 SQL。"
    )
    match = score_candidate(jd, candidate, ["RAG 检索平台 FastAPI SQL"])

    questions = generate_interview_questions(jd, candidate, match)
    followups = generate_followups(candidate, match)

    assert len(questions) >= 10
    assert all(q.focus and q.difficulty and q.scoring_criteria for q in questions)
    assert 3 <= len(followups) <= 5
    assert all(item.question for item in followups)
