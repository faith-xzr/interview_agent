import asyncio
import json
from datetime import datetime
from pathlib import Path
import time

from fastapi.testclient import TestClient
import httpx

from app.config import Settings
from app.main import create_app
from app.pipeline import RecruitingPipeline
from app.schemas import FollowUpQuestion, InterviewQuestion, JDProfile, MatchReport, RunReport, ScoreBreakdown


def make_client(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "demo.sqlite3",
        vector_dir=tmp_path / "vectors",
        llm_api_key=None,
        llm_base_url=None,
        llm_model="demo-offline",
    )
    return TestClient(create_app(settings))


class QueueLLM:
    available = True

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def complete_json(self, system_prompt: str, user_prompt: str):
        self.calls.append((system_prompt, user_prompt))
        return self.payloads.pop(0)


def test_run_pipeline_without_llm_returns_ranked_report_and_export(tmp_path):
    client = make_client(tmp_path)

    response = client.post(
        "/api/runs",
        data={
            "jd_text": "高级 Python 后端工程师，5年以上经验，负责 FastAPI、RAG、SQL、React 平台建设。",
            "resume_texts": [
                "王五\n电话 13812345678\n邮箱 wangwu@example.com\n7年 Python 后端经验。项目：RAG 检索平台，使用 FastAPI、SQL 和 React。",
                "赵六\n2年客服经验，熟悉 Excel，参与客户满意度运营项目。",
            ],
        },
    )

    assert response.status_code == 200
    report = response.json()
    assert report["run_id"]
    assert any(
        fact["fact_type"] == "required_skill" and fact["value"] == "Python"
        for fact in report["jd_extraction_facts"]
    )
    assert any(
        fact["fact_type"] == "years_required" and fact["value"] == "5"
        for fact in report["jd_extraction_facts"]
    )
    assert any(
        fact["fact_type"] == "responsibility" and "FastAPI" in fact["evidence"]
        for fact in report["jd_extraction_facts"]
    )
    assert len(report["candidates"]) == 2
    assert report["candidates"][0]["match_report"]["total_score"] >= report["candidates"][1]["match_report"]["total_score"]
    assert report["candidates"][0]["match_report"]["decision"] == ""
    assert report["candidates"][1]["match_report"]["decision"] == ""
    assert len(report["candidates"][0]["match_report"]["interview_questions"]) >= 10
    assert 3 <= len(report["candidates"][0]["match_report"]["followup_questions"]) <= 5

    export_response = client.get(f"/api/runs/{report['run_id']}/export")

    assert export_response.status_code == 200
    assert export_response.headers["content-type"].startswith("application/json")
    assert json.loads(export_response.content)["run_id"] == report["run_id"]


def test_run_pipeline_rejects_empty_resume_input(tmp_path):
    client = make_client(tmp_path)

    response = client.post("/api/runs", data={"jd_text": "Python 工程师"})

    assert response.status_code == 400
    assert "至少需要一份有效简历内容" in response.json()["detail"]


def test_answer_followup_generates_question_from_candidate_answer(tmp_path):
    client = make_client(tmp_path)
    run_response = client.post(
        "/api/runs",
        data={
            "jd_text": "高级 Python 后端工程师，5年以上经验，负责 FastAPI、RAG、SQL 平台建设。",
            "resume_texts": "王五\n7年 Python 后端经验。项目：RAG 检索平台，使用 FastAPI 和 SQL。",
        },
    )
    run_report = run_response.json()
    candidate_id = run_report["candidates"][0]["candidate_id"]

    response = client.post(
        f"/api/runs/{run_report['run_id']}/answer-followup",
        json={
            "candidate_id": candidate_id,
            "question_index": 0,
            "candidate_answer": "我做过 RAG 系统，主要用了 FastAPI，整体效果还可以。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["followup_needed"] is True
    assert payload["followup_question"]
    assert "具体" in payload["followup_question"] or "个人" in payload["followup_question"]
    assert payload["clarity_score"] < 70
    assert any("量化" in issue or "个人" in issue for issue in payload["issues"])


def test_health_responds_while_run_pipeline_is_processing(tmp_path, monkeypatch):
    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "demo.sqlite3",
        vector_dir=tmp_path / "vectors",
        llm_api_key=None,
        llm_base_url=None,
        llm_model="demo-offline",
        enable_chroma=False,
    )

    def slow_run(self, jd_text, resumes):
        time.sleep(0.8)
        return RunReport(
            run_id="slow-run",
            created_at=datetime.utcnow(),
            jd_profile=JDProfile(job_title="Python 工程师"),
            candidates=[],
        )

    monkeypatch.setattr(RecruitingPipeline, "run", slow_run)
    app = create_app(settings)

    async def exercise():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            started = time.perf_counter()
            run_task = asyncio.create_task(
                client.post(
                    "/api/runs",
                    data={
                        "jd_text": "Python 工程师",
                        "resume_texts": "候选人，Python 经验。",
                    },
                )
            )
            await asyncio.sleep(0.05)

            health_response = await client.get("/api/health")
            elapsed = time.perf_counter() - started

            assert health_response.status_code == 200
            assert elapsed < 0.35
            run_response = await run_task
            assert run_response.status_code == 200

    asyncio.run(exercise())


def test_run_pipeline_returns_extraction_facts_for_sectioned_resume(tmp_path):
    client = make_client(tmp_path)
    resume_text = """
小陈
求职意向：高级翻译（AI 辅助）
教育经历
某外国语大学  翻译硕士 (MTI)  硕士
工作经历
AI 独角兽企业  |  提示词工程师 (Prompt Engineer)
• 负责大模型翻译场景的 Prompt 调优，通过思维链 (CoT) 设计，将复杂长难句的翻译准确率提升 25%。
专业技能
Prompt Engineering | AI 译后编辑 (MTPE)
"""

    response = client.post(
        "/api/runs",
        data={
            "jd_text": "高级翻译，负责 AI 辅助翻译、Prompt Engineering 和 MTPE 流程优化。",
            "resume_texts": [resume_text],
        },
    )

    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["profile"]["target_role"] == "高级翻译（AI 辅助）"
    assert "Prompt Engineering" in candidate["profile"]["skills"]
    assert any(
        fact["fact_type"] == "metric" and fact["value"] == "25%" and "Prompt 调优" in fact["evidence"]
        for fact in candidate["extraction_facts"]
    )


def test_run_pipeline_preserves_decorated_resume_sections(tmp_path):
    client = make_client(tmp_path)
    resume_text = """
小周
求职意向：AI产品经理 / Agent 应用架构师
【个人评价】
• 精通 Agent 编排与 RAG 链路设计，曾主导企业级智能助手落地。
【教育背景】
• 某重点理工类大学（985）| 计算机科学与技术 | 本科
【项目经验】
• 企业级智能助手项目：负责 RAG 召回评估和上线验收。
【专业技能】
Python | SQL | RAG | Agent 编排
"""

    response = client.post(
        "/api/runs",
        data={
            "jd_text": "AI产品经理，负责 Agent 应用、RAG 链路设计和项目落地。",
            "resume_texts": [resume_text],
        },
    )

    assert response.status_code == 200
    facts = response.json()["candidates"][0]["extraction_facts"]
    assert any(fact["section"] == "summary" for fact in facts)
    assert any(fact["section"] == "projects" for fact in facts)
    assert any(fact["section"] == "skills" and fact["value"] == "Agent 编排" for fact in facts)


def test_pipeline_uses_llm_end_to_end_for_jd_and_resume(tmp_path):
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
    jd_text = "AI产品经理，负责 Agent 应用落地，要求 Agent 编排经验。"
    resume_text = """
小周
【教育背景】
• 某重点理工类大学（985）| 计算机科学与技术 | 本科
【项目经验】
• 企业级智能助手项目：负责 RAG 召回评估和上线验收。
【专业技能】
Agent 编排 | RAG
"""
    pipeline.llm = QueueLLM(
        [
            {
                "key_points": [
                    {
                        "topic": "必备技能",
                        "summary": "需要具备 Agent 编排能力",
                        "evidence": "要求 Agent 编排经验",
                        "importance": "high",
                        "category": "skill",
                    },
                    {
                        "topic": "核心职责",
                        "summary": "负责 Agent 应用在业务场景的落地推进",
                        "evidence": "负责 Agent 应用落地",
                        "importance": "high",
                        "category": "responsibility",
                    },
                ],
            },
            {
                "profile": {
                    "name": "候选人",
                    "education": ["某重点理工类大学计算机科学与技术本科。"],
                    "work_experiences": ["企业级智能助手项目成员：负责 RAG 召回评估和上线验收。"],
                    "projects": ["企业级智能助手项目：负责 RAG 召回评估和上线验收。"],
                    "skills": ["Agent 编排"],
                },
                "facts": [
                    {
                        "category": "education_summary",
                        "label": "学历背景",
                        "summary": "某重点理工类大学计算机科学与技术本科。",
                        "evidence": "• 某重点理工类大学（985）| 计算机科学与技术 | 本科",
                        "section": "education",
                        "importance": "medium",
                    },
                    {
                        "category": "work_summary",
                        "label": "实习/工作经验",
                        "summary": "企业级智能助手项目成员：负责 RAG 召回评估和上线验收。",
                        "evidence": "• 企业级智能助手项目：负责 RAG 召回评估和上线验收。",
                        "section": "projects",
                        "importance": "high",
                    }
                ],
            },
        ]
    )

    report = pipeline.run(jd_text, [("小周.txt", resume_text)])

    assert any(fact.extractor == "llm_end_to_end" for fact in report.jd_extraction_facts)
    candidate = report.candidates[0]
    assert candidate.profile.name == "小周"
    assert candidate.profile.education == ["某重点理工类大学计算机科学与技术本科。"]
    assert candidate.profile.work_experiences == ["企业级智能助手项目成员：负责 RAG 召回评估和上线验收。"]
    assert any(fact.extractor == "llm_resume" for fact in candidate.extraction_facts)


def test_pipeline_uses_llm_dynamic_match_scoring_when_available(tmp_path):
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
    jd_text = (
        "AIGC 内容运营，要求熟练运用 ChatGPT，能直接使用 Midjourney 产出视觉素材，"
        "能使用 Runway 等 AI 工具辅助文案，并沉淀 AI 内容 SOP；有成功自媒体案例或 KOL 经历优先。"
    )
    resume_text = """
小林
项目经历
• 使用 Midjourney 产出视觉素材，用 Runway 辅助短视频脚本。
• 参与 KOL 合作案例复盘。
专业技能
Midjourney | Runway
"""
    pipeline.llm = QueueLLM(
        [
            {
                "key_points": [
                    {
                        "topic": "必备技能",
                        "summary": "熟练运用 ChatGPT",
                        "evidence": "熟练运用 ChatGPT",
                        "importance": "high",
                        "category": "skill",
                    },
                    {
                        "topic": "必备技能",
                        "summary": "能直接使用 Midjourney 产出视觉素材",
                        "evidence": "能直接使用 Midjourney 产出视觉素材",
                        "importance": "high",
                        "category": "skill",
                    },
                    {
                        "topic": "必备技能",
                        "summary": "能使用 Runway 等 AI 工具辅助文案",
                        "evidence": "能使用 Runway 等 AI 工具辅助文案",
                        "importance": "high",
                        "category": "skill",
                    },
                    {
                        "topic": "核心职责",
                        "summary": "能沉淀 AI 内容 SOP",
                        "evidence": "沉淀 AI 内容 SOP",
                        "importance": "high",
                        "category": "responsibility",
                    },
                    {
                        "topic": "加分项",
                        "summary": "有成功自媒体案例或 KOL 经历",
                        "evidence": "有成功自媒体案例或 KOL 经历优先",
                        "importance": "low",
                        "category": "nice_to_have_skill",
                    },
                ],
            },
            {
                "profile": {
                    "name": "候选人",
                    "projects": ["使用 Midjourney 产出视觉素材，用 Runway 辅助短视频脚本。", "参与 KOL 合作案例复盘。"],
                    "skills": ["Midjourney", "Runway"],
                },
                "facts": [
                    {
                        "label": "项目经验",
                        "category": "project",
                        "summary": "使用 Midjourney 产出视觉素材，用 Runway 辅助短视频脚本。",
                        "evidence": "• 使用 Midjourney 产出视觉素材，用 Runway 辅助短视频脚本。",
                        "section": "projects",
                        "importance": "high",
                    },
                    {
                        "label": "项目经验",
                        "category": "project",
                        "summary": "参与 KOL 合作案例复盘。",
                        "evidence": "• 参与 KOL 合作案例复盘。",
                        "section": "projects",
                        "importance": "medium",
                    },
                ],
            },
            {
                "rubric": [
                    {
                        "dimension": "AIGC工具生态",
                        "requirement": "熟练运用 ChatGPT",
                        "requirement_type": "core_skill",
                        "max_score": 20,
                        "priority": "must_have",
                    },
                    {
                        "dimension": "AIGC工具生态",
                        "requirement": "能直接使用 Midjourney 产出视觉素材",
                        "requirement_type": "core_skill",
                        "max_score": 20,
                        "priority": "must_have",
                    },
                    {
                        "dimension": "AIGC工具生态",
                        "requirement": "能使用 Runway 等 AI 工具辅助文案",
                        "requirement_type": "core_skill",
                        "max_score": 15,
                        "priority": "must_have",
                    },
                    {
                        "dimension": "内容生产方法",
                        "requirement": "能沉淀 AI 内容 SOP",
                        "requirement_type": "responsibility",
                        "max_score": 25,
                        "priority": "must_have",
                    },
                    {
                        "dimension": "平台与案例",
                        "requirement": "有成功自媒体案例或 KOL 经历",
                        "requirement_type": "project_depth",
                        "max_score": 20,
                        "priority": "nice_to_have",
                    },
                ]
            },
            {
                "matches": [
                    {
                        "requirement": "熟练运用 ChatGPT",
                        "status": "未匹配",
                        "confidence": 0,
                        "contribution": 0,
                        "reason": "简历未明确覆盖 ChatGPT 使用经验",
                        "evidence_indexes": [],
                    },
                    {
                        "requirement": "能直接使用 Midjourney 产出视觉素材",
                        "status": "强匹配",
                        "confidence": 0.95,
                        "contribution": 19,
                        "reason": "项目经历直接说明使用 Midjourney 产出视觉素材",
                        "evidence_indexes": [0],
                    },
                    {
                        "requirement": "能使用 Runway 等 AI 工具辅助文案",
                        "status": "相关匹配",
                        "confidence": 0.8,
                        "contribution": 9,
                        "reason": "简历展示 Runway 辅助短视频脚本经验",
                        "evidence_indexes": [0],
                    },
                    {
                        "requirement": "能沉淀 AI 内容 SOP",
                        "status": "未匹配",
                        "confidence": 0,
                        "contribution": 0,
                        "reason": "简历未出现 SOP 沉淀证据",
                        "evidence_indexes": [],
                    },
                    {
                        "requirement": "有成功自媒体案例或 KOL 经历",
                        "status": "直接匹配",
                        "confidence": 0.9,
                        "contribution": 16,
                        "reason": "简历有 KOL 合作案例证据",
                        "evidence_indexes": [1],
                    },
                ]
            },
        ]
    )

    report = pipeline.run(jd_text, [("小林.txt", resume_text)])

    candidate = report.candidates[0]
    assert candidate.match_report.total_score == 44
    assert candidate.match_report.dimension_scores["AIGC工具生态"] == 28
    assert any(
        item.dimension == "内容生产方法" and item.requirement == "能沉淀 AI 内容 SOP"
        for item in candidate.match_report.requirement_matches
    )
    stored = pipeline.get_run(report.run_id)
    assert stored.candidates[0].match_report.dimension_scores["平台与案例"] == 16


def test_pipeline_skips_question_materials_when_match_score_is_below_40(tmp_path, monkeypatch):
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
    generation_calls = []

    def low_match(*args, **kwargs):
        return MatchReport(
            total_score=39,
            decision="",
            dimension_scores={},
            score_breakdown=ScoreBreakdown(),
            match_reasons=["匹配分低于面试生成阈值"],
            gap_reasons=["核心技能未覆盖"],
        )

    def generate_questions(*args, **kwargs):
        generation_calls.append("questions")
        return [
            InterviewQuestion(
                question="不应生成的问题",
                focus="低分候选人",
                scoring_criteria="不应进入面试题生成环节。",
            )
        ]

    def generate_static_followups(*args, **kwargs):
        generation_calls.append("followups")
        return [
            FollowUpQuestion(
                question="不应生成的追问",
                reason="低分候选人不需要追问生成。",
            )
        ]

    monkeypatch.setattr("app.pipeline.score_candidate_with_llm", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.pipeline.score_candidate", low_match)
    monkeypatch.setattr("app.pipeline.generate_interview_questions", generate_questions)
    monkeypatch.setattr("app.pipeline.generate_followups", generate_static_followups)

    report = pipeline.run("高级 Python 后端工程师，负责 FastAPI 平台建设。", [("weak.txt", "候选人\n客服经验。")])

    match_report = report.candidates[0].match_report
    assert match_report.total_score == 39
    assert match_report.interview_questions == []
    assert match_report.followup_questions == []
    assert generation_calls == []


def test_pipeline_generates_question_materials_at_score_40(tmp_path, monkeypatch):
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

    def threshold_match(*args, **kwargs):
        return MatchReport(
            total_score=40,
            decision="",
            dimension_scores={},
            score_breakdown=ScoreBreakdown(),
            match_reasons=["刚好达到面试生成阈值"],
            gap_reasons=["仍需面试确认"],
        )

    monkeypatch.setattr("app.pipeline.score_candidate_with_llm", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.pipeline.score_candidate", threshold_match)
    monkeypatch.setattr(
        "app.pipeline.generate_interview_questions",
        lambda *args, **kwargs: [
            InterviewQuestion(
                question="达到阈值后生成的问题",
                focus="边界分数",
                scoring_criteria="40 分应进入面试题生成环节。",
            )
        ],
    )
    monkeypatch.setattr(
        "app.pipeline.generate_followups",
        lambda *args, **kwargs: [
            FollowUpQuestion(
                question="达到阈值后生成的追问",
                reason="40 分应进入追问生成环节。",
            )
        ],
    )

    report = pipeline.run("高级 Python 后端工程师，负责 FastAPI 平台建设。", [("threshold.txt", "候选人\nPython 经验。")])

    match_report = report.candidates[0].match_report
    assert match_report.total_score == 40
    assert [item.question for item in match_report.interview_questions] == ["达到阈值后生成的问题"]
    assert [item.question for item in match_report.followup_questions] == ["达到阈值后生成的追问"]


def test_pipeline_uses_llm_question_generation_after_matching(tmp_path):
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
    jd_text = "高级推荐系统后端工程师，负责 FastAPI 推荐平台建设，要求 Kafka、Flink 和推荐链路优化经验。"
    resume_text = """
小周
项目经历
• 低延迟推荐项目：负责召回链路优化，使用 Kafka、Flink 和 Python，推荐链路延迟降低 30%。
专业技能
Python | Kafka | Flink
"""
    llm_questions = [
        {
            "question": f"模型生成面试题 {index + 1}",
            "focus": f"模型生成考察点 {index + 1}",
            "scoring_criteria": f"模型生成评分标准 {index + 1}",
            "category": "hr" if index == 9 else "technical_business",
            "basis": "resume" if index < 6 else ("general" if index == 9 else "jd"),
        }
        for index in range(10)
    ]
    pipeline.llm = QueueLLM(
        [
            {
                "key_points": [
                    {
                        "topic": "必备技能",
                        "summary": "要求 Kafka、Flink 和推荐链路优化经验",
                        "evidence": "要求 Kafka、Flink 和推荐链路优化经验",
                        "importance": "high",
                        "category": "skill",
                    },
                    {
                        "topic": "核心职责",
                        "summary": "负责 FastAPI 推荐平台建设",
                        "evidence": "负责 FastAPI 推荐平台建设",
                        "importance": "high",
                        "category": "responsibility",
                    },
                ],
            },
            {
                "profile": {
                    "name": "候选人",
                    "projects": ["低延迟推荐项目：负责召回链路优化，使用 Kafka、Flink 和 Python。"],
                    "skills": ["Python", "Kafka", "Flink"],
                    "highlights": ["推荐链路延迟降低 30%"],
                },
                "facts": [
                    {
                        "label": "项目经验",
                        "category": "project",
                        "summary": "低延迟推荐项目：负责召回链路优化，使用 Kafka、Flink 和 Python。",
                        "evidence": "• 低延迟推荐项目：负责召回链路优化，使用 Kafka、Flink 和 Python，推荐链路延迟降低 30%。",
                        "section": "projects",
                        "importance": "high",
                    }
                ],
            },
            {
                "rubric": [
                    {
                        "dimension": "推荐工程",
                        "requirement": "要求 Kafka、Flink 和推荐链路优化经验",
                        "requirement_type": "core_skill",
                        "max_score": 60,
                        "priority": "must_have",
                    },
                    {
                        "dimension": "后端平台",
                        "requirement": "负责 FastAPI 推荐平台建设",
                        "requirement_type": "responsibility",
                        "max_score": 40,
                        "priority": "must_have",
                    },
                ]
            },
            {
                "matches": [
                    {
                        "requirement": "要求 Kafka、Flink 和推荐链路优化经验",
                        "status": "强匹配",
                        "confidence": 0.95,
                        "contribution": 58,
                        "reason": "简历项目直接覆盖 Kafka、Flink 和推荐链路优化",
                        "evidence_indexes": [0],
                    },
                    {
                        "requirement": "负责 FastAPI 推荐平台建设",
                        "status": "相关匹配",
                        "confidence": 0.7,
                        "contribution": 24,
                        "reason": "简历有 Python 后端经验，但 FastAPI 证据较弱",
                        "evidence_indexes": [0],
                    },
                ]
            },
            {"questions": llm_questions},
        ]
    )

    report = pipeline.run(jd_text, [("小周.txt", resume_text)])

    questions = report.candidates[0].match_report.interview_questions
    assert [item.question for item in questions] == [f"模型生成面试题 {index + 1}" for index in range(10)]
    assert all(set(item.model_dump().keys()) == {"question", "focus", "scoring_criteria"} for item in questions)
    assert len(pipeline.llm.calls) == 5
    assert "低延迟推荐项目" in pipeline.llm.calls[-1][1]
    assert "高级推荐系统后端工程师" in pipeline.llm.calls[-1][1]


def test_pipeline_keeps_rule_facts_when_llm_resume_returns_partial_facts(tmp_path):
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
    jd_text = "后端开发工程师，要求 Java、Spring Boot、MySQL 和 Docker。"
    resume_text = """
小文
教育背景
某理工类重点大学（985/211）| 计算机科学与技术 | 本科 | 2022.09-2026.06
实习经历
某互联网大厂 | 后端开发实习生 | 2024.06-2024.09
• 负责高并发秒杀系统的接口优化，通过引入 Redis 缓存与消息队列削峰，使系统 QPS 承载能力提升 3 倍。
专业技能
Java/Go 后端开发、Spring Boot/Django 框架、MySQL/PostgreSQL 数据库、Docker/K8s 容器化部署与 CI/CD
"""
    pipeline.llm = QueueLLM(
        [
            {
                "key_points": [
                    {
                        "topic": "必备技能",
                        "summary": "要求 Java、Spring Boot、MySQL 和 Docker",
                        "evidence": "要求 Java、Spring Boot、MySQL 和 Docker",
                        "importance": "high",
                        "category": "skill",
                    }
                ],
            },
            {
                "profile": {
                    "name": "候选人",
                    "skills": [
                        "Java/Go 后端开发",
                        "Spring Boot/Django 框架",
                        "MySQL/PostgreSQL 数据库",
                        "Docker/K8s 容器化部署与 CI/CD",
                    ],
                },
                "facts": [
                    {
                        "label": "专业技能",
                        "category": "skill",
                        "summary": "熟练掌握 Java/Go 后端开发、Spring Boot/Django 框架、MySQL/PostgreSQL 数据库、Docker/K8s 容器化部署与 CI/CD",
                        "evidence": "Java/Go 后端开发、Spring Boot/Django 框架、MySQL/PostgreSQL 数据库、Docker/K8s 容器化部署与 CI/CD",
                        "section": "skills",
                        "importance": "high",
                    }
                ],
            },
        ]
    )

    report = pipeline.run(jd_text, [("小文.txt", resume_text)])

    candidate = report.candidates[0]
    assert candidate.profile.education
    assert candidate.profile.work_experiences
    assert any(fact.extractor == "llm_resume" and fact.section == "skills" for fact in candidate.extraction_facts)
    assert any(fact.section == "education" for fact in candidate.extraction_facts)
    assert any(fact.section == "experience" for fact in candidate.extraction_facts)


def test_run_pipeline_accepts_jd_text_with_resume_file_only(tmp_path):
    client = make_client(tmp_path)
    resume_path = Path("samples/resumes/小黄_深度实战版_.pdf")

    with resume_path.open("rb") as resume_file:
        response = client.post(
            "/api/runs",
            data={
                "jd_text": "海外内容运营，熟悉 TikTok Shop、AI 视频营销、跨境电商和数据分析。",
            },
            files={"resume_files": (resume_path.name, resume_file, "application/pdf")},
        )

    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["profile"]["name"] == "小黄"
    assert candidate["source_name"] == resume_path.name
