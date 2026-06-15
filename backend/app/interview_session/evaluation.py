from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from app.llm_timeouts import LLM_JSON_TIMEOUT_SECONDS
from app.schemas import (
    AgentSkill,
    CandidateReport,
    InterviewCategoryScore,
    InterviewFinalReport,
    InterviewQuestionEvaluation,
    InterviewReferenceAnswer,
    InterviewTurn,
    RunReport,
)

PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts" / "interview_evaluation"
SYSTEM_PROMPT = (PROMPT_DIR / "interview_evaluation_system.md").read_text(encoding="utf-8")
USER_PROMPT_TEMPLATE = (PROMPT_DIR / "interview_evaluation_user.md").read_text(encoding="utf-8")
SUMMARY_SYSTEM_PROMPT = (PROMPT_DIR / "interview_evaluation_summary_system.md").read_text(encoding="utf-8")
SUMMARY_USER_PROMPT_TEMPLATE = (PROMPT_DIR / "interview_evaluation_summary_user.md").read_text(encoding="utf-8")

BATCH_SIZE = 8
MAX_RESUME_CONTEXT_CHARS = 3000
MAX_REFERENCE_CONTEXT_CHARS = 6000


@dataclass(frozen=True)
class BatchReport:
    start_index: int
    end_index: int
    overall_score: int
    overall_feedback: str
    strengths: list[str]
    improvements: list[str]
    question_evaluations: list[QuestionEvaluationDraft]


@dataclass(frozen=True)
class QuestionEvaluationDraft:
    question_index: int
    score: int
    feedback: str
    reference_answer: str
    key_points: list[str]


@dataclass(frozen=True)
class SummaryDraft:
    overall_feedback: str
    strengths: list[str]
    improvements: list[str]


def build_llm_final_report(
    llm: Any,
    turns: list[InterviewTurn],
    *,
    run: Optional[RunReport] = None,
    candidate: Optional[CandidateReport] = None,
    skill: Optional[AgentSkill] = None,
) -> Optional[InterviewFinalReport]:
    if not turns or not getattr(llm, "available", False):
        return None

    job_context = _build_job_context(run, candidate, skill)
    resume_context = _truncate(_build_resume_context(candidate), MAX_RESUME_CONTEXT_CHARS)
    reference_context = _truncate(_build_reference_context(skill, candidate), MAX_REFERENCE_CONTEXT_CHARS)

    batch_reports: list[BatchReport] = []
    for start in range(0, len(turns), BATCH_SIZE):
        end = min(start + BATCH_SIZE, len(turns))
        batch = turns[start:end]
        raw = _complete_json(
            llm,
            SYSTEM_PROMPT,
            _render_prompt(
                USER_PROMPT_TEMPLATE,
                {
                    "jobContext": job_context,
                    "resumeText": resume_context,
                    "qaRecords": _build_qa_records(batch),
                    "referenceContext": reference_context or "无",
                },
            ),
        )
        parsed = _parse_batch_report(raw, batch, start, end)
        if parsed is not None:
            batch_reports.append(parsed)

    if not batch_reports:
        return None

    question_drafts = _merge_question_evaluations(turns, batch_reports)
    fallback_feedback = _merge_feedback(batch_reports)
    fallback_strengths = _merge_items(report.strengths for report in batch_reports)
    fallback_improvements = _merge_items(report.improvements for report in batch_reports)
    summary = _summarize_reports(
        llm,
        turns,
        question_drafts,
        job_context,
        resume_context,
        reference_context,
        fallback_feedback,
        fallback_strengths,
        fallback_improvements,
    )
    return _build_report(turns, question_drafts, summary)


def _complete_json(llm: Any, system_prompt: str, user_prompt: str) -> Optional[dict[str, Any]]:
    try:
        payload = llm.complete_json(system_prompt, user_prompt, timeout=LLM_JSON_TIMEOUT_SECONDS)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_batch_report(
    payload: Optional[dict[str, Any]],
    batch: list[InterviewTurn],
    start_index: int,
    end_index: int,
) -> Optional[BatchReport]:
    if not isinstance(payload, dict):
        return None
    raw_evaluations = _get(payload, "questionEvaluations", "question_evaluations")
    if not isinstance(raw_evaluations, list):
        return None

    drafts: list[QuestionEvaluationDraft] = []
    for position, raw_item in enumerate(raw_evaluations[: len(batch)]):
        if not isinstance(raw_item, dict):
            continue
        fallback_index = start_index + position
        drafts.append(
            QuestionEvaluationDraft(
                question_index=_coerce_int(_get(raw_item, "questionIndex", "question_index"), fallback_index),
                score=_coerce_score(_get(raw_item, "score")),
                feedback=_coerce_text(_get(raw_item, "feedback")),
                reference_answer=_coerce_text(_get(raw_item, "referenceAnswer", "reference_answer")),
                key_points=_coerce_text_list(_get(raw_item, "keyPoints", "key_points")),
            )
        )

    if not drafts:
        return None
    return BatchReport(
        start_index=start_index,
        end_index=end_index,
        overall_score=_coerce_score(_get(payload, "overallScore", "overall_score")),
        overall_feedback=_coerce_text(_get(payload, "overallFeedback", "overall_feedback")),
        strengths=_coerce_text_list(_get(payload, "strengths")),
        improvements=_coerce_text_list(_get(payload, "improvements")),
        question_evaluations=drafts,
    )


def _merge_question_evaluations(
    turns: list[InterviewTurn],
    batch_reports: list[BatchReport],
) -> list[QuestionEvaluationDraft]:
    by_index: dict[int, QuestionEvaluationDraft] = {}
    for report in batch_reports:
        for item in report.question_evaluations:
            by_index[item.question_index] = item

    merged: list[QuestionEvaluationDraft] = []
    for question_index, turn in enumerate(turns):
        item = by_index.get(question_index)
        if item is not None:
            merged.append(item)
            continue
        merged.append(
            QuestionEvaluationDraft(
                question_index=question_index,
                score=0,
                feedback="该题未成功生成评估结果，系统按 0 分处理。",
                reference_answer="",
                key_points=[],
            )
        )
    return merged


def _summarize_reports(
    llm: Any,
    turns: list[InterviewTurn],
    evaluations: list[QuestionEvaluationDraft],
    job_context: str,
    resume_context: str,
    reference_context: str,
    fallback_feedback: str,
    fallback_strengths: list[str],
    fallback_improvements: list[str],
) -> SummaryDraft:
    raw = _complete_json(
        llm,
        SUMMARY_SYSTEM_PROMPT,
        _render_prompt(
            SUMMARY_USER_PROMPT_TEMPLATE,
            {
                "jobContext": job_context,
                "resumeText": resume_context,
                "referenceContext": reference_context or "无",
                "categorySummary": _build_category_summary(turns, evaluations),
                "questionHighlights": _build_question_highlights(turns, evaluations),
                "fallbackOverallFeedback": fallback_feedback,
                "fallbackStrengths": "\n".join(fallback_strengths),
                "fallbackImprovements": "\n".join(fallback_improvements),
            },
        ),
    )
    if not isinstance(raw, dict):
        return SummaryDraft(fallback_feedback, fallback_strengths, fallback_improvements)
    feedback = _coerce_text(_get(raw, "overallFeedback", "overall_feedback")) or fallback_feedback
    strengths = _coerce_text_list(_get(raw, "strengths")) or fallback_strengths
    improvements = _coerce_text_list(_get(raw, "improvements")) or fallback_improvements
    return SummaryDraft(feedback, _distinct(strengths, 8), _distinct(improvements, 8))


def _build_report(
    turns: list[InterviewTurn],
    evaluations: list[QuestionEvaluationDraft],
    summary: SummaryDraft,
) -> InterviewFinalReport:
    question_evaluations: list[InterviewQuestionEvaluation] = []
    reference_answers: list[InterviewReferenceAnswer] = []
    scores_by_category: dict[str, list[int]] = defaultdict(list)
    evaluation_by_index = {item.question_index: item for item in evaluations}

    for sequence_index, turn in enumerate(turns):
        question_index = sequence_index
        item = evaluation_by_index.get(question_index)
        score = item.score if item is not None and turn.answer.strip() else 0
        category = _turn_category(turn)
        feedback = item.feedback if item is not None else "该题未成功生成评估反馈。"
        reference_answer = item.reference_answer if item is not None else ""
        key_points = item.key_points if item is not None else []
        scores_by_category[category].append(score)
        question_evaluations.append(
            InterviewQuestionEvaluation(
                question_index=question_index,
                question=turn.question.question,
                category=category,
                user_answer=turn.answer,
                score=score,
                feedback=feedback,
            )
        )
        reference_answers.append(
            InterviewReferenceAnswer(
                question_index=question_index,
                question=turn.question.question,
                reference_answer=reference_answer,
                key_points=key_points,
            )
        )

    category_scores = [
        InterviewCategoryScore(
            category=category,
            score=round(sum(scores) / len(scores)) if scores else 0,
            question_count=len(scores),
        )
        for category, scores in sorted(scores_by_category.items())
    ]
    answered_scores = [item.score for item in question_evaluations if item.user_answer.strip()]
    overall_score = round(sum(answered_scores) / len(answered_scores)) if answered_scores else 0
    clarity_score = round(sum(turn.diagnosis.clarity_score for turn in turns) / len(turns))
    depth_score = round(sum(turn.diagnosis.depth_score for turn in turns) / len(turns))
    consistency = _overall_consistency(turns)
    improvements = summary.improvements or ["继续围绕岗位核心能力做证据核验。"]
    return InterviewFinalReport(
        overall_score=overall_score,
        clarity_score=clarity_score,
        depth_score=depth_score,
        evidence_consistency=consistency,
        recommendation=_recommendation(overall_score, consistency),
        strengths=summary.strengths or ["已形成可评估的面试问答记录。"],
        risks=improvements,
        summary=summary.overall_feedback,
        next_steps=_next_steps_from_improvements(improvements),
        category_scores=category_scores,
        question_evaluations=question_evaluations,
        reference_answers=reference_answers,
    )


def _build_qa_records(turns: list[InterviewTurn]) -> str:
    parts: list[str] = []
    for sequence_index, turn in enumerate(turns):
        parts.append(
            "\n".join(
                [
                    f"问题{sequence_index + 1} [{_turn_category(turn)}]: {turn.question.question}",
                    f"考察点: {turn.question.focus or '未说明'}",
                    f"评分标准: {turn.question.scoring_criteria or '未说明'}",
                    f"回答: {turn.answer or '(未回答)'}",
                    f"上一轮诊断: 清晰度 {turn.diagnosis.clarity_score}，深度 {turn.diagnosis.depth_score}，"
                    f"证据一致性 {turn.diagnosis.evidence_consistency}，问题 {', '.join(turn.diagnosis.issues) or '无'}",
                ]
            )
        )
    return "\n\n".join(parts)


def _build_job_context(
    run: Optional[RunReport],
    candidate: Optional[CandidateReport],
    skill: Optional[AgentSkill],
) -> str:
    lines: list[str] = []
    if run is not None:
        jd = run.jd_profile
        lines.extend(
            [
                f"岗位名称: {jd.job_title}",
                f"职责: {'；'.join(jd.responsibilities) or '未说明'}",
                f"必备技能: {'、'.join(jd.required_skills) or '未说明'}",
                f"加分技能: {'、'.join(jd.nice_to_have_skills) or '未说明'}",
                f"硬性要求: {'；'.join(jd.hard_requirements) or '未说明'}",
            ]
        )
    if candidate is not None:
        report = candidate.match_report
        lines.extend(
            [
                f"候选人匹配分: {report.total_score}",
                f"匹配结论: {report.decision}",
                f"匹配理由: {'；'.join(report.match_reasons[:5]) or '无'}",
                f"待确认缺口: {'；'.join(report.gap_reasons[:5]) or '无'}",
            ]
        )
    if skill is not None:
        lines.extend(
            [
                f"面试方向: {skill.name}",
                f"方向说明: {skill.description or '无'}",
                f"评分锚点: {'；'.join(skill.rubric_focuses[:6]) or '无'}",
            ]
        )
    return "\n".join(lines) or "无"


def _build_resume_context(candidate: Optional[CandidateReport]) -> str:
    if candidate is None:
        return ""
    profile = candidate.profile
    lines = [
        f"候选人: {profile.name}",
        f"目标岗位: {profile.target_role or '未说明'}",
        f"教育经历: {'；'.join(profile.education) or '未说明'}",
        f"工作经历: {'；'.join(profile.work_experiences) or '未说明'}",
        f"项目经历: {'；'.join(profile.projects) or '未说明'}",
        f"技能: {'、'.join(profile.skills) or '未说明'}",
        f"亮点: {'；'.join(profile.highlights) or '无'}",
        f"风险点: {'；'.join(profile.risk_points) or '无'}",
        f"模糊点: {'；'.join(profile.ambiguous_points) or '无'}",
    ]
    return "\n".join(lines)


def _build_reference_context(skill: Optional[AgentSkill], candidate: Optional[CandidateReport]) -> str:
    lines: list[str] = []
    if skill is not None:
        lines.extend(
            [
                f"# {skill.name} 面试参考基线",
                skill.body,
            ]
        )
        if skill.categories:
            category_lines = [
                f"- {category.label}（{category.priority}，权重 {category.weight:g}）"
                for category in skill.categories
            ]
            lines.append("## Skill 分类\n" + "\n".join(category_lines))
        if skill.question_focuses:
            lines.append("## 常用追问方向\n" + "\n".join(f"- {item}" for item in skill.question_focuses))
    if candidate is not None:
        match = candidate.match_report
        lines.append("## 匹配缺口\n" + "\n".join(f"- {item}" for item in match.gap_reasons[:8]))
        if match.requirement_matches:
            requirements = [
                f"- {item.requirement}: {item.status}，{item.reason}"
                for item in match.requirement_matches[:12]
            ]
            lines.append("## Rubric 覆盖情况\n" + "\n".join(requirements))
    return "\n\n".join(part for part in lines if part.strip())


def _build_category_summary(turns: list[InterviewTurn], evaluations: list[QuestionEvaluationDraft]) -> str:
    evaluation_by_index = {item.question_index: item for item in evaluations}
    scores_by_category: dict[str, list[int]] = defaultdict(list)
    for sequence_index, turn in enumerate(turns):
        item = evaluation_by_index.get(sequence_index)
        score = item.score if item is not None and turn.answer.strip() else 0
        scores_by_category[_turn_category(turn)].append(score)
    lines = []
    for category, scores in sorted(scores_by_category.items()):
        average = round(sum(scores) / len(scores)) if scores else 0
        lines.append(f"- {category}: 平均分 {average}, 题数 {len(scores)}")
    return "\n".join(lines) or "无"


def _build_question_highlights(turns: list[InterviewTurn], evaluations: list[QuestionEvaluationDraft]) -> str:
    evaluation_by_index = {item.question_index: item for item in evaluations}
    highlights: list[str] = []
    for sequence_index, turn in enumerate(turns[:20]):
        item = evaluation_by_index.get(sequence_index)
        score = item.score if item is not None else 0
        feedback = _truncate(item.feedback if item is not None else "", 80)
        question = _truncate(turn.question.question, 50)
        highlights.append(f"- Q{sequence_index + 1} | {question} | 分数:{score} | 反馈:{feedback}")
    return "\n".join(highlights) or "无"


def _turn_category(turn: InterviewTurn) -> str:
    return (turn.question.stage or turn.question.focus or "综合").strip() or "综合"


def _merge_feedback(batch_reports: list[BatchReport]) -> str:
    feedback = "\n\n".join(report.overall_feedback for report in batch_reports if report.overall_feedback)
    return feedback or "本次面试已完成分批评估，但未生成有效综合评语。"


def _merge_items(groups: Iterable[list[str]]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        merged.extend(group)
    return _distinct(merged, 8)


def _next_steps_from_improvements(improvements: list[str]) -> list[str]:
    if not improvements:
        return ["下一轮继续围绕岗位核心能力做证据核验。"]
    steps = []
    for item in improvements[:5]:
        text = item.strip().rstrip("。")
        if text.startswith(("补充", "追问", "核验", "确认", "要求")):
            steps.append(text + "。")
        else:
            steps.append(f"下一轮重点核验：{text}。")
    return steps


def _overall_consistency(turns: list[InterviewTurn]) -> str:
    values = [turn.diagnosis.evidence_consistency for turn in turns]
    if any(value == "contradictory" for value in values):
        return "contradictory"
    if values and all(value == "consistent" for value in values):
        return "consistent"
    return "weak"


def _recommendation(overall: int, consistency: str) -> str:
    if consistency == "contradictory":
        return "暂缓推进，优先核验证据矛盾"
    if overall >= 85:
        return "建议推进下一轮"
    if overall >= 70:
        return "可推进，继续验证关键深度"
    if overall >= 60:
        return "谨慎推进，补充验证关键缺口"
    return "暂缓推进，继续深挖核心能力"


def _render_prompt(template: str, values: dict[str, str]) -> str:
    result = template
    for key, value in values.items():
        result = result.replace("{" + key + "}", value)
    return result


def _get(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _coerce_score(value: Any) -> int:
    return max(0, min(100, _coerce_int(value, 0)))


def _coerce_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(round(value))
    if isinstance(value, str) and value.strip():
        try:
            return int(round(float(value.strip())))
        except ValueError:
            return default
    return default


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
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


def _distinct(items: Iterable[str], limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...(内容过长，已截断)"
