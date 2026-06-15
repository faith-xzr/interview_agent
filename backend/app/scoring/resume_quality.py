import re
from pathlib import Path
from typing import Any, Iterable, List, Optional

from app.llm_timeouts import LLM_JSON_TIMEOUT_SECONDS
from app.schemas import CandidateProfile, ExtractedFact, ResumeQualityReport, ResumeQualityScoreDetail, ResumeQualitySuggestion


PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts" / "resume_quality"
SYSTEM_PROMPT_PATH = PROMPT_DIR / "resume_quality_system.st"
USER_PROMPT_PATH = PROMPT_DIR / "resume_quality_user.st"

SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
USER_PROMPT_TEMPLATE = USER_PROMPT_PATH.read_text(encoding="utf-8")

TECH_DEPTH_KEYWORDS = {
    "高并发",
    "分布式",
    "分布式锁",
    "原子",
    "Redis",
    "Redis",
    "缓存",
    "可观测",
    "链路",
    "幂等",
    "消息队列",
    "MQ",
    "Kafka",
    "RocketMQ",
    "Sentinel",
    "数据库",
    "索引",
    "优化",
    "压测",
    "性能",
    "并发",
    "限流",
    "治理",
    "一致性",
    "事务",
    "异步",
    "消息",
    "多线程",
    "线程池",
    "重构",
    "架构",
    "架构设计",
}

METRIC_PATTERN = re.compile(r"\b\d+(?:\.\d+)?%?\b|\d+\s*(?:万|千|亿|ms|s|秒|分钟|小时|天|人|页|次|单|条|GB|MB)", re.I)


def _record_failure(
    failure_sink: Optional[list[dict[str, Any]]],
    *,
    stage: str,
    failure_code: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
) -> None:
    if failure_sink is None:
        return
    failure_sink.append(
        {
            "stage": stage,
            "failure_code": failure_code,
            "message": message,
            "invalid_requirements": [],
            "details": details or {},
        }
    )


def _coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, str):
        if not value.strip():
            return 0
        try:
            return int(round(float(value.strip())))
        except ValueError:
            return 0
    return 0


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _to_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split("|") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [
            item.strip()
            for item in (str(item).strip() for item in value)
            if item.strip()
        ]
    return [_coerce_text(value)] if value else []


def _build_summary(profile: CandidateProfile, scores: ResumeQualityScoreDetail) -> str:
    if scores.project_score >= 30 and scores.skill_match_score >= 16:
        return "简历信息较完整，技术深度和项目经验表现较好。"
    if scores.project_score >= 20 or scores.skill_match_score >= 12:
        return "简历具备一定的技术和项目基础，建议补齐量化和技术细化。"
    return "简历结构和量化信息较薄弱，建议补齐项目结果与技术深度。"


def _fallback_strengths(profile: CandidateProfile, resume_text: str, facts: List[ExtractedFact]) -> List[str]:
    strengths: List[str] = []
    if profile.skills:
        strengths.append(f"技能覆盖较好（{len(profile.skills)} 项可评估项）")
    if profile.projects:
        strengths.append("包含项目经历，具备基于项目的技术表达")
    if profile.work_experiences:
        strengths.append("包含工作经历信息，便于评估真实职业轨迹")
    metric_count = len(METRIC_PATTERN.findall(resume_text))
    if metric_count >= 2:
        strengths.append("存在一定量化信息，可进行结果导向评估")
    if any(fact.fact_type in {"metric", "project"} for fact in facts):
        strengths.append("提取到可用于审核的项目/量化事实")
    return strengths[:3]


def _fallback_suggestions(profile: CandidateProfile, resume_text: str, scores: ResumeQualityScoreDetail) -> List[ResumeQualitySuggestion]:
    suggestions: List[ResumeQualitySuggestion] = []
    metric_count = len(METRIC_PATTERN.findall(resume_text))
    if len(profile.projects) < 2:
        suggestions.append(
            ResumeQualitySuggestion(
                category="项目",
                priority="高",
                issue="项目数偏少，难以完整体现能力闭环",
                recommendation="补充至少2个高质量项目，强调业务问题、方案和量化结果（如性能提升、产出周期）。",
            )
        )
    if scores.skill_match_score < 12:
        suggestions.append(
            ResumeQualitySuggestion(
                category="技能",
                priority="高",
                issue="技能覆盖不够完整或未结构化表达",
                recommendation="按照技术栈结构化拆分：编程语言、基础设施、数据库、中间件、平台能力，并结合实际项目映射。",
            )
        )
    if metric_count < 1:
        suggestions.append(
            ResumeQualitySuggestion(
                category="内容",
                priority="中",
                issue="缺少量化结果或业务指标",
                recommendation="每条核心项目补充1-2个结果指标（如响应时延、并发、QPS、成本、效率变化）。",
            )
        )
    if scores.structure_score < 10:
        suggestions.append(
            ResumeQualitySuggestion(
                category="格式",
                priority="中",
                issue="结构化排版不够规范",
                recommendation="建议按：个人信息、教育背景、技能清单、工作经历、项目经历、证书奖项排序，避免混乱堆砌。",
            )
        )
    if scores.expression_score < 8:
        suggestions.append(
            ResumeQualitySuggestion(
                category="内容",
                priority="低",
                issue="表达可读性不够，关键点不够突出",
                recommendation="采用‘结果导向’句式：场景+动作+方法+结果（如：针对 X 痛点，采用 Y 方案，提升 Z%）。",
            )
        )
    return suggestions[:4]


def _fallback_scores(profile: CandidateProfile, resume_text: str) -> ResumeQualityScoreDetail:
    text = resume_text or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    bullet_count = len([line for line in lines if re.match(r"^[\-•*]\s*", line)])

    section_headers = ("教育", "工作", "项目", "项目经历", "技能", "证书", "简介", "自我评价", "经历")
    section_count = len([line for line in lines if any(h in line for h in section_headers)])

    project_count = len(profile.projects)
    metric_count = len(METRIC_PATTERN.findall(text))
    skills = {item.strip() for item in profile.skills if item.strip()}
    tech_depth = len([kw for kw in TECH_DEPTH_KEYWORDS if kw.lower() in text.lower()])

    project_score = min(40, 6 + project_count * 8 + min(18, metric_count * 3) + min(10, tech_depth * 2))
    skill_match_score = min(20, 4 + len(skills) * 2 + (2 if any(kw in text for kw in ["Spring", "FastAPI", "Django", "MySQL", "Redis", "Kafka", "MQ"]) else 0))
    content_score = min(15, (3 if profile.education else 0) + (3 if profile.work_experiences else 0) + (4 if profile.projects else 0) + (3 if profile.skills else 0) + (2 if profile.certifications else 0))
    structure_score = min(15, section_count * 2 + min(5, bullet_count // 2))
    expression_score = 0
    if lines:
        avg_len = sum(len(line) for line in lines) / len(lines)
        if 20 <= avg_len <= 120:
            expression_score += 5
        elif avg_len > 120:
            expression_score += 3
        else:
            expression_score += 2
    expression_score += min(5, len([line for line in lines if re.search(r"[，。；:：]", line)] ) // 8)
    expression_score = min(10, max(1, expression_score))

    return ResumeQualityScoreDetail(
        project_score=project_score,
        skill_match_score=skill_match_score,
        content_score=content_score,
        structure_score=structure_score,
        expression_score=expression_score,
    )


def _build_from_llm_payload(payload: dict[str, Any]) -> ResumeQualityReport:
    if not isinstance(payload, dict):
        raise ValueError("Invalid payload")

    raw_detail = payload.get("scoreDetail") or payload.get("score_detail")
    if not isinstance(raw_detail, dict):
        raise ValueError("Missing scoreDetail")

    score_detail = ResumeQualityScoreDetail(
        project_score=_coerce_int(raw_detail.get("projectScore", raw_detail.get("project_score", 0))),
        skill_match_score=_coerce_int(raw_detail.get("skillMatchScore", raw_detail.get("skill_match_score", 0))),
        content_score=_coerce_int(raw_detail.get("contentScore", raw_detail.get("content_score", 0))),
        structure_score=_coerce_int(raw_detail.get("structureScore", raw_detail.get("structure_score", 0))),
        expression_score=_coerce_int(raw_detail.get("expressionScore", raw_detail.get("expression_score", 0))),
    )

    raw_suggestions = _to_list(payload.get("suggestions"))
    suggestions: List[ResumeQualitySuggestion] = []
    for item in raw_suggestions:
        if not isinstance(item, dict):
            continue
        suggestion = ResumeQualitySuggestion(
            category=_coerce_text(item.get("category")) or "内容",
            priority=_coerce_text(item.get("priority")) or "中",
            issue=_coerce_text(item.get("issue")),
            recommendation=_coerce_text(item.get("recommendation")),
        )
        if suggestion.issue and suggestion.recommendation:
            suggestions.append(suggestion)

    return ResumeQualityReport(
        overall_score=_coerce_int(payload.get("overallScore", payload.get("overall_score", 0))),
        score_detail=score_detail,
        summary=_coerce_text(payload.get("summary")) or "该简历暂未给出完整总结。",
        strengths=_to_list(payload.get("strengths")),
        suggestions=suggestions[:8],
    )


def score_resume_quality_with_llm(
    llm,
    resume_text: str,
    profile: CandidateProfile,
    extraction_facts: Iterable[ExtractedFact],
    *,
    failure_sink: Optional[list[dict[str, Any]]] = None,
) -> Optional[ResumeQualityReport]:
    if not getattr(llm, "available", False):
        return None
    try:
        prompt_payload = USER_PROMPT_TEMPLATE.replace("{resumeText}", resume_text)
        payload = llm.complete_json(
            SYSTEM_PROMPT,
            prompt_payload,
            timeout=LLM_JSON_TIMEOUT_SECONDS,
        )
        if not isinstance(payload, dict):
            raise ValueError(_llm_failure_reason(llm, payload))
        return _build_from_llm_payload(payload)
    except Exception as exc:
        _record_failure(
            failure_sink,
            stage="resume_quality",
            failure_code=str(exc),
            message=str(exc),
            details={"llm_timeout_seconds": LLM_JSON_TIMEOUT_SECONDS},
        )
        return None


def _llm_failure_reason(llm, payload: Any) -> str:
    last_error = getattr(llm, "last_error", None)
    if last_error:
        return str(last_error)
    if payload is None:
        return "llm_returned_none"
    return "invalid_llm_response"


def score_resume_quality(
    llm,
    resume_text: str,
    profile: CandidateProfile,
    extraction_facts: Iterable[ExtractedFact],
    *,
    failure_sink: Optional[list[dict[str, Any]]] = None,
) -> ResumeQualityReport:
    facts = list(extraction_facts)
    payload = score_resume_quality_with_llm(llm, resume_text, profile, facts, failure_sink=failure_sink)
    if payload is not None:
        payload.summary = _coerce_text(payload.summary) or _build_summary(profile, payload.score_detail)
        if not payload.strengths:
            payload.strengths = _fallback_strengths(profile, resume_text, facts)
        if not payload.suggestions:
            payload.suggestions = _fallback_suggestions(profile, resume_text, payload.score_detail)
        return payload

    score_detail = _fallback_scores(profile, resume_text)
    return ResumeQualityReport(
        overall_score=score_detail.project_score
        + score_detail.skill_match_score
        + score_detail.content_score
        + score_detail.structure_score
        + score_detail.expression_score,
        score_detail=score_detail,
        summary=_build_summary(profile, score_detail),
        strengths=_fallback_strengths(profile, resume_text, facts),
        suggestions=_fallback_suggestions(profile, resume_text, score_detail),
    )
