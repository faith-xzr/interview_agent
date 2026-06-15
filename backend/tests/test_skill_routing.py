from pathlib import Path

from app.schemas import ExtractedFact, JDProfile
from app.skills.repository import SkillRepository
from app.skills.routing import route_skill_for_jd


class QueueLLM:
    available = True

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def complete_json(self, system_prompt: str, user_prompt: str, **kwargs):
        self.calls.append((system_prompt, user_prompt, kwargs))
        return self.payloads.pop(0)


def skill_repository() -> SkillRepository:
    return SkillRepository(Path(__file__).resolve().parents[1] / "skills")


def ai_business_jd() -> JDProfile:
    return JDProfile(
        job_title="AI 业务探索",
        responsibilities=[
            "挖掘业务痛点，判断哪些环节可由 AI 接管或增效",
            "快速搭建 AI Agent 或自动化脚本验证方案",
            "参与设计全新工作流 SOP",
        ],
        required_skills=["Prompt", "Agent", "业务流程重构"],
        nice_to_have_skills=["自动化工具", "电商/供应链/B 端业务认知"],
        seniority="未说明",
        years_required=0,
        industry_background=["B2B 平台"],
        hard_requirements=[],
    )


def ai_business_fact() -> ExtractedFact:
    return ExtractedFact(
        fact_type="responsibility",
        value="快速搭建 AI Agent 或自动化脚本验证方案",
        evidence="快速搭建 AI Agent 或自动化脚本，验证 AI 能干到什么程度。",
        section="jd",
        confidence=0.9,
        extractor="test",
    )


def ai_content_operations_jd() -> JDProfile:
    return JDProfile(
        job_title="新媒体运营（AI 方向）",
        responsibilities=[
            "负责小红书、抖音等平台的内容策划与分发。",
            "探索并沉淀 AI 内容 SOP 以提升生产效率。",
            "通过追踪平台算法与热点，利用数据驱动优化策略，打造爆款图文内容。",
        ],
        required_skills=["ChatGPT", "Midjourney", "Runway", "短视频平台生态"],
        nice_to_have_skills=["数字人", "自动化分发", "MCN 创业背景"],
        seniority="未说明",
        years_required=0,
        industry_background=["B2B", "供应链"],
        hard_requirements=[],
    )


def test_route_skill_for_jd_accepts_valid_llm_choice():
    llm = QueueLLM([
        {
            "skill_id": "ai-agent-dev",
            "confidence": 0.91,
            "reason": "JD 强调 AI Agent 原型、Prompt 和工作流落地。",
        }
    ])

    result = route_skill_for_jd(llm, ai_business_jd(), [ai_business_fact()], skill_repository())

    assert result.skill_id == "ai-agent-dev"
    assert result.skill_name == "AI Agent 开发"
    assert result.position_name == "AI 业务探索"
    assert result.confidence == 0.91
    assert result.source == "llm"
    assert "AI Agent 原型" in result.reason
    assert "ai-agent-dev" in llm.calls[0][1]


def test_route_skill_for_jd_falls_back_when_llm_choice_is_invalid():
    llm = QueueLLM([
        {
            "skill_id": "not-a-real-skill",
            "confidence": 0.99,
            "reason": "模型误返回了不存在的 skill。",
        }
    ])

    result = route_skill_for_jd(llm, ai_business_jd(), [ai_business_fact()], skill_repository())

    assert result.skill_id == "ai-agent-dev"
    assert result.skill_name == "AI Agent 开发"
    assert result.position_name == "AI 业务探索"
    assert result.source == "keyword"
    assert result.confidence < 0.91
    assert "模型返回的 skill_id 无效" in result.reason


def test_route_skill_for_jd_falls_back_when_llm_confidence_is_low():
    llm = QueueLLM([
        {
            "skill_id": "frontend",
            "confidence": 0.31,
            "reason": "缺少前端证据。",
        }
    ])

    result = route_skill_for_jd(llm, ai_business_jd(), [ai_business_fact()], skill_repository())

    assert result.skill_id == "ai-agent-dev"
    assert result.source == "keyword"
    assert "置信度低于阈值" in result.reason


def test_route_skill_for_jd_uses_custom_jd_for_ai_content_operations_keyword_fallback():
    llm = QueueLLM([
        "not-json",
    ])

    result = route_skill_for_jd(llm, ai_content_operations_jd(), [], skill_repository())

    assert result.skill_id == "custom-jd"
    assert result.skill_name == "自定义 JD"
    assert result.position_name == "新媒体运营（AI 方向）"
    assert result.source == "keyword"
    assert "算法与数据结构" not in result.route_result


def test_route_skill_for_jd_rejects_algorithm_llm_choice_for_content_operations():
    llm = QueueLLM([
        {
            "skill_id": "algorithm",
            "confidence": 0.92,
            "reason": "JD 提到平台算法和图文内容。",
        }
    ])

    result = route_skill_for_jd(llm, ai_content_operations_jd(), [], skill_repository())

    assert result.skill_id == "custom-jd"
    assert result.source == "keyword"
    assert "缺少算法与数据结构岗位强信号" in result.reason


def test_route_skill_for_jd_rejects_ai_agent_llm_choice_for_content_operations():
    llm = QueueLLM([
        {
            "skill_id": "ai-agent-dev",
            "confidence": 0.92,
            "reason": "JD 提到 AI 内容 SOP 和自动化分发。",
        }
    ])

    result = route_skill_for_jd(llm, ai_content_operations_jd(), [], skill_repository())

    assert result.skill_id == "custom-jd"
    assert result.source == "keyword"
    assert "缺少 AI Agent 开发岗位强信号" in result.reason
