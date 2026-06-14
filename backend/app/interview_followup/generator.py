import json
from pathlib import Path
import re
from typing import Any, Dict, Optional

from app.schemas import CandidateReport, InterviewAnswerFollowUp, InterviewQuestion, JDProfile


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "interview_followup" / "answer_diagnosis.md"
SYSTEM_PROMPT = "你是招聘面试官追问助手。只输出 JSON，不要输出解释文本。"
CONSISTENCY_VALUES = {"consistent", "weak", "contradictory"}


def generate_interview_answer_followup(
    llm: Any,
    jd: JDProfile,
    candidate: CandidateReport,
    question_index: int,
    candidate_answer: str,
) -> InterviewAnswerFollowUp:
    question = candidate.match_report.interview_questions[question_index]
    return generate_interview_answer_followup_for_question(
        llm,
        jd,
        candidate,
        question,
        question_index,
        candidate_answer,
    )


def generate_interview_answer_followup_for_question(
    llm: Any,
    jd: JDProfile,
    candidate: CandidateReport,
    question: InterviewQuestion,
    question_index: int,
    candidate_answer: str,
) -> InterviewAnswerFollowUp:
    answer = candidate_answer.strip()
    if getattr(llm, "available", False):
        payload = _call_llm(llm, jd, candidate, question, question_index, answer)
        parsed = _parse_llm_payload(payload, question, question_index, answer)
        if parsed is not None:
            return parsed
    return _rule_based_followup(question, question_index, answer)


def _call_llm(
    llm: Any,
    jd: JDProfile,
    candidate: CandidateReport,
    question: InterviewQuestion,
    question_index: int,
    answer: str,
) -> Optional[Dict[str, Any]]:
    context = {
        "jd_profile": jd.model_dump(mode="json"),
        "candidate_profile": candidate.profile.model_dump(mode="json"),
        "match_reasons": candidate.match_report.match_reasons,
        "gap_reasons": candidate.match_report.gap_reasons,
        "evidence_snippets": [item.model_dump(mode="json") for item in candidate.match_report.evidence_snippets[:5]],
        "question_index": question_index,
        "interview_question": question.model_dump(mode="json"),
        "candidate_answer": answer,
    }
    prompt = PROMPT_PATH.read_text(encoding="utf-8").replace(
        "{{CONTEXT_JSON}}",
        json.dumps(context, ensure_ascii=False, indent=2),
    )
    try:
        payload = llm.complete_json(SYSTEM_PROMPT, prompt)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_llm_payload(
    payload: Optional[Dict[str, Any]],
    question: InterviewQuestion,
    question_index: int,
    answer: str,
) -> Optional[InterviewAnswerFollowUp]:
    if not payload:
        return None
    followup_question = _coerce_text(payload.get("followup_question"))
    followup_needed = bool(payload.get("followup_needed", bool(followup_question)))
    if followup_needed and not followup_question:
        return None
    if not followup_needed and not followup_question:
        followup_question = "这道题回答已较完整，可以进入下一题。"
    issues = _coerce_text_list(payload.get("issues"))
    consistency = _normalize_consistency(_coerce_text(payload.get("evidence_consistency")))
    return InterviewAnswerFollowUp(
        question_index=question_index,
        original_question=question.question,
        candidate_answer=answer,
        answer_summary=_coerce_text(payload.get("answer_summary")) or _summarize_answer(answer),
        clarity_score=_coerce_int(payload.get("clarity_score"), 60),
        depth_score=_coerce_int(payload.get("depth_score"), 60),
        evidence_consistency=consistency,
        issues=issues,
        followup_needed=followup_needed,
        followup_question=followup_question,
        reason=_coerce_text(payload.get("reason")) or "候选人回答仍有需要澄清的信息。",
        expected_signal=_coerce_text(payload.get("expected_signal")) or "验证候选人能否补充具体证据。",
        source="llm",
    )


def _rule_based_followup(question: InterviewQuestion, question_index: int, answer: str) -> InterviewAnswerFollowUp:
    issues = _detect_answer_issues(answer)
    followup_needed = bool(issues)
    followup_question = (
        _build_followup_question(answer, issues)
        if followup_needed
        else "这道题回答已较完整，可以进入下一题。"
    )
    penalty = len(issues) * 16
    clarity_score = max(20, 88 - penalty - (12 if len(answer) < 80 else 0))
    depth_score = max(20, 82 - penalty - (14 if "缺少量化结果" in issues else 0))
    return InterviewAnswerFollowUp(
        question_index=question_index,
        original_question=question.question,
        candidate_answer=answer,
        answer_summary=_summarize_answer(answer),
        clarity_score=clarity_score,
        depth_score=depth_score,
        evidence_consistency="weak" if followup_needed else "consistent",
        issues=issues,
        followup_needed=followup_needed,
        followup_question=followup_question,
        reason=_reason_for_issues(issues),
        expected_signal=_expected_signal_for_issues(issues),
        source="rules",
    )


def _detect_answer_issues(answer: str) -> list[str]:
    issues: list[str] = []
    if len(answer) < 60:
        issues.append("回答过短，缺少关键细节")
    if not re.search(r"(我|本人|负责|主导|参与|实现|设计|落地|推进|优化)", answer):
        issues.append("缺少个人职责")
    if not re.search(r"(\d+[%％倍]?|QPS|准确率|召回率|转化率|成本|时延|耗时|提升|降低|增长)", answer, re.IGNORECASE):
        issues.append("缺少量化结果")
    if not re.search(r"(因为|通过|使用|架构|接口|数据库|模型|指标|方案|流程|监控|评估|优化|FastAPI|SQL|RAG|Python)", answer, re.IGNORECASE):
        issues.append("技术细节较泛")
    if re.search(r"(不清楚|没有|没做过|不了解|不太熟)", answer):
        issues.append("与题目期待存在潜在不一致")
    return issues[:4]


def _build_followup_question(answer: str, issues: list[str]) -> str:
    lead = _answer_lead(answer)
    if "缺少个人职责" in issues or "缺少量化结果" in issues:
        return f"你刚才提到{lead}，能具体说明你个人负责的环节、关键实现，以及用什么指标验证结果吗？"
    if "技术细节较泛" in issues:
        return f"关于{lead}，你能展开一个具体技术决策、当时的替代方案和最终取舍吗？"
    if "与题目期待存在潜在不一致" in issues:
        return f"你刚才的回答和这道题的考察点有些偏离，能补充一个更贴近原问题的真实案例吗？"
    return f"你能围绕{lead}补充一个更具体的项目背景、行动和结果吗？"


def _answer_lead(answer: str) -> str:
    compact = re.sub(r"\s+", "", answer)
    if not compact:
        return "这个问题"
    return f"“{compact[:24]}{'…' if len(compact) > 24 else ''}”"


def _reason_for_issues(issues: list[str]) -> str:
    if not issues:
        return "候选人回答覆盖了当前问题的主要判断点。"
    return "回答存在" + "、".join(issues[:3]) + "，需要继续澄清。"


def _expected_signal_for_issues(issues: list[str]) -> str:
    if "缺少个人职责" in issues and "缺少量化结果" in issues:
        return "候选人能否讲清个人贡献、关键实现和可验证结果。"
    if "技术细节较泛" in issues:
        return "候选人能否补充具体技术路径和决策依据。"
    if "与题目期待存在潜在不一致" in issues:
        return "候选人是否真的具备题目考察的相关经验。"
    return "候选人能否把回答从概述补充为可验证事实。"


def _summarize_answer(answer: str) -> str:
    if not answer:
        return "候选人尚未提供有效回答。"
    compact = re.sub(r"\s+", " ", answer).strip()
    return compact[:90] + ("..." if len(compact) > 90 else "")


def _normalize_consistency(value: str) -> str:
    if value in CONSISTENCY_VALUES:
        return value
    if "矛盾" in value:
        return "contradictory"
    if "一致" in value:
        return "consistent"
    return "weak"


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        return [text for text in (_coerce_text(item) for item in value) if text]
    text = _coerce_text(value)
    return [text] if text else []


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default
