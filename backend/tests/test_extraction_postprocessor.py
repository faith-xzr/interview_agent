from app.extraction.postprocessor import postprocess_extraction
from app.schemas import CandidateProfile, ExtractedFact


class FakeLLM:
    available = True

    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, system_prompt: str, user_prompt: str):
        return self.payload


class CapturingLLM:
    available = True

    def __init__(self):
        self.user_prompt = ""

    def complete_json(self, system_prompt: str, user_prompt: str):
        self.user_prompt = user_prompt
        return {"profile": {}, "facts": []}


def test_postprocessor_prompt_omits_candidate_pii_from_profile_and_facts():
    llm = CapturingLLM()
    profile = CandidateProfile(name="小周", contacts={"phone": "13812345678"})
    facts = [
        ExtractedFact(
            fact_type="contact",
            value="13812345678",
            evidence="电话：13812345678",
            section="basic",
            confidence=0.9,
            extractor="section_rules",
        )
    ]

    postprocess_extraction(
        llm=llm,
        text="候选人A\n电话：[PHONE_1]",
        profile=profile,
        facts=facts,
        warnings=[],
        label="小周",
    )

    assert "小周" not in llm.user_prompt
    assert "13812345678" not in llm.user_prompt


def test_postprocessor_accepts_supported_fact_reclassification():
    text = "【项目经验】\n• 企业级智能助手项目：负责 RAG 召回评估和上线验收。"
    profile = CandidateProfile(name="小周")
    facts = [
        ExtractedFact(
            fact_type="summary",
            value="企业级智能助手项目",
            evidence="• 企业级智能助手项目：负责 RAG 召回评估和上线验收。",
            section="summary",
            line_start=2,
            line_end=2,
            confidence=0.6,
            extractor="section_rules",
        )
    ]
    llm = FakeLLM(
        {
            "profile": {
                "name": "小周",
                "projects": ["企业级智能助手项目：负责 RAG 召回评估和上线验收。"],
            },
            "facts": [
                {
                    "fact_type": "project",
                    "value": "企业级智能助手项目",
                    "evidence": "• 企业级智能助手项目：负责 RAG 召回评估和上线验收。",
                    "section": "projects",
                    "line_start": 2,
                    "line_end": 2,
                    "confidence": 0.86,
                    "extractor": "llm_postprocess",
                }
            ],
        }
    )
    warnings = []

    result_profile, result_facts = postprocess_extraction(
        llm=llm,
        text=text,
        profile=profile,
        facts=facts,
        warnings=warnings,
        label="小周",
    )

    assert warnings == []
    assert "企业级智能助手项目：负责 RAG 召回评估和上线验收。" in result_profile.projects
    assert any(fact.fact_type == "project" and fact.section == "projects" for fact in result_facts)
    assert any(fact.extractor == "llm_postprocess" for fact in result_facts)


def test_postprocessor_rejects_facts_without_source_evidence():
    text = "【专业技能】\nPython | SQL"
    profile = CandidateProfile(name="小周", skills=["Python", "SQL"])
    facts = [
        ExtractedFact(
            fact_type="skill",
            value="Python",
            evidence="Python | SQL",
            section="skills",
            line_start=2,
            line_end=2,
            confidence=0.9,
            extractor="section_rules",
        )
    ]
    llm = FakeLLM(
        {
            "profile": {"name": "小周", "skills": ["Python", "SQL", "Kubernetes"]},
            "facts": [
                {
                    "fact_type": "skill",
                    "value": "Kubernetes",
                    "evidence": "熟悉 Kubernetes 集群调优",
                    "section": "skills",
                    "confidence": 0.9,
                    "extractor": "llm_postprocess",
                }
            ],
        }
    )
    warnings = []

    result_profile, result_facts = postprocess_extraction(
        llm=llm,
        text=text,
        profile=profile,
        facts=facts,
        warnings=warnings,
        label="小周",
    )

    assert "Kubernetes" not in result_profile.skills
    assert not any(fact.value == "Kubernetes" for fact in result_facts)
    assert warnings == []


def test_postprocessor_falls_back_when_payload_is_invalid():
    text = "小周\n【专业技能】\nPython | SQL"
    profile = CandidateProfile(name="小周", skills=["Python", "SQL"])
    facts = [
        ExtractedFact(
            fact_type="skill",
            value="Python",
            evidence="Python | SQL",
            section="skills",
            line_start=3,
            line_end=3,
            confidence=0.9,
            extractor="section_rules",
        )
    ]
    warnings = []

    result_profile, result_facts = postprocess_extraction(
        llm=FakeLLM({"profile": {"name": []}, "facts": "not-a-list"}),
        text=text,
        profile=profile,
        facts=facts,
        warnings=warnings,
        label="小周",
    )

    assert result_profile == profile
    assert result_facts == facts
    assert warnings == ["小周 的 LLM 抽取后处理结果结构不合法，已使用本地规则结果。"]
