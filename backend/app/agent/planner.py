from datetime import datetime
from typing import Iterable, Optional
from uuid import uuid4

from app.schemas import AgentPlan, AgentPlanStep, AgentSkill, AgentState, JDProfile


def build_recruiting_agent_plan(jd_profile: JDProfile, skills: Iterable[AgentSkill]) -> AgentPlan:
    selected_skills = list(skills)
    return AgentPlan(
        plan_id=f"plan-{uuid4().hex}",
        objective="连接 JD/简历解析、证据评分、面试追问和最终评估报告。",
        strategy="code_driven_orchestration_with_llm_specialists",
        selected_skill_ids=[skill.id for skill in selected_skills],
        question_budget=10,
        followup_policy="先生成 3-5 个证据缺口追问，再在每轮回答后动态判断是否追问。",
        evidence_requirements=[
            "所有 JD 与简历关键事实必须保留原文证据。",
            "评分正向结论必须引用候选人简历或检索片段。",
            "面试问题必须对齐 JD 能力、候选人项目和匹配缺口。",
            "最终报告只能总结面试回答、原始证据和评分轨迹中出现的信息。",
        ],
        stop_conditions=[
            "all_candidates_scored",
            "interview_materials_generated",
            "final_evaluation_report",
        ],
        steps=_default_steps(jd_profile),
    )


def create_agent_state(plan: AgentPlan) -> AgentState:
    first_step = plan.steps[0].step_id if plan.steps else None
    return AgentState(plan_id=plan.plan_id, status="planned", current_step_id=first_step)


def complete_step(
    state: AgentState,
    step_id: str,
    *,
    current_step_id: Optional[str] = None,
    tool_call_ids: Optional[list[str]] = None,
) -> None:
    if step_id not in state.completed_steps:
        state.completed_steps.append(step_id)
    if tool_call_ids:
        for call_id in tool_call_ids:
            if call_id not in state.tool_call_ids:
                state.tool_call_ids.append(call_id)
    state.current_step_id = current_step_id or step_id
    state.status = "running"
    state.updated_at = datetime.utcnow()


def complete_state(state: AgentState, final_step_id: str = "finalize_report") -> None:
    if final_step_id not in state.completed_steps:
        state.completed_steps.append(final_step_id)
    state.current_step_id = final_step_id
    state.status = "completed"
    state.updated_at = datetime.utcnow()


def _default_steps(jd_profile: JDProfile) -> list[AgentPlanStep]:
    job_title = jd_profile.job_title or "目标岗位"
    return [
        AgentPlanStep(
            step_id="extract_jd",
            title="解析 JD",
            tool_name="extract_jd",
            intent=f"将 {job_title} 的岗位要求抽取为可评分事实。",
        ),
        AgentPlanStep(
            step_id="extract_resumes",
            title="解析简历",
            tool_name="extract_resume",
            intent="将候选人简历抽取为结构化画像和证据事实。",
        ),
        AgentPlanStep(
            step_id="retrieve_evidence",
            title="检索证据",
            tool_name="retrieve_evidence",
            intent="围绕 JD 要求检索候选人简历中的相关片段。",
        ),
        AgentPlanStep(
            step_id="score_candidates",
            title="证据评分",
            tool_name="score_candidate",
            intent="用动态 rubric 和候选人证据生成匹配结论。",
        ),
        AgentPlanStep(
            step_id="generate_interview_materials",
            title="生成面试材料",
            tool_name="generate_interview_questions",
            intent="生成 10 道问题和 3-5 个候选追问。",
        ),
        AgentPlanStep(
            step_id="run_interview_session",
            title="运行模拟面试",
            tool_name="submit_interview_turn",
            intent="基于回答质量和证据一致性进行多轮追问。",
        ),
        AgentPlanStep(
            step_id="finalize_report",
            title="生成最终报告",
            tool_name="finalize_interview_report",
            intent="汇总匹配证据、回答质量、风险和后续建议。",
        ),
    ]
