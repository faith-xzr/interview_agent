from app.schemas import CandidateProfile, ExtractedFact, JDProfile
from app.scoring.llm_scorer import generate_scoring_rubric, score_candidate_with_llm
from app.scoring.score_engine import compute_contribution


class QueueLLM:
    available = True

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def complete_json(self, system_prompt: str, user_prompt: str):
        self.calls.append((system_prompt, user_prompt))
        return self.payloads.pop(0)


def test_generate_scoring_rubric_uses_jd_facts_and_normalizes_to_100():
    llm = QueueLLM(
        [
            {
                "rubric": [
                    {
                        "dimension": "AIGC工具生态",
                        "requirement": "熟练运用 ChatGPT",
                        "requirement_type": "core_tool",
                        "max_score": 30,
                        "priority": "must_have",
                        "scoring_note": "岗位明确要求熟练使用 ChatGPT",
                    },
                    {
                        "dimension": "AIGC工具生态",
                        "requirement": "能直接使用 Midjourney 产出视觉素材",
                        "requirement_type": "core_tool",
                        "max_score": 30,
                        "priority": "must_have",
                        "scoring_note": "岗位强调 Midjourney 是核心工具",
                    },
                    {
                        "dimension": "内容生产方法",
                        "requirement": "能沉淀 AI 内容 SOP",
                        "requirement_type": "responsibility",
                        "max_score": 20,
                        "priority": "must_have",
                        "scoring_note": "岗位要求形成可复用流程",
                    },
                ]
            }
        ]
    )
    jd = JDProfile(job_title="AIGC 内容运营")
    jd_facts = [
        ExtractedFact(
            fact_type="必备技能",
            value="熟练运用 ChatGPT",
            evidence="熟练运用 ChatGPT",
            section="jd",
            confidence=0.92,
            extractor="llm_end_to_end",
        ),
        ExtractedFact(
            fact_type="必备技能",
            value="能直接使用 Midjourney 产出视觉素材",
            evidence="Midjourney",
            section="jd",
            confidence=0.92,
            extractor="llm_end_to_end",
        ),
        ExtractedFact(
            fact_type="核心职责",
            value="能沉淀 AI 内容 SOP",
            evidence="沉淀 AI 内容 SOP",
            section="jd",
            confidence=0.82,
            extractor="llm_end_to_end",
        ),
    ]

    rubric = generate_scoring_rubric(llm, jd, jd_facts)

    assert rubric is not None
    assert [item.requirement for item in rubric.items] == [
        "熟练运用 ChatGPT",
        "能直接使用 Midjourney 产出视觉素材",
        "能沉淀 AI 内容 SOP",
    ]
    assert sum(item.max_score for item in rubric.items) == 100
    assert rubric.items[0].dimension == "AIGC工具生态"
    assert "待匹配岗位名称" in llm.calls[0][1]
    assert "AIGC 内容运营" in llm.calls[0][1]
    assert "{{JD_FACTS_JSON}}" not in llm.calls[0][1]


def test_scoring_prompts_borrow_resume_audit_standards():
    llm = QueueLLM(
        [
            {
                "rubric": [
                    {
                        "dimension": "项目深度",
                        "requirement": "有 RAG 系统落地经验",
                        "requirement_type": "project_depth",
                        "max_score": 100,
                        "priority": "must_have",
                        "scoring_note": "岗位强调真实项目落地",
                    }
                ]
            },
            {
                "matches": [
                    {
                        "requirement": "有 RAG 系统落地经验",
                        "status": "强匹配",
                        "confidence": 0.9,
                        "reason": "简历有 RAG 系统项目证据",
                        "evidence_indexes": [0],
                    }
                ]
            },
        ]
    )
    jd = JDProfile(job_title="AI Agent 工程师")
    jd_facts = [
        ExtractedFact(
            fact_type="核心职责",
            value="有 RAG 系统落地经验",
            evidence="负责 RAG 系统落地",
            section="jd",
        )
    ]
    candidate = CandidateProfile(name="小林", projects=["RAG 系统：负责检索链路和评测。"])
    candidate_facts = [
        ExtractedFact(
            fact_type="project",
            value="RAG 系统",
            evidence="RAG 系统：负责检索链路和评测。",
            section="projects",
        )
    ]

    report = score_candidate_with_llm(llm, jd, candidate, [], jd_facts, candidate_facts)

    assert report is not None
    rubric_prompt = llm.calls[0][1]
    matching_prompt = llm.calls[1][1]
    assert "项目技术深度" in rubric_prompt
    assert "技能匹配度" in rubric_prompt
    assert "技术实现 + 业务场景 + 结果量化" in rubric_prompt
    assert "个人职责边界" in matching_prompt
    assert "业务价值或量化结果" in matching_prompt
    assert "只写熟悉/参与/负责但没有具体项目证据" in matching_prompt


def test_score_candidate_with_llm_matches_all_dynamic_requirements():
    llm = QueueLLM(
        [
            {
                "rubric": [
                    {
                        "dimension": "AIGC工具生态",
                        "requirement": "熟练运用 ChatGPT",
                        "requirement_type": "core_skill",
                        "max_score": 20,
                        "priority": "must_have",
                        "scoring_note": "核心工具要求",
                    },
                    {
                        "dimension": "AIGC工具生态",
                        "requirement": "能直接使用 Midjourney 产出视觉素材",
                        "requirement_type": "core_skill",
                        "max_score": 20,
                        "priority": "must_have",
                        "scoring_note": "核心工具要求",
                    },
                    {
                        "dimension": "AIGC工具生态",
                        "requirement": "能使用 Runway 等 AI 工具辅助文案",
                        "requirement_type": "core_skill",
                        "max_score": 15,
                        "priority": "must_have",
                        "scoring_note": "核心工具要求",
                    },
                    {
                        "dimension": "内容生产方法",
                        "requirement": "能沉淀 AI 内容 SOP",
                        "requirement_type": "responsibility",
                        "max_score": 25,
                        "priority": "must_have",
                        "scoring_note": "方法论要求",
                    },
                    {
                        "dimension": "平台与案例",
                        "requirement": "有成功自媒体案例或 KOL 经历",
                        "requirement_type": "project_depth",
                        "max_score": 20,
                        "priority": "nice_to_have",
                        "scoring_note": "案例证明要求",
                    },
                ]
            },
            {
                "matches": [
                    {
                        "requirement": "熟练运用 ChatGPT",
                        "status": "未匹配",
                        "confidence": 0,
                        "reason": "简历未明确覆盖 ChatGPT 使用经验",
                        "evidence_indexes": [],
                    },
                    {
                        "requirement": "能直接使用 Midjourney 产出视觉素材",
                        "status": "强匹配",
                        "confidence": 0.95,
                        "reason": "项目经历直接说明使用 Midjourney 产出视觉素材",
                        "evidence_indexes": [0],
                    },
                    {
                        "requirement": "能使用 Runway 等 AI 工具辅助文案",
                        "status": "相关匹配",
                        "confidence": 0.8,
                        "reason": "简历展示 Runway 辅助短视频脚本经验",
                        "evidence_indexes": [1],
                    },
                    {
                        "requirement": "能沉淀 AI 内容 SOP",
                        "status": "未匹配",
                        "confidence": 0,
                        "reason": "简历未出现 SOP 沉淀证据",
                        "evidence_indexes": [],
                    },
                    {
                        "requirement": "有成功自媒体案例或 KOL 经历",
                        "status": "直接匹配",
                        "confidence": 0.9,
                        "reason": "简历有 KOL 合作案例证据",
                        "evidence_indexes": [2],
                    },
                ]
            },
        ]
    )
    jd = JDProfile(job_title="AIGC 内容运营")
    jd_facts = [
        ExtractedFact(fact_type="必备技能", value="熟练运用 ChatGPT", evidence="熟练运用 ChatGPT", section="jd"),
        ExtractedFact(
            fact_type="必备技能",
            value="能直接使用 Midjourney 产出视觉素材",
            evidence="Midjourney",
            section="jd",
        ),
        ExtractedFact(
            fact_type="必备技能",
            value="能使用 Runway 等 AI 工具辅助文案",
            evidence="Runway等AI工具辅助文案",
            section="jd",
        ),
        ExtractedFact(fact_type="核心职责", value="能沉淀 AI 内容 SOP", evidence="沉淀AI内容SOP", section="jd"),
        ExtractedFact(
            fact_type="加分项",
            value="有成功自媒体案例或 KOL 经历",
            evidence="有成功自媒体案例或KOL经历",
            section="jd",
        ),
    ]
    candidate = CandidateProfile(
        name="小林",
        projects=["使用 Midjourney 产出视觉素材", "用 Runway 辅助短视频脚本", "参与 KOL 合作案例复盘"],
        skills=["Midjourney", "Runway"],
    )
    candidate_facts = [
        ExtractedFact(
            fact_type="project",
            value="使用 Midjourney 产出视觉素材",
            evidence="使用 Midjourney 产出视觉素材",
            section="projects",
            line_start=8,
        ),
        ExtractedFact(
            fact_type="project",
            value="用 Runway 辅助短视频脚本",
            evidence="用 Runway 辅助短视频脚本",
            section="projects",
            line_start=9,
        ),
        ExtractedFact(
            fact_type="project",
            value="参与 KOL 合作案例复盘",
            evidence="参与 KOL 合作案例复盘",
            section="projects",
            line_start=10,
        ),
    ]

    report = score_candidate_with_llm(llm, jd, candidate, ["Midjourney Runway KOL"], jd_facts, candidate_facts)

    assert report is not None
    assert "待匹配岗位名称" in llm.calls[1][1]
    assert "AIGC 内容运营" in llm.calls[1][1]
    assert "contribution" not in llm.calls[1][1]
    assert report.total_score == 42
    assert [item.requirement for item in report.requirement_matches] == [
        "熟练运用 ChatGPT",
        "能直接使用 Midjourney 产出视觉素材",
        "能使用 Runway 等 AI 工具辅助文案",
        "能沉淀 AI 内容 SOP",
        "有成功自媒体案例或 KOL 经历",
    ]
    assert report.dimension_scores["AIGC工具生态"] == 26
    assert report.dimension_scores["内容生产方法"] == 0
    assert report.dimension_scores["平台与案例"] == 16
    midjourney_match = report.requirement_matches[1]
    assert midjourney_match.max_score == 20
    assert midjourney_match.contribution == 19
    assert midjourney_match.evidence[0].text == "使用 Midjourney 产出视觉素材"
    assert report.gap_reasons[0] == "AIGC工具生态待确认：熟练运用 ChatGPT（简历未明确覆盖 ChatGPT 使用经验）"


def test_score_candidate_with_llm_caps_score_when_hard_requirement_missing():
    llm = QueueLLM(
        [
            {
                "rubric": [
                    {
                        "dimension": "核心技能",
                        "requirement": "熟练掌握 Python",
                        "requirement_type": "core_skill",
                        "max_score": 50,
                        "priority": "must_have",
                    },
                    {
                        "dimension": "项目深度",
                        "requirement": "有 RAG 项目落地经验",
                        "requirement_type": "project_depth",
                        "max_score": 30,
                        "priority": "must_have",
                    },
                    {
                        "dimension": "硬性门槛",
                        "requirement": "本科及以上学历",
                        "requirement_type": "hard_requirement",
                        "max_score": 20,
                        "priority": "hard_gate",
                    },
                ]
            },
            {
                "matches": [
                    {
                        "requirement": "熟练掌握 Python",
                        "status": "强匹配",
                        "confidence": 0.95,
                        "reason": "技能和项目均明确 Python",
                        "evidence_indexes": [0],
                    },
                    {
                        "requirement": "有 RAG 项目落地经验",
                        "status": "强匹配",
                        "confidence": 0.9,
                        "reason": "项目经历直接说明 RAG 落地",
                        "evidence_indexes": [1],
                    },
                    {
                        "requirement": "本科及以上学历",
                        "status": "未匹配",
                        "confidence": 0,
                        "reason": "简历未提供学历信息",
                        "evidence_indexes": [],
                    },
                ]
            },
        ]
    )
    jd = JDProfile(job_title="AI Agent 工程师", hard_requirements=["本科及以上学历"])
    jd_facts = [
        ExtractedFact(fact_type="必备技能", value="熟练掌握 Python", evidence="Python", section="jd"),
        ExtractedFact(fact_type="核心职责", value="有 RAG 项目落地经验", evidence="RAG 项目", section="jd"),
        ExtractedFact(fact_type="硬性门槛", value="本科及以上学历", evidence="本科及以上", section="jd"),
    ]
    candidate = CandidateProfile(name="小林", projects=["RAG 项目落地"], skills=["Python"])
    candidate_facts = [
        ExtractedFact(fact_type="skill", value="Python", evidence="Python", section="skills"),
        ExtractedFact(fact_type="project", value="RAG 项目落地", evidence="RAG 项目落地", section="projects"),
    ]

    report = score_candidate_with_llm(llm, jd, candidate, [], jd_facts, candidate_facts)

    assert report is not None
    assert report.total_score == 69
    assert report.score_breakdown.risk_deduction == 5
    assert any("本科及以上学历" in reason for reason in report.gap_reasons)


def test_score_candidate_with_llm_rejects_invalid_payload():
    llm = QueueLLM(
        [
            {
                "rubric": [
                    {
                        "dimension": "AIGC工具生态",
                        "requirement": "熟练运用 ChatGPT",
                        "requirement_type": "core_skill",
                        "max_score": 100,
                        "priority": "must_have",
                    }
                ]
            },
            {"matches": []},
        ]
    )
    jd = JDProfile(job_title="AIGC 内容运营")
    jd_facts = [
        ExtractedFact(fact_type="必备技能", value="熟练运用 ChatGPT", evidence="熟练运用 ChatGPT", section="jd")
    ]
    candidate = CandidateProfile(name="小林")

    report = score_candidate_with_llm(llm, jd, candidate, [], jd_facts, [])

    assert report is None


def test_compute_contribution_uses_backend_policy_not_model_score():
    assert compute_contribution(20, "强匹配", 0.95) == 19
    assert compute_contribution(15, "相关匹配", 0.8) == 6.6
    assert compute_contribution(20, "直接匹配", 0.9) == 16.2
    assert compute_contribution(25, "未匹配", 1) == 0


def test_score_candidate_with_llm_rejects_positive_match_without_evidence():
    llm = QueueLLM(
        [
            {
                "rubric": [
                    {
                        "dimension": "项目深度",
                        "requirement": "有 RAG / Agent 系统落地经验",
                        "requirement_type": "project_depth",
                        "max_score": 100,
                        "priority": "must_have",
                    }
                ]
            },
            {
                "matches": [
                    {
                        "requirement": "有 RAG / Agent 系统落地经验",
                        "status": "强匹配",
                        "confidence": 0.9,
                        "reason": "模型声称强匹配，但没有引用证据",
                        "evidence_indexes": [],
                    }
                ]
            },
        ]
    )
    jd = JDProfile(job_title="Agent 工程师")
    jd_facts = [
        ExtractedFact(
            fact_type="核心职责",
            value="有 RAG / Agent 系统落地经验",
            evidence="有 RAG / Agent 系统落地经验",
            section="jd",
        )
    ]
    candidate = CandidateProfile(name="小林", projects=["RAG 项目"])

    report = score_candidate_with_llm(llm, jd, candidate, [], jd_facts, [])

    assert report is None
