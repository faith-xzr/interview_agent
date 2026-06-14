from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, List, Optional
from uuid import uuid4

from app.interview_followup import generate_interview_answer_followup_for_question
from app.schemas import (
    AgentSkill,
    AgentSkillCategory,
    CandidateReport,
    InterviewFinalReport,
    InterviewQuestion,
    InterviewSession,
    InterviewSessionQuestion,
    InterviewTurn,
    RunReport,
)
from app.skills import SkillRepository, select_skill_for_direction

MAX_SESSION_TURNS = 5
PLANNED_QUESTION_SOURCES = {"planned", "fallback", "skill_planned", "skill_fallback"}


@dataclass(frozen=True)
class InterviewModeSpec:
    mode: str
    channel: str
    direction: str
    difficulty: str
    interviewer_style: str


def create_interview_session(
    run: RunReport,
    candidate: CandidateReport,
    mode: str = "structured",
    skill_repository: Optional[SkillRepository] = None,
) -> InterviewSession:
    now = datetime.utcnow()
    normalized_mode = (mode or "structured").strip() or "structured"
    mode_spec = _parse_interview_mode(normalized_mode)
    skill = _resolve_skill(mode_spec.direction, run, skill_repository)
    return InterviewSession(
        session_id=uuid4().hex,
        run_id=run.run_id,
        candidate_id=candidate.candidate_id,
        mode=normalized_mode,
        direction=mode_spec.direction,
        difficulty=mode_spec.difficulty,
        interviewer_style=mode_spec.interviewer_style,
        skill_id=skill.id if skill is not None else None,
        skill_name=skill.name if skill is not None else None,
        flow=_skill_flow(skill),
        status="active",
        created_at=now,
        updated_at=now,
        current_question=_planned_question(candidate, 0, skill),
    )


def submit_interview_turn(
    llm: Any,
    run: RunReport,
    candidate: CandidateReport,
    session: InterviewSession,
    candidate_answer: str,
    skill_repository: Optional[SkillRepository] = None,
) -> InterviewSession:
    answer = (candidate_answer or "").strip()
    if not answer:
        raise ValueError("候选人回答不能为空。")
    if session.status == "completed":
        raise ValueError("该面试会话已完成，不能继续追加回答。")
    if session.current_question is None:
        raise ValueError("当前会话没有待回答问题，请先生成最终报告。")

    current_question = session.current_question
    diagnosis = generate_interview_answer_followup_for_question(
        llm,
        run.jd_profile,
        candidate,
        _as_interview_question(current_question),
        current_question.question_index,
        answer,
    )
    turn = InterviewTurn(
        turn_index=len(session.turns) + 1,
        question=current_question,
        answer=answer,
        diagnosis=diagnosis,
    )
    session.turns.append(turn)
    skill = _resolve_session_skill(session, run, skill_repository)
    session.current_question = _next_question(
        candidate,
        session,
        diagnosis.followup_needed,
        diagnosis.followup_question,
        skill,
    )
    session.status = "active" if session.current_question is not None else "ready_for_report"
    session.updated_at = datetime.utcnow()
    return session


def finalize_interview_session(session: InterviewSession) -> InterviewSession:
    session.final_report = _build_final_report(session.turns)
    session.status = "completed"
    session.current_question = None
    session.updated_at = datetime.utcnow()
    return session


def _next_question(
    candidate: CandidateReport,
    session: InterviewSession,
    followup_needed: bool,
    followup_question: str,
    skill: Optional[AgentSkill],
) -> Optional[InterviewSessionQuestion]:
    last_question = session.turns[-1].question
    if followup_needed and followup_question and len(session.turns) < MAX_SESSION_TURNS:
        return InterviewSessionQuestion(
            question=followup_question,
            focus="动态追问",
            scoring_criteria=session.turns[-1].diagnosis.expected_signal,
            source="dynamic_followup",
            question_index=last_question.question_index,
            skill_id=session.skill_id,
            stage=last_question.stage or "dynamic_followup",
        )
    if len(session.turns) >= MAX_SESSION_TURNS:
        return None
    return _planned_question(candidate, _next_planned_index(session.turns), skill)


def _planned_question(
    candidate: CandidateReport,
    index: int,
    skill: Optional[AgentSkill] = None,
) -> Optional[InterviewSessionQuestion]:
    category = _category_for_index(skill, index)
    questions = candidate.match_report.interview_questions
    if not questions:
        return InterviewSessionQuestion(
            question=_fallback_question(skill, category),
            focus=_stage_focus("岗位匹配度与项目真实性", category),
            scoring_criteria=_stage_scoring_criteria(
                "优秀回答应覆盖项目背景、个人职责、关键动作、量化结果和复盘。",
                skill,
                category,
                index,
            ),
            source="skill_fallback" if skill is not None else "fallback",
            question_index=index,
            skill_id=skill.id if skill is not None else None,
            stage=category.key if category is not None else None,
        )
    if index >= len(questions):
        return None
    question = questions[index]
    return InterviewSessionQuestion(
        question=question.question,
        focus=_stage_focus(question.focus, category),
        scoring_criteria=_stage_scoring_criteria(question.scoring_criteria, skill, category, index),
        source="skill_planned" if skill is not None else "planned",
        question_index=index,
        skill_id=skill.id if skill is not None else None,
        stage=category.key if category is not None else None,
    )


def _next_planned_index(turns: Iterable[InterviewTurn]) -> int:
    used = {
        turn.question.question_index
        for turn in turns
        if turn.question.source in PLANNED_QUESTION_SOURCES
    }
    index = 0
    while index in used:
        index += 1
    return index


def _as_interview_question(question: InterviewSessionQuestion) -> InterviewQuestion:
    return InterviewQuestion(
        question=question.question,
        focus=question.focus,
        scoring_criteria=question.scoring_criteria,
    )


def _parse_interview_mode(mode: str) -> InterviewModeSpec:
    parts = [part.strip() for part in mode.split(":")]
    channel = parts[0] if parts and parts[0] else "structured"
    direction = parts[1] if len(parts) > 1 else ""
    difficulty = parts[2] if len(parts) > 2 else ""
    interviewer_style = parts[3] if len(parts) > 3 else ""
    return InterviewModeSpec(
        mode=mode,
        channel=channel,
        direction=direction,
        difficulty=difficulty,
        interviewer_style=interviewer_style,
    )


def _resolve_skill(
    direction: str,
    run: RunReport,
    repository: Optional[SkillRepository],
) -> Optional[AgentSkill]:
    if repository is None:
        return None
    return select_skill_for_direction(direction, repository, run.jd_profile)


def _resolve_session_skill(
    session: InterviewSession,
    run: RunReport,
    repository: Optional[SkillRepository],
) -> Optional[AgentSkill]:
    if repository is None:
        return None
    if session.skill_id:
        skill = repository.get_optional(session.skill_id)
        if skill is not None:
            return skill
    return select_skill_for_direction(session.direction, repository, run.jd_profile)


def _skill_flow(skill: Optional[AgentSkill]) -> List[str]:
    if skill is None:
        return []
    return [category.label for category in skill.categories]


def _category_for_index(skill: Optional[AgentSkill], index: int) -> Optional[AgentSkillCategory]:
    if skill is None or not skill.categories:
        return None
    return skill.categories[index % len(skill.categories)]


def _stage_focus(base_focus: str, category: Optional[AgentSkillCategory]) -> str:
    if category is None:
        return base_focus
    if not base_focus:
        return category.label
    return f"{category.label} · {base_focus}"


def _stage_scoring_criteria(
    base_criteria: str,
    skill: Optional[AgentSkill],
    category: Optional[AgentSkillCategory],
    index: int,
) -> str:
    if skill is None:
        return base_criteria
    additions: list[str] = []
    if category is not None:
        additions.append(f"方向要求：围绕「{skill.name} / {category.label}」验证真实经验、机制理解、边界场景和权衡。")
    elif skill.name:
        additions.append(f"方向要求：围绕「{skill.name}」验证真实经验、机制理解、边界场景和权衡。")
    if skill.rubric_focuses:
        additions.append(f"评分锚点：{skill.rubric_focuses[index % len(skill.rubric_focuses)]}")
    return "；".join([item for item in [base_criteria, *additions] if item])


def _fallback_question(skill: Optional[AgentSkill], category: Optional[AgentSkillCategory]) -> str:
    if skill is None:
        return "请结合你的简历，介绍一个最能代表你岗位匹配度的项目，并说明个人贡献和结果。"
    if category is not None:
        return f"请结合你的简历，讲一个最能体现「{category.label}」能力的项目，并说明你的个人贡献、关键取舍和结果。"
    return f"请结合你的简历，讲一个最能体现「{skill.name}」岗位匹配度的项目，并说明个人贡献和结果。"


def _build_final_report(turns: List[InterviewTurn]) -> InterviewFinalReport:
    if not turns:
        return InterviewFinalReport(
            summary="本次面试尚未产生有效问答记录。",
            risks=["缺少候选人回答，无法判断真实能力。"],
            next_steps=["至少完成 2-3 轮围绕简历证据的追问后再评估。"],
        )

    clarity = round(sum(turn.diagnosis.clarity_score for turn in turns) / len(turns))
    depth = round(sum(turn.diagnosis.depth_score for turn in turns) / len(turns))
    consistency = _overall_consistency(turns)
    consistency_score = {"consistent": 100, "weak": 65, "contradictory": 35}[consistency]
    overall = round(clarity * 0.35 + depth * 0.45 + consistency_score * 0.2)
    issues = _unique_issue_texts(issue for turn in turns for issue in turn.diagnosis.issues)
    strengths = _strengths_for_scores(clarity, depth, turns)
    risks = issues[:5] or ["暂无明显风险，但仍建议继续围绕核心项目做交叉验证。"]

    return InterviewFinalReport(
        overall_score=overall,
        clarity_score=clarity,
        depth_score=depth,
        evidence_consistency=consistency,
        recommendation=_recommendation(overall, consistency),
        strengths=strengths,
        risks=risks,
        summary=(
            f"本次面试完成 {len(turns)} 轮问答。候选人平均表达清晰度 {clarity} 分，"
            f"回答深度 {depth} 分，证据一致性为 {consistency}。"
        ),
        next_steps=_next_steps_for_issues(issues, consistency),
    )


def _overall_consistency(turns: List[InterviewTurn]) -> str:
    values = [turn.diagnosis.evidence_consistency for turn in turns]
    if any(value == "contradictory" for value in values):
        return "contradictory"
    if values and all(value == "consistent" for value in values):
        return "consistent"
    return "weak"


def _strengths_for_scores(clarity: int, depth: int, turns: List[InterviewTurn]) -> List[str]:
    strengths: List[str] = []
    if clarity >= 70:
        strengths.append("回答表达相对清楚，能覆盖问题主干。")
    if depth >= 70:
        strengths.append("回答中包含一定项目细节，具备继续深挖价值。")
    if any(turn.diagnosis.evidence_consistency == "consistent" for turn in turns):
        strengths.append("部分回答能与简历证据保持一致。")
    return strengths or ["已形成初步面试记录，可作为后续追问依据。"]


def _recommendation(overall: int, consistency: str) -> str:
    if consistency == "contradictory":
        return "暂缓推进，优先核验证据矛盾"
    if overall >= 75:
        return "建议推进下一轮"
    if overall >= 60:
        return "谨慎推进，补充验证关键缺口"
    return "暂缓推进，继续深挖核心能力"


def _next_steps_for_issues(issues: List[str], consistency: str) -> List[str]:
    steps: List[str] = []
    if consistency == "contradictory":
        steps.append("对照简历原文逐项核验矛盾点，必要时要求候选人补充证明材料。")
    if any("量化" in issue for issue in issues):
        steps.append("继续要求候选人给出指标口径、基线、提升幅度和验证方式。")
    if any("个人职责" in issue for issue in issues):
        steps.append("追问候选人与团队其他成员的边界，确认真实个人贡献。")
    if any("技术细节" in issue for issue in issues):
        steps.append("围绕一个具体方案追问架构、取舍、失败案例和复盘。")
    if not steps:
        steps.append("下一轮可以直接进入岗位场景题或更高压的反事实追问。")
    return steps


def _unique_issue_texts(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        text = (item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
