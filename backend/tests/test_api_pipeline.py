import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


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
    assert report["candidates"][0]["match_report"]["decision"] == "推荐推进"
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
