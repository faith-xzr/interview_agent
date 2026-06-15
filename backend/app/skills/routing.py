import json
from typing import Any, Iterable, Optional, Sequence

from app.llm_timeouts import LLM_JSON_TIMEOUT_SECONDS
from app.schemas import AgentSkill, ExtractedFact, JDProfile, SkillRouteResult
from app.skills.repository import SkillRepository

MIN_LLM_ROUTE_CONFIDENCE = 0.65
FLEXIBLE_SKILL_IDS = {"custom-jd"}
ALGORITHM_STRONG_SIGNALS = (
    "算法工程师",
    "算法与数据结构",
    "数据结构",
    "复杂度",
    "动态规划",
    "leetcode",
    "编程题",
    "代码题",
    "acm",
    "oj",
    "图论",
    "图算法",
    "二叉树",
    "哈希表",
    "优先队列",
)
AI_AGENT_STRONG_SIGNALS = (
    "ai agent",
    "agent",
    "智能体",
    "rag",
    "mcp",
    "tool calling",
    "function calling",
    "工具调用",
    "llm 应用",
    "llm应用",
    "大模型应用开发",
    "检索增强",
    "上下文工程",
    "多 agent",
    "多智能体",
    "agent loop",
    "prompt 工程",
    "提示词工程",
)
CONTENT_OPERATIONS_SIGNALS = (
    "运营",
    "内容",
    "新媒体",
    "小红书",
    "抖音",
    "短视频",
    "图文",
    "文案",
    "视频",
    "kol",
    "mcn",
    "营销",
    "社媒",
    "自媒体",
)

SYSTEM_PROMPT = """你是招聘面试系统的 JD 到面试 skill 路由器。
你只能从用户给出的候选 skill 中选择一个最适合的 skill_id。
优先选择能覆盖 JD 核心职责、必备能力和面试追问策略的 skill。
如果 JD 是 AI Agent、Prompt、RAG、LLM 应用、自动化工作流或 AI 原型落地方向，优先考虑 AI Agent 相关 skill。
只返回 JSON，不要输出解释文本。"""


def route_skill_for_jd(
    llm: Any,
    jd_profile: JDProfile,
    jd_facts: Sequence[ExtractedFact],
    repository: SkillRepository,
) -> SkillRouteResult:
    candidates = _route_candidates(repository)
    if not candidates:
        raise KeyError("No interview skills are configured.")

    fallback_reason_prefix = ""
    if getattr(llm, "available", False):
        raw = llm.complete_json(
            SYSTEM_PROMPT,
            _build_route_prompt(jd_profile, jd_facts, candidates),
            timeout=LLM_JSON_TIMEOUT_SECONDS,
        )
        llm_result, invalid_reason = _parse_llm_result(raw, candidates)
        if llm_result is not None:
            skill, confidence, reason = llm_result
            unsafe_reason = _unsafe_specific_route_reason(jd_profile, skill)
            if unsafe_reason:
                fallback_reason_prefix = unsafe_reason
            elif confidence >= MIN_LLM_ROUTE_CONFIDENCE:
                return _result(jd_profile, skill, confidence, reason, "llm")
            else:
                fallback_reason_prefix = f"模型路由置信度低于阈值（{confidence:.2f} < {MIN_LLM_ROUTE_CONFIDENCE:.2f}），"
        else:
            fallback_reason_prefix = f"{invalid_reason}，"
    else:
        fallback_reason_prefix = "模型路由不可用，"

    return _keyword_route(jd_profile, candidates, fallback_reason_prefix)


def _route_candidates(repository: SkillRepository) -> list[AgentSkill]:
    return repository.list_skills()


def _build_route_prompt(
    jd_profile: JDProfile,
    jd_facts: Sequence[ExtractedFact],
    candidates: Sequence[AgentSkill],
) -> str:
    facts = [
        {
            "type": fact.fact_type,
            "value": fact.value,
            "evidence": fact.evidence,
            "confidence": fact.confidence,
        }
        for fact in jd_facts[:20]
    ]
    skill_payload = [
        {
            "skill_id": skill.id,
            "skill_name": skill.name,
            "description": skill.description,
            "keywords": skill.keywords,
            "categories": [category.label for category in skill.categories],
            "question_focuses": skill.question_focuses,
        }
        for skill in candidates
    ]
    payload = {
        "jd_profile": jd_profile.model_dump(mode="json"),
        "jd_facts": facts,
        "candidate_skills": skill_payload,
        "output_schema": {
            "skill_id": "必须是 candidate_skills 中的一个 skill_id",
            "confidence": "0 到 1 的数字",
            "reason": "一句中文说明，说明为何该 JD 应路由到这个 skill",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _parse_llm_result(
    raw: Any,
    candidates: Sequence[AgentSkill],
) -> tuple[Optional[tuple[AgentSkill, float, str]], str]:
    if not isinstance(raw, dict):
        return None, "模型路由未返回有效 JSON"
    skill_id = str(raw.get("skill_id") or "").strip()
    skill_by_id = {skill.id: skill for skill in candidates}
    skill = skill_by_id.get(skill_id)
    if skill is None:
        return None, "模型返回的 skill_id 无效"
    confidence = _coerce_confidence(raw.get("confidence"))
    reason = str(raw.get("reason") or "").strip()
    if not reason:
        reason = f"模型判断 JD 与「{skill.name}」最匹配。"
    return (skill, confidence, reason), ""


def _keyword_route(
    jd_profile: JDProfile,
    candidates: Sequence[AgentSkill],
    reason_prefix: str = "",
) -> SkillRouteResult:
    haystack = _normalize_search_text(
        [
            jd_profile.job_title,
            jd_profile.seniority,
            *jd_profile.required_skills,
            *jd_profile.nice_to_have_skills,
            *jd_profile.responsibilities,
            *jd_profile.industry_background,
            *jd_profile.hard_requirements,
        ]
    )
    scored = []
    flexible_hits = []
    for skill in candidates:
        hits = _matched_keywords(haystack, skill.keywords)
        if skill.id in FLEXIBLE_SKILL_IDS:
            flexible_hits.extend(hits)
            continue
        if hits and _unsafe_specific_route_reason(jd_profile, skill):
            flexible_hits.extend(hits)
            continue
        if hits:
            scored.append((len(hits), skill.id, skill, hits))

    if scored:
        scored.sort(key=lambda item: (-item[0], item[1]))
        score, _, skill, hits = scored[0]
        confidence = min(0.86, 0.56 + score * 0.08)
        reason = f"{reason_prefix}使用本地关键词路由；命中关键词：{', '.join(hits[:6])}。"
        return _result(jd_profile, skill, confidence, reason, "keyword")

    flexible = (
        next((skill for skill in candidates if skill.id == "custom-jd"), None)
        or candidates[0]
    )
    if flexible_hits:
        unique_hits = list(dict.fromkeys(flexible_hits))
        confidence = min(0.78, 0.54 + len(unique_hits) * 0.06)
        reason = f"{reason_prefix}未命中特定技术方向，使用自建 JD 路由；命中通用关键词：{', '.join(unique_hits[:6])}。"
        return _result(jd_profile, flexible, confidence, reason, "keyword")

    reason = f"{reason_prefix}未命中特定方向关键词，回退到自建 JD 面试。"
    return _result(jd_profile, flexible, 0.42, reason, "fallback")


def _result(
    jd_profile: JDProfile,
    skill: AgentSkill,
    confidence: float,
    reason: str,
    source: str,
) -> SkillRouteResult:
    position_name = jd_profile.job_title or "未命名岗位"
    route_result = f"{position_name} / {skill.name}"
    return SkillRouteResult(
        position_name=position_name,
        skill_id=skill.id,
        skill_name=skill.name,
        route_result=route_result,
        confidence=round(max(0.0, min(1.0, confidence)), 2),
        reason=reason,
        source=source,
    )


def _normalize_search_text(parts: Iterable[str]) -> str:
    return " ".join(part for part in parts if part).lower()


def _matched_keywords(haystack: str, keywords: Iterable[str]) -> list[str]:
    hits: list[str] = []
    for keyword in keywords:
        normalized = keyword.strip().lower()
        if normalized and normalized in haystack:
            hits.append(keyword.strip())
    return hits


def _unsafe_specific_route_reason(jd_profile: JDProfile, skill: AgentSkill) -> str:
    haystack = _jd_route_haystack(jd_profile)
    if skill.id == "algorithm" and not _contains_any(haystack, ALGORITHM_STRONG_SIGNALS):
        return "模型选择算法与数据结构，但 JD 缺少算法与数据结构岗位强信号，"
    if (
        skill.id in {"ai-agent-dev", "ai-agent-engineer"}
        and _contains_any(haystack, CONTENT_OPERATIONS_SIGNALS)
        and not _contains_any(haystack, AI_AGENT_STRONG_SIGNALS)
    ):
        return "模型选择 AI Agent 开发，但 JD 缺少 AI Agent 开发岗位强信号，"
    return ""


def _jd_route_haystack(jd_profile: JDProfile) -> str:
    return _normalize_search_text(
        [
            jd_profile.job_title,
            jd_profile.seniority,
            *jd_profile.required_skills,
            *jd_profile.nice_to_have_skills,
            *jd_profile.responsibilities,
            *jd_profile.industry_background,
            *jd_profile.hard_requirements,
        ]
    )


def _contains_any(haystack: str, signals: Iterable[str]) -> bool:
    return any(signal.lower() in haystack for signal in signals)


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))
