from datetime import datetime

from app.agent.planner import build_recruiting_agent_plan, create_agent_state
from app.config import Settings
from app.interview_session import create_interview_session
from app.pipeline import RecruitingPipeline
from app.schemas import (
    CandidateProfile,
    CandidateReport,
    InterviewQuestion,
    JDProfile,
    MatchReport,
    RunReport,
    ScoreBreakdown,
)
from app.skills import SkillRepository, select_skill_for_direction, select_skills_for_jd


def test_interview_direction_labels_resolve_to_local_skills():
    repository = SkillRepository.default()

    expected = {
        "AI Agent 开发": "ai-agent-dev",
        "算法与数据结构": "algorithm",
        "前端工程": "frontend",
        "Java 后端开发": "java-backend",
        "Python 后端开发": "python-backend",
        "系统设计": "system-design",
        "自定义 JD": "custom-jd",
    }

    for direction, skill_id in expected.items():
        skill = select_skill_for_direction(direction, repository)
        assert skill.id == skill_id
        assert skill.categories
        assert skill.question_focuses


def test_skill_repository_loads_default_skills_and_matches_agent_jd():
    repository = SkillRepository.default()

    skills = repository.list_skills()
    skill_ids = {skill.id for skill in skills}
    assert "generic-interview" in skill_ids
    assert "ai-agent-engineer" in skill_ids
    assert "ai-agent-dev" in skill_ids
    assert "java-backend" in skill_ids

    agent_skill = repository.get("ai-agent-engineer")
    assert agent_skill.name == "AI Agent 工程师"
    assert any(category.key == "rag" for category in agent_skill.categories)
    assert any("Agent" in focus for focus in agent_skill.question_focuses)

    jd = JDProfile(
        job_title="AI Agent 工程师",
        responsibilities=["负责 RAG、Memory、Tool Calling 和评测体系建设"],
        required_skills=["Python", "RAG", "Agent", "Memory"],
    )

    selected = select_skills_for_jd(jd, repository)

    assert [skill.id for skill in selected] == ["ai-agent-engineer"]


def test_interview_session_uses_direction_skill_flow():
    repository = SkillRepository.default()
    jd = JDProfile(
        job_title="Java 后端开发",
        responsibilities=["负责订单服务、缓存治理和 MySQL 性能优化"],
        required_skills=["Java", "Spring", "MySQL", "Redis"],
    )
    candidate = CandidateReport(
        candidate_id="candidate-1",
        source_name="resume.txt",
        profile=CandidateProfile(name="张三", skills=["Java", "Spring Boot", "MySQL"]),
        match_report=MatchReport(
            total_score=82,
            decision="建议面试",
            dimension_scores={},
            score_breakdown=ScoreBreakdown(),
            match_reasons=[],
            gap_reasons=[],
            interview_questions=[
                InterviewQuestion(
                    question="请介绍一个你主导过的 Java 后端项目。",
                    focus="项目经历",
                    scoring_criteria="说明个人职责、技术方案、指标结果和复盘。",
                )
            ],
        ),
    )
    run = RunReport(run_id="run-1", created_at=datetime.utcnow(), jd_profile=jd, candidates=[candidate])

    session = create_interview_session(
        run,
        candidate,
        "text:Java 后端开发:senior:strict_manager",
        repository,
    )

    assert session.direction == "Java 后端开发"
    assert session.difficulty == "senior"
    assert session.interviewer_style == "strict_manager"
    assert session.skill_id == "java-backend"
    assert session.flow[:3] == ["Java", "MySQL", "Redis"]
    assert session.current_question is not None
    assert session.current_question.skill_id == "java-backend"
    assert session.current_question.stage == "JAVA"
    assert session.current_question.source == "skill_planned"
    assert session.current_question.focus.startswith("Java · ")
    assert "方向要求" in session.current_question.scoring_criteria


def test_agent_plan_and_state_describe_end_to_end_flow():
    skill = SkillRepository.default().get("ai-agent-engineer")
    jd = JDProfile(
        job_title="AI Agent 工程师",
        responsibilities=["负责从 JD 到模拟面试报告的招聘智能体闭环"],
        required_skills=["Python", "RAG", "Agent"],
    )

    plan = build_recruiting_agent_plan(jd, [skill])
    state = create_agent_state(plan)

    assert plan.objective == "连接 JD/简历解析、证据评分、面试追问和最终评估报告。"
    assert plan.strategy == "code_driven_orchestration_with_llm_specialists"
    assert plan.selected_skill_ids == ["ai-agent-engineer"]
    assert [step.step_id for step in plan.steps] == [
        "extract_jd",
        "extract_resumes",
        "retrieve_evidence",
        "score_candidates",
        "generate_interview_materials",
        "run_interview_session",
        "finalize_report",
    ]
    assert "final_evaluation_report" in plan.stop_conditions
    assert state.plan_id == plan.plan_id
    assert state.status == "planned"
    assert state.current_step_id == "extract_jd"


def test_pipeline_records_plan_state_and_tool_calls(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "demo.sqlite3",
        vector_dir=tmp_path / "vectors",
        llm_api_key=None,
        llm_base_url=None,
        llm_model="demo-offline",
        enable_chroma=False,
    )
    pipeline = RecruitingPipeline(settings)

    report = pipeline.run(
        "AI Agent 工程师，负责 RAG、Memory、Tool Calling 和评测体系建设。",
        [
            (
                "agent_resume.txt",
                "李雷\n5年 Python 后端经验。项目：Agent 面试系统，负责 RAG 检索、Memory 管理和 Tool Calling。",
            )
        ],
    )

    assert report.agent_plan is not None
    assert report.agent_plan.selected_skill_ids == ["ai-agent-engineer"]
    assert report.agent_state.status == "completed"
    assert report.agent_state.current_step_id == "finalize_report"
    assert "generate_interview_materials" in report.agent_state.completed_steps

    tool_names = [tool.tool_name for tool in report.tool_calls]
    assert tool_names[:3] == ["extract_jd", "extract_resume", "retrieve_evidence"]
    assert "score_candidate" in tool_names
    assert "generate_interview_questions" in tool_names
    assert all(tool.status == "success" for tool in report.tool_calls)
    assert all(tool.duration_ms >= 0 for tool in report.tool_calls)
    assert all(tool.run_id == report.run_id for tool in report.tool_calls)

    persisted = pipeline.get_run(report.run_id)
    assert persisted.agent_plan.selected_skill_ids == ["ai-agent-engineer"]
    assert len(persisted.tool_calls) == len(report.tool_calls)
