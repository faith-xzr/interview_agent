from datetime import datetime

from app.interview_session import finalize_interview_session
from app.schemas import (
    CandidateProfile,
    CandidateReport,
    InterviewAnswerFollowUp,
    InterviewQuestion,
    InterviewSession,
    InterviewSessionQuestion,
    InterviewTurn,
    JDProfile,
    MatchReport,
    RunReport,
    ScoreBreakdown,
)


class FakeEvaluationLLM:
    available = True

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system_prompt: str, user_prompt: str, *, timeout: float = 30):
        self.calls.append((system_prompt, user_prompt))
        if "二次汇总" in system_prompt:
            return {
                "overallFeedback": "候选人能说明 RAG 召回评估，但缺少指标口径和失败案例。",
                "strengths": ["能解释 RAG 召回评估目标"],
                "improvements": ["补充召回率、延迟和失败兜底的量化证据"],
            }
        return {
            "overallScore": 78,
            "overallFeedback": "回答覆盖了 RAG 评估目标，但缺少线上指标。",
            "strengths": ["提到了召回评估和上线验收"],
            "improvements": ["缺少 P99 延迟、召回率和对照基线"],
            "questionEvaluations": [
                {
                    "questionIndex": 0,
                    "score": 78,
                    "feedback": "能说明项目职责，但指标口径不完整。",
                    "referenceAnswer": "应说明检索链路、召回率、延迟、基线对照和失败兜底。",
                    "keyPoints": ["检索链路", "量化指标", "失败兜底"],
                }
            ],
        }


def test_finalize_interview_session_uses_llm_two_stage_evaluation():
    llm = FakeEvaluationLLM()
    run = RunReport(
        run_id="run-1",
        created_at=datetime.utcnow(),
        jd_profile=JDProfile(
            job_title="AI Agent / RAG 应用工程师",
            responsibilities=["负责 Agent 编排和 RAG 质量评估"],
            required_skills=["RAG", "LLM", "Prompt Engineering"],
        ),
        candidates=[],
    )
    candidate = CandidateReport(
        candidate_id="candidate-1",
        source_name="resume.txt",
        profile=CandidateProfile(
            name="许哲瑞",
            projects=["客服 Agent 项目：负责 RAG 检索、工具调用和多轮追问。"],
            skills=["RAG", "Agent", "FastAPI"],
        ),
        match_report=MatchReport(
            total_score=82,
            decision="推荐面试",
            dimension_scores={"技能": 80},
            score_breakdown=ScoreBreakdown(skill_score=40),
            match_reasons=["简历包含 RAG 和 Agent 项目经验。"],
            gap_reasons=["缺少召回率、延迟和失败兜底的量化数据。"],
            interview_questions=[
                InterviewQuestion(
                    question="你如何评估 RAG 召回质量？",
                    focus="RAG 评估",
                    scoring_criteria="优秀回答应包含指标、基线和线上验证方式。",
                )
            ],
        ),
    )
    run.candidates.append(candidate)
    session = InterviewSession(
        session_id="session-1",
        run_id=run.run_id,
        candidate_id=candidate.candidate_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        turns=[
            InterviewTurn(
                turn_index=1,
                question=InterviewSessionQuestion(
                    question="你如何评估 RAG 召回质量？",
                    focus="RAG 评估",
                    scoring_criteria="优秀回答应包含指标、基线和线上验证方式。",
                    question_index=0,
                    stage="RAG",
                ),
                answer="我主要看召回评估和上线验收，整体效果还不错。",
                diagnosis=InterviewAnswerFollowUp(
                    question_index=0,
                    original_question="你如何评估 RAG 召回质量？",
                    candidate_answer="我主要看召回评估和上线验收，整体效果还不错。",
                    answer_summary="候选人提到召回评估但缺少指标。",
                    clarity_score=72,
                    depth_score=55,
                    evidence_consistency="weak",
                    issues=["缺少量化指标支撑"],
                    followup_question="请补充召回率和延迟指标。",
                    reason="指标不完整",
                    expected_signal="能说明指标口径、基线和验证方式。",
                ),
            )
        ],
    )

    completed = finalize_interview_session(
        session,
        llm=llm,
        run=run,
        candidate=candidate,
    )

    assert len(llm.calls) == 2
    assert "---问答记录开始---" in llm.calls[0][1]
    assert "你如何评估 RAG 召回质量？" in llm.calls[0][1]
    assert "许哲瑞" in llm.calls[0][1]
    assert completed.final_report is not None
    assert completed.final_report.overall_score == 78
    assert completed.final_report.summary == "候选人能说明 RAG 召回评估，但缺少指标口径和失败案例。"
    assert completed.final_report.strengths == ["能解释 RAG 召回评估目标"]
    assert completed.final_report.risks == ["补充召回率、延迟和失败兜底的量化证据"]
    assert completed.final_report.question_evaluations[0].score == 78
    assert completed.final_report.reference_answers[0].key_points == ["检索链路", "量化指标", "失败兜底"]


def test_finalize_interview_session_keeps_followup_turns_with_duplicate_question_indexes():
    class DuplicateIndexLLM(FakeEvaluationLLM):
        def complete_json(self, system_prompt: str, user_prompt: str, *, timeout: float = 30):
            self.calls.append((system_prompt, user_prompt))
            if "二次汇总" in system_prompt:
                return {
                    "overallFeedback": "两轮问答都已纳入评估。",
                    "strengths": ["能持续围绕同一项目补充信息"],
                    "improvements": ["继续补齐指标口径"],
                }
            return {
                "overallScore": 80,
                "overallFeedback": "两轮回答质量不同。",
                "strengths": ["能回答主问题"],
                "improvements": ["追问仍缺少指标"],
                "questionEvaluations": [
                    {
                        "questionIndex": 0,
                        "score": 70,
                        "feedback": "主问题回答偏概括。",
                        "referenceAnswer": "主问题参考答案",
                        "keyPoints": ["主问题"],
                    },
                    {
                        "questionIndex": 1,
                        "score": 90,
                        "feedback": "追问回答补充了更多细节。",
                        "referenceAnswer": "追问参考答案",
                        "keyPoints": ["追问"],
                    },
                ],
            }

    llm = DuplicateIndexLLM()
    run = RunReport(
        run_id="run-1",
        created_at=datetime.utcnow(),
        jd_profile=JDProfile(job_title="AI Agent 工程师"),
        candidates=[],
    )
    candidate = CandidateReport(
        candidate_id="candidate-1",
        source_name="resume.txt",
        profile=CandidateProfile(name="候选人", projects=["Agent 项目"]),
        match_report=MatchReport(
            total_score=75,
            decision="推荐面试",
            dimension_scores={},
            score_breakdown=ScoreBreakdown(),
            match_reasons=[],
            gap_reasons=[],
        ),
    )
    run.candidates.append(candidate)
    base_question = InterviewSessionQuestion(
        question="介绍你的 Agent 项目。",
        focus="项目经历",
        scoring_criteria="说明职责、实现和结果。",
        question_index=0,
        stage="PROJECT",
    )
    followup_question = InterviewSessionQuestion(
        question="请补充指标口径。",
        focus="动态追问",
        scoring_criteria="说明基线和验证方法。",
        question_index=0,
        stage="dynamic_followup",
    )
    session = InterviewSession(
        session_id="session-1",
        run_id=run.run_id,
        candidate_id=candidate.candidate_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        turns=[
            InterviewTurn(
                turn_index=1,
                question=base_question,
                answer="我负责 Agent 编排。",
                diagnosis=InterviewAnswerFollowUp(
                    question_index=0,
                    original_question=base_question.question,
                    candidate_answer="我负责 Agent 编排。",
                    answer_summary="回答偏概括。",
                    clarity_score=70,
                    depth_score=55,
                    evidence_consistency="weak",
                    issues=["缺少指标"],
                    followup_question=followup_question.question,
                    reason="需要追问",
                    expected_signal="指标口径",
                ),
            ),
            InterviewTurn(
                turn_index=2,
                question=followup_question,
                answer="我们对比上线前后召回率，人工抽检验证。",
                diagnosis=InterviewAnswerFollowUp(
                    question_index=0,
                    original_question=followup_question.question,
                    candidate_answer="我们对比上线前后召回率，人工抽检验证。",
                    answer_summary="补充了验证方式。",
                    clarity_score=85,
                    depth_score=80,
                    evidence_consistency="consistent",
                    issues=[],
                    followup_needed=False,
                    followup_question="",
                    reason="已补充",
                    expected_signal="指标口径",
                ),
            ),
        ],
    )

    completed = finalize_interview_session(session, llm=llm, run=run, candidate=candidate)

    assert completed.final_report is not None
    assert [item.question_index for item in completed.final_report.question_evaluations] == [0, 1]
    assert [item.score for item in completed.final_report.question_evaluations] == [70, 90]
    assert completed.final_report.question_evaluations[1].question == "请补充指标口径。"
    assert completed.final_report.reference_answers[1].reference_answer == "追问参考答案"
