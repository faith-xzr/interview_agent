from app.fallback_ai import extract_candidate_profile, extract_jd_profile
from app.followups import generate_followups
from app.question_generation import generate_interview_questions
from app.scoring import score_candidate
from app.schemas import CandidateProfile, ExtractedFact, JDProfile


class QueueLLM:
    available = True

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def complete_json(self, system_prompt: str, user_prompt: str, **kwargs):
        self.calls.append((system_prompt, user_prompt, kwargs))
        return self.payloads.pop(0)


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


def test_score_candidate_returns_scores_and_reasons_without_decision_threshold():
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
    assert strong_report.decision == ""
    assert strong_report.dimension_scores["核心技能与工具"] >= 24
    assert strong_report.match_reasons
    assert weak_report.total_score < 60
    assert weak_report.decision == ""
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

    assert len(questions) == 10
    assert all(q.question and q.focus and q.scoring_criteria for q in questions)
    assert all(set(q.model_dump().keys()) == {"question", "focus", "scoring_criteria"} for q in questions)
    assert 3 <= len(followups) <= 5
    assert all(item.question for item in followups)


def test_llm_question_generation_uses_jd_resume_and_returns_lightweight_questions():
    llm = QueueLLM(
        [
            {
                "questions": [
                    {
                        "question": "请复盘你在低延迟推荐项目中负责的召回链路，核心瓶颈是怎么定位的？",
                        "focus": "简历项目中的推荐系统工程能力",
                        "scoring_criteria": "优秀回答应包含个人职责、召回链路、性能指标、排查路径和量化结果。",
                        "category": "technical_business",
                        "basis": "resume",
                    },
                    {
                        "question": "简历提到 Kafka 和 Flink，请说明你如何设计实时特征处理的数据流？",
                        "focus": "实时数据处理能力",
                        "scoring_criteria": "优秀回答应说明数据源、状态管理、延迟控制、容错和监控。",
                        "category": "technical_business",
                        "basis": "resume",
                    },
                    {
                        "question": "你在推荐排序优化中如何选择评价指标，并判断模型改动值得上线？",
                        "focus": "业务指标与上线判断",
                        "scoring_criteria": "优秀回答应覆盖离线指标、线上实验、风险、回滚和业务收益。",
                        "category": "technical_business",
                        "basis": "resume",
                    },
                    {
                        "question": "请说明你在项目里如何和产品或运营确认推荐效果是否符合业务目标？",
                        "focus": "技术与业务目标对齐",
                        "scoring_criteria": "优秀回答应体现目标拆解、数据口径、沟通机制和取舍判断。",
                        "category": "technical_business",
                        "basis": "resume",
                    },
                    {
                        "question": "简历中的高并发经验如果迁移到本岗位，你会优先复用哪些设计？",
                        "focus": "经验迁移能力",
                        "scoring_criteria": "优秀回答应结合 JD 职责说明可复用设计、限制条件和验证方式。",
                        "category": "technical_business",
                        "basis": "resume",
                    },
                    {
                        "question": "你如何证明自己在低延迟推荐项目中的贡献不是只参与而是关键负责人？",
                        "focus": "项目真实性和个人贡献",
                        "scoring_criteria": "优秀回答应给出负责模块、决策点、协作边界和结果证据。",
                        "category": "technical_business",
                        "basis": "resume",
                    },
                    {
                        "question": "JD 要求 FastAPI 平台建设，你会如何设计一个可观测的服务接口？",
                        "focus": "JD 核心职责的方案设计",
                        "scoring_criteria": "优秀回答应包含接口边界、错误处理、日志、指标、压测和告警。",
                        "category": "technical_business",
                        "basis": "jd",
                    },
                    {
                        "question": "如果推荐链路上线后出现核心指标下降，你会如何止损和复盘？",
                        "focus": "线上问题处理",
                        "scoring_criteria": "优秀回答应说明止损动作、根因定位、数据验证和长期改进。",
                        "category": "technical_business",
                        "basis": "jd",
                    },
                    {
                        "question": "当产品想快速上线但你认为风险较高时，你会如何推进决策？",
                        "focus": "业务沟通与风险判断",
                        "scoring_criteria": "优秀回答应体现风险量化、方案对比、里程碑和共同决策。",
                        "category": "technical_business",
                        "basis": "jd",
                    },
                    {
                        "question": "你为什么考虑这个岗位，最希望在下一份工作里获得什么成长？",
                        "focus": "求职动机与稳定性",
                        "scoring_criteria": "优秀回答应真实说明动机、岗位匹配点、成长目标和长期稳定性。",
                        "category": "hr",
                        "basis": "general",
                    },
                ]
            }
        ]
    )
    jd = JDProfile(
        job_title="高级推荐系统后端工程师",
        responsibilities=["负责 FastAPI 推荐平台建设", "优化推荐链路稳定性"],
        required_skills=["Python", "FastAPI", "Kafka", "Flink"],
        seniority="高级",
    )
    candidate = CandidateProfile(
        name="小周",
        projects=["低延迟推荐项目：负责召回链路优化，使用 Kafka、Flink 和 Python。"],
        skills=["Python", "Kafka", "Flink"],
        highlights=["推荐链路延迟降低 30%"],
    )
    facts = [
        ExtractedFact(
            fact_type="project",
            value="低延迟推荐项目",
            evidence="低延迟推荐项目：负责召回链路优化，使用 Kafka、Flink 和 Python。",
            section="projects",
        )
    ]
    match = score_candidate(jd, candidate, ["低延迟推荐项目 Kafka Flink"])

    questions = generate_interview_questions(
        jd,
        candidate,
        match,
        llm=llm,
        resume_text="小周\n低延迟推荐项目：负责召回链路优化，使用 Kafka、Flink 和 Python。",
        extraction_facts=facts,
    )

    assert len(questions) == 10
    assert all(set(q.model_dump().keys()) == {"question", "focus", "scoring_criteria"} for q in questions)
    assert "待匹配岗位名称" in llm.calls[0][1]
    assert "高级推荐系统后端工程师" in llm.calls[0][1]
    assert "低延迟推荐项目" in llm.calls[0][1]
    assert "Kafka" in llm.calls[0][1]
    assert "{{" not in llm.calls[0][1]


def test_llm_question_generation_records_llm_source_and_timeout():
    llm = QueueLLM(
        [
            {
                "questions": [
                    {
                        "question": f"模型生成面试题 {index + 1}",
                        "focus": f"模型生成考察点 {index + 1}",
                        "scoring_criteria": f"模型生成评分标准 {index + 1}",
                        "category": "hr" if index == 9 else "technical_business",
                        "basis": "resume" if index < 6 else ("general" if index == 9 else "jd"),
                    }
                    for index in range(10)
                ]
            }
        ]
    )
    jd = JDProfile(job_title="AI Agent 工程师", required_skills=["Python"])
    candidate = CandidateProfile(name="小周", skills=["Python"], projects=["RAG 项目"])
    match = score_candidate(jd, candidate, ["RAG 项目 Python"])
    diagnostics = {}

    questions = generate_interview_questions(jd, candidate, match, llm=llm, diagnostics=diagnostics)

    assert len(questions) == 10
    assert llm.calls[0][2]["timeout"] == 90
    assert diagnostics["question_generation_source"] == "llm"
    assert diagnostics["llm_timeout_seconds"] == 90
    assert "fallback_reason" not in diagnostics


def test_llm_question_generation_records_rule_fallback_reason():
    llm = QueueLLM([None])
    jd = JDProfile(job_title="AI Agent 工程师", required_skills=["Python"])
    candidate = CandidateProfile(name="小周", skills=["Python"], projects=["RAG 项目"])
    match = score_candidate(jd, candidate, ["RAG 项目 Python"])
    diagnostics = {}

    questions = generate_interview_questions(jd, candidate, match, llm=llm, diagnostics=diagnostics)

    assert len(questions) == 10
    assert llm.calls[0][2]["timeout"] == 90
    assert diagnostics["question_generation_source"] == "rule_fallback"
    assert diagnostics["fallback_reason"] == "llm_returned_none"
    assert questions[0].question == "请结合你最近的项目，说明你如何使用 Python 解决一个真实业务问题？"


def test_rule_followup_generation_uses_job_title_as_context():
    jd = JDProfile(
        job_title="高级推荐系统后端工程师",
        responsibilities=["负责推荐平台建设"],
        required_skills=["Kafka", "Flink"],
    )
    candidate = CandidateProfile(name="小周")
    match = score_candidate(jd, candidate, [])

    followups = generate_followups(candidate, match, jd=jd)

    assert any("高级推荐系统后端工程师" in item.question for item in followups)
