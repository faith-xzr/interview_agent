import asyncio
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
import time

from fastapi.testclient import TestClient
import httpx

from app.config import Settings
from app.main import create_app
from app.pipeline import RecruitingPipeline
from app.schemas import FollowUpQuestion, InterviewQuestion, JDProfile, MatchReport, RunReport, ScoreBreakdown
from app.storage import RunStorage


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


def _resume_quality_payload(overall_score: int = 84):
    return {
        "overallScore": overall_score,
        "scoreDetail": {
            "projectScore": 36,
            "skillMatchScore": 18,
            "contentScore": 13,
            "structureScore": 9,
            "expressionScore": 8,
        },
        "summary": "项目表达较完整，具备可验证成果。",
        "strengths": ["项目证据较清晰"],
        "suggestions": [
            {
                "category": "内容",
                "priority": "中",
                "issue": "部分指标口径仍可补充",
                "recommendation": "补充统一可复核的结果指标。",
            }
        ],
    }


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


def test_resume_score_endpoint_rejects_empty_input(tmp_path):
    client = make_client(tmp_path)

    response = client.post("/api/resume-score")

    assert response.status_code == 400
    assert response.json()["detail"] == "未提供简历内容，请上传简历或粘贴简历文本。"


def _poll_resume_status(client: object, resume_id: int) -> dict:
    last_payload = {}
    for _ in range(60):
        response = client.get(f"/api/resumes/{resume_id}/detail")
        assert response.status_code == 200
        payload = response.json()
        last_payload = payload
        if payload["analyze_status"] == "COMPLETED":
            return payload
        time.sleep(0.05)
    raise AssertionError(f"简历分析未在预期时间内完成: {last_payload}")


def test_resume_upload_uploads_and_exports_analysis_chain(tmp_path):
    client = make_client(tmp_path)
    files = {
        "file": (
            "resume_for_chain.txt",
            (
                "李四\n"
                "5年 Python 后端开发经验，负责电商推荐链路。\n"
                "项目：将检索链路从 2s 降到 1.2s，支持百万级请求。\n"
            ),
            "text/plain",
        )
    }

    upload_response = client.post("/api/resumes/upload", files=files)
    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    assert upload_payload["duplicate"] is False
    resume_id = upload_payload["resume"]["id"]

    detail_payload = _poll_resume_status(client, resume_id)
    assert detail_payload["id"] == resume_id
    assert detail_payload["analyze_status"] == "COMPLETED"
    assert detail_payload["analyses"], "应至少有一条分析记录"

    export_response = client.get(f"/api/resumes/{resume_id}/export")
    assert export_response.status_code == 200
    export_payload = export_response.json()
    assert export_payload["resume_id"] == resume_id
    assert export_payload["report"]["overall_score"] == detail_payload["analyses"][0]["overall_score"]

    reanalyze_response = client.post(f"/api/resumes/{resume_id}/reanalyze")
    assert reanalyze_response.status_code == 200
    assert reanalyze_response.json()["status"] == "submitted"

    list_payload = client.get("/api/resumes").json()
    assert list_payload and list_payload[0]["id"] == resume_id
    assert list_payload[0]["analyze_status"] in {"PENDING", "PROCESSING", "COMPLETED"}


def test_resume_upload_duplicate_reuses_existing_analysis_and_increments_access_count(tmp_path):
    client = make_client(tmp_path)
    files = {
        "file": (
            "resume_for_chain_dup.txt",
            (
                "王五\n"
                "3年 Java 后端开发经验，负责订单系统。\n"
                "项目：提升下单成功率 15%，优化异步重试策略。\n"
            ),
            "text/plain",
        )
    }

    first_response = client.post("/api/resumes/upload", files=files)
    assert first_response.status_code == 200
    resume_id = first_response.json()["resume"]["id"]
    _poll_resume_status(client, resume_id)

    list_before = client.get("/api/resumes").json()
    assert len(list_before) == 1
    assert list_before[0]["id"] == resume_id
    assert list_before[0]["access_count"] == 1

    second_response = client.post("/api/resumes/upload", files=files)
    assert second_response.status_code == 200
    duplicate_payload = second_response.json()
    assert duplicate_payload["duplicate"] is True
    assert duplicate_payload["resume"]["id"] == resume_id
    assert duplicate_payload["analysis"] is not None

    list_after = client.get("/api/resumes").json()
    assert len(list_after) == 1
    assert list_after[0]["access_count"] == 2


def test_resume_score_endpoint_scores_single_resume_without_jd(tmp_path):
    client = make_client(tmp_path)
    resume_text = (
        "赵晓\n"
        "目标：高级后端开发工程师\n"
        "项目经历\n"
        "• 基于 FastAPI 与 Redis 重构风控服务，响应时延从 1.8s 降至 0.7s。\n"
        "• 使用 Kafka 落地异步任务链路，支持 20w QPS 峰值压测。\n"
        "技能\n"
        "Python, FastAPI, SQL, Redis, Kafka"
    )

    response = client.post(
        "/api/resume-score",
        data={
            "resume_text": resume_text
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_score"] >= 0
    assert "score_detail" in payload
    assert payload["score_detail"]["project_score"] > 0
    assert payload["score_detail"]["skill_match_score"] > 0
    assert payload["score_detail"]["content_score"] > 0
    assert payload["original_text"] == resume_text
    assert "summary" in payload
    assert "strengths" in payload and isinstance(payload["strengths"], list)
    assert "suggestions" in payload and isinstance(payload["suggestions"], list)


def test_create_run_persists_report_once(tmp_path, monkeypatch):
    save_calls = []
    original_save_run = RunStorage.save_run

    def spy_save_run(self, report):
        save_calls.append(report.run_id)
        return original_save_run(self, report)

    monkeypatch.setattr(RunStorage, "save_run", spy_save_run)
    client = make_client(tmp_path)

    response = client.post(
        "/api/runs",
        data={
            "jd_text": "Python 后端工程师，负责 FastAPI 服务建设。",
            "resume_texts": "王五\n5年 Python 后端经验，做过 FastAPI 服务。",
        },
    )

    assert response.status_code == 200
    assert save_calls == [response.json()["run_id"]]


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


def test_interview_session_runs_turns_and_final_report(tmp_path):
    client = make_client(tmp_path)
    run_response = client.post(
        "/api/runs",
        data={
            "jd_text": "AI 产品经理，负责 Agent 应用落地，要求 RAG 评估、需求拆解和跨团队推进经验。",
            "resume_texts": "小周\n项目经历：企业级智能助手项目，负责 RAG 召回评估、需求拆解和上线验收。",
        },
    )
    run_report = run_response.json()
    candidate_id = run_report["candidates"][0]["candidate_id"]

    start_response = client.post(
        f"/api/runs/{run_report['run_id']}/interviews",
        json={"candidate_id": candidate_id},
    )

    assert start_response.status_code == 200
    session = start_response.json()
    assert session["run_id"] == run_report["run_id"]
    assert session["candidate_id"] == candidate_id
    assert session["status"] == "active"
    assert session["current_question"]["question"]
    assert session["turns"] == []

    turn_response = client.post(
        f"/api/interviews/{session['session_id']}/turns",
        json={"candidate_answer": "我参与了 RAG 召回评估，主要看召回率和上线验收，整体效果还不错。"},
    )

    assert turn_response.status_code == 200
    updated = turn_response.json()
    assert len(updated["turns"]) == 1
    assert updated["turns"][0]["diagnosis"]["followup_question"]
    assert updated["turns"][0]["diagnosis"]["clarity_score"] < 100
    assert updated["current_question"]["question"]

    persisted_response = client.get(f"/api/interviews/{session['session_id']}")

    assert persisted_response.status_code == 200
    assert len(persisted_response.json()["turns"]) == 1

    report_response = client.post(f"/api/interviews/{session['session_id']}/final-report")

    assert report_response.status_code == 200
    completed = report_response.json()
    assert completed["status"] == "completed"
    assert completed["final_report"]["overall_score"] >= 0
    assert completed["final_report"]["recommendation"]
    assert completed["final_report"]["summary"]


def test_run_and_interview_records_are_listed_and_deletable(tmp_path):
    client = make_client(tmp_path)
    run_response = client.post(
        "/api/runs",
        data={
            "jd_text": "Python 后端工程师，负责 FastAPI 服务建设。",
            "resume_texts": "王五\n5年 Python 后端经验，做过 FastAPI 服务。",
        },
    )
    assert run_response.status_code == 200
    run_report = run_response.json()
    candidate_id = run_report["candidates"][0]["candidate_id"]

    runs_response = client.get("/api/runs")

    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload[0]["run_id"] == run_report["run_id"]
    assert runs_payload[0]["jd_profile"]["job_title"]

    start_response = client.post(
        f"/api/runs/{run_report['run_id']}/interviews",
        json={
            "candidate_id": candidate_id,
            "mode": "text:Python 后端开发:mid:friendly_hr",
        },
    )
    assert start_response.status_code == 200
    session = start_response.json()
    assert session["direction"] == "Python 后端开发"
    assert session["difficulty"] == "mid"
    assert session["interviewer_style"] == "friendly_hr"
    assert session["skill_id"] == "python-backend"
    assert session["flow"][:3] == ["Python 基础", "数据库", "Django/Flask"]
    assert session["current_question"]["skill_id"] == "python-backend"
    assert session["current_question"]["source"] == "skill_planned"

    sessions_response = client.get("/api/interviews")

    assert sessions_response.status_code == 200
    sessions_payload = sessions_response.json()
    assert sessions_payload[0]["session_id"] == session["session_id"]
    assert sessions_payload[0]["mode"] == "text:Python 后端开发:mid:friendly_hr"

    run_sessions_response = client.get(f"/api/interviews?run_id={run_report['run_id']}")

    assert run_sessions_response.status_code == 200
    assert [item["session_id"] for item in run_sessions_response.json()] == [session["session_id"]]

    delete_response = client.delete(f"/api/interviews/{session['session_id']}")

    assert delete_response.status_code == 204
    assert client.get(f"/api/interviews/{session['session_id']}").status_code == 404
    assert client.get("/api/interviews").json() == []


def test_skill_route_endpoint_uses_existing_jd_group_for_interview_skill(tmp_path):
    client = make_client(tmp_path)
    jd_text = (
        "职位二：AI 业务探索\n"
        "核心使命：深入业务，用 AI（Prompt/Agent/工作流）识别并重塑重复性工作。\n"
        "工作内容：快速搭建 AI Agent 或自动化脚本，验证 AI 能干到什么程度。\n"
        "任职要求：有搭建 Agent 或编写复杂 Prompt 的实战经验，能与业务和技术同频对话。"
    )

    run_response = client.post(
        "/api/runs",
        data={
            "jd_text": jd_text,
            "resume_texts": "小黄\n做过 AI Agent 原型和 Prompt 工作流自动化。",
        },
    )
    assert run_response.status_code == 200
    run_report = run_response.json()

    route_response = client.get(f"/api/runs/{run_report['run_id']}/skill-route")

    assert route_response.status_code == 200
    route = route_response.json()
    assert route["position_name"] == "AI 业务探索"
    assert route["skill_id"] == "ai-agent-dev"
    assert route["skill_name"] == "AI Agent 开发"
    assert route["route_result"] == "AI 业务探索 / AI Agent 开发"
    assert route["confidence"] > 0
    assert route["reason"]

    start_response = client.post(
        f"/api/runs/{run_report['run_id']}/interviews",
        json={
            "candidate_id": run_report["candidates"][0]["candidate_id"],
            "mode": "text::mid:friendly_hr",
            "skill_id": route["skill_id"],
        },
    )

    assert start_response.status_code == 200
    session = start_response.json()
    assert session["direction"] == "AI Agent 开发"
    assert session["skill_id"] == "ai-agent-dev"
    assert session["current_question"]["skill_id"] == "ai-agent-dev"


def test_runs_with_same_jd_are_merged_into_one_group(tmp_path):
    client = make_client(tmp_path)

    first = client.post(
        "/api/runs",
        data={
            "jd_text": "Python 后端工程师，负责 FastAPI 和 SQL。",
            "resume_texts": ["王五\n5年 Python 后端经验，做过 FastAPI 服务。"],
        },
    )
    assert first.status_code == 200
    first_report = first.json()

    second = client.post(
        "/api/runs",
        data={
            "jd_text": "Python 后端工程师，负责 FastAPI 和 SQL。",
            "resume_texts": ["赵六\n3年 Python 后端经验。"],
        },
    )
    assert second.status_code == 200
    second_report = second.json()
    assert second_report["run_id"] == first_report["run_id"]

    runs_payload = client.get("/api/runs").json()
    assert len(runs_payload) == 1
    merged = runs_payload[0]
    assert merged["run_id"] == first_report["run_id"]
    candidate_ids = {candidate["candidate_id"] for candidate in merged["candidates"]}
    assert candidate_ids == {"candidate-1", "candidate-2"}


def test_delete_single_resume_from_run(tmp_path):
    client = make_client(tmp_path)

    response = client.post(
        "/api/runs",
        data={
            "jd_text": "Python 后端工程师，负责 FastAPI 和 SQL。",
            "resume_texts": [
                "王五\n5年 Python 后端经验，做过 FastAPI 服务。",
                "赵六\n3年 Python 后端经验，参与过系统迭代。",
            ],
        },
    )
    assert response.status_code == 200
    report = response.json()
    run_id = report["run_id"]
    victim_id = report["candidates"][0]["candidate_id"]

    delete_response = client.delete(f"/api/runs/{run_id}/candidates/{victim_id}")
    assert delete_response.status_code == 200
    updated = delete_response.json()
    assert updated["run_id"] == run_id
    assert victim_id not in {item["candidate_id"] for item in updated["candidates"]}
    assert len(updated["candidates"]) == 1

    runs_payload = client.get("/api/runs").json()
    assert len(runs_payload) == 1
    assert runs_payload[0]["run_id"] == run_id
    assert victim_id not in {item["candidate_id"] for item in runs_payload[0]["candidates"]}


def test_delete_last_resume_removes_run_and_interview_history(tmp_path):
    client = make_client(tmp_path)

    create_response = client.post(
        "/api/runs",
        data={
            "jd_text": "Python 后端工程师，负责 FastAPI 和 SQL。",
            "resume_texts": [
                "王五\n5年 Python 后端经验，做过 FastAPI 服务。",
            ],
        },
    )
    assert create_response.status_code == 200
    report = create_response.json()
    run_id = report["run_id"]
    candidate_id = report["candidates"][0]["candidate_id"]

    session_response = client.post(
        f"/api/runs/{run_id}/interviews",
        json={"candidate_id": candidate_id, "mode": "text:Python 后端开发:mid:friendly_hr"},
    )
    assert session_response.status_code == 200
    assert client.get("/api/interviews").json() != []

    delete_response = client.delete(f"/api/runs/{run_id}/candidates/{candidate_id}")
    assert delete_response.status_code == 204

    assert client.get("/api/runs").json() == []
    assert client.get("/api/interviews").json() == []


def test_delete_all_runs_clears_runs_and_interviews(tmp_path):
    client = make_client(tmp_path)

    first = client.post(
        "/api/runs",
        data={
            "jd_text": "Python 后端工程师，负责 FastAPI 和 SQL。",
            "resume_texts": ["王五\n5年 Python 后端经验，做过 FastAPI 服务。"],
        },
    )
    assert first.status_code == 200
    first_report = first.json()

    second = client.post(
        "/api/runs",
        data={
            "jd_text": "产品运营岗位，负责增长与留存。",
            "resume_texts": ["赵六\n3年运营经验，负责增长策略优化。"],
        },
    )
    assert second.status_code == 200
    second_report = second.json()

    first_session = client.post(
        f"/api/runs/{first_report['run_id']}/interviews",
        json={"candidate_id": first_report['candidates'][0]['candidate_id']},
    )
    assert first_session.status_code == 200

    second_session = client.post(
        f"/api/runs/{second_report['run_id']}/interviews",
        json={"candidate_id": second_report['candidates'][0]['candidate_id']},
    )
    assert second_session.status_code == 200

    assert len(client.get("/api/interviews").json()) == 2

    delete_response = client.delete("/api/runs")
    assert delete_response.status_code == 204
    assert client.get("/api/runs").json() == []
    assert client.get("/api/interviews").json() == []


def test_delete_all_runs_is_idempotent(tmp_path):
    client = make_client(tmp_path)

    first = client.delete("/api/runs")
    assert first.status_code == 204

    second = client.delete("/api/runs")
    assert second.status_code == 204

    assert client.get("/api/runs").json() == []
    assert client.get("/api/interviews").json() == []


def test_model_provider_settings_can_be_read_and_switched(tmp_path):
    client = make_client(tmp_path)

    settings_response = client.get("/api/settings/model-providers")

    assert settings_response.status_code == 200
    payload = settings_response.json()
    assert payload["default_provider_id"] == "openai-compatible"
    assert [provider["id"] for provider in payload["providers"]] == [
        "dashscope",
        "deepseek",
        "kimi",
        "glm",
        "openai-compatible",
    ]
    assert "local" not in [provider["id"] for provider in payload["providers"]]
    openai_provider = next(provider for provider in payload["providers"] if provider["id"] == "openai-compatible")
    assert openai_provider["is_default"] is True
    assert openai_provider["api_key_configured"] is False

    switch_response = client.put(
        "/api/settings/model-providers/default",
        json={"provider_id": "dashscope"},
    )

    assert switch_response.status_code == 200
    switched = switch_response.json()
    assert switched["default_provider_id"] == "dashscope"
    assert next(provider for provider in switched["providers"] if provider["id"] == "dashscope")["is_default"] is True

    health_response = client.get("/api/health")

    assert health_response.status_code == 200
    assert health_response.json()["model_provider"] == "dashscope"
    assert health_response.json()["llm_model"] == "qwen3.5-flash"


def test_deepseek_legacy_llm_env_maps_to_deepseek_provider(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "demo.sqlite3",
        vector_dir=tmp_path / "vectors",
        llm_api_key="secret",
        llm_base_url="https://api.deepseek.com/v1",
        llm_model="deepseek-v4-flash",
    )
    client = TestClient(create_app(settings))

    settings_response = client.get("/api/settings/model-providers")

    assert settings_response.status_code == 200
    payload = settings_response.json()
    assert payload["default_provider_id"] == "deepseek"
    deepseek_provider = next(provider for provider in payload["providers"] if provider["id"] == "deepseek")
    openai_provider = next(provider for provider in payload["providers"] if provider["id"] == "openai-compatible")
    assert deepseek_provider["model"] == "deepseek-v4-flash"
    assert deepseek_provider["api_key_configured"] is True
    assert openai_provider["base_url"] == "https://api.openai.com/v1"
    assert openai_provider["api_key_configured"] is False
    assert client.get("/api/health").json()["model_provider"] == "deepseek"


def test_legacy_openai_default_setting_migrates_to_known_deepseek_provider(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "demo.sqlite3",
        vector_dir=tmp_path / "vectors",
        llm_api_key="secret",
        llm_base_url="https://api.deepseek.com/v1",
        llm_model="deepseek-v4-flash",
    )
    RunStorage(settings.database_path).set_setting("default_model_provider_id", "openai-compatible")

    client = TestClient(create_app(settings))

    payload = client.get("/api/settings/model-providers").json()
    assert payload["default_provider_id"] == "deepseek"
    assert client.get("/api/health").json()["model_provider"] == "deepseek"
    assert RunStorage(settings.database_path).get_setting("default_model_provider_id") == "deepseek"


def test_model_provider_api_key_can_be_saved_from_settings_page(tmp_path):
    client = make_client(tmp_path)

    save_response = client.put(
        "/api/settings/model-providers/deepseek/api-key",
        json={"api_key": "sk-direct-deepseek"},
    )

    assert save_response.status_code == 200
    saved = save_response.json()
    deepseek_provider = next(provider for provider in saved["providers"] if provider["id"] == "deepseek")
    assert deepseek_provider["api_key_configured"] is True
    assert deepseek_provider["api_key_source"] == "saved"

    switch_response = client.put(
        "/api/settings/model-providers/default",
        json={"provider_id": "deepseek"},
    )

    assert switch_response.status_code == 200
    assert client.get("/api/health").json()["llm_enabled"] is True
    stored_key = RunStorage(tmp_path / "demo.sqlite3").get_setting("model_provider_api_key:deepseek")
    assert stored_key == "sk-direct-deepseek"


def test_model_provider_api_key_rejects_blank_or_unknown_provider(tmp_path):
    client = make_client(tmp_path)

    blank_response = client.put(
        "/api/settings/model-providers/deepseek/api-key",
        json={"api_key": "   "},
    )
    missing_response = client.put(
        "/api/settings/model-providers/missing/api-key",
        json={"api_key": "sk-any"},
    )

    assert blank_response.status_code == 400
    assert "API Key" in blank_response.json()["detail"]
    assert missing_response.status_code == 400
    assert "未知模型服务" in missing_response.json()["detail"]


def test_model_provider_switch_rejects_unknown_provider(tmp_path):
    client = make_client(tmp_path)

    response = client.put(
        "/api/settings/model-providers/default",
        json={"provider_id": "missing"},
    )

    assert response.status_code == 400
    assert "未知模型服务" in response.json()["detail"]


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

    def slow_run(self, jd_text, resumes, initial_warnings=None):
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
            _resume_quality_payload(),
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
                        "reason": "简历未明确覆盖 ChatGPT 使用经验",
                        "evidence_indexes": [],
                    },
                    {
                        "requirement": "能直接使用 Midjourney 产出视觉素材",
                        "status": "强匹配",
                        "confidence": 0.95,
                        "reason": "项目经历直接说明使用 Midjourney 产出视觉素材",
                        "evidence_indexes": [0],
                    },
                    {
                        "requirement": "能使用 Runway 等 AI 工具辅助文案",
                        "status": "相关匹配",
                        "confidence": 0.8,
                        "reason": "简历展示 Runway 辅助短视频脚本经验",
                        "evidence_indexes": [0],
                    },
                    {
                        "requirement": "能沉淀 AI 内容 SOP",
                        "status": "未匹配",
                        "confidence": 0,
                        "reason": "简历未出现 SOP 沉淀证据",
                        "evidence_indexes": [],
                    },
                    {
                        "requirement": "有成功自媒体案例或 KOL 经历",
                        "status": "直接匹配",
                        "confidence": 0.9,
                        "reason": "简历有 KOL 合作案例证据",
                        "evidence_indexes": [1],
                    },
                ]
            },
        ]
    )

    report = pipeline.run(jd_text, [("小林.txt", resume_text)])

    candidate = report.candidates[0]
    assert candidate.resume_quality is not None
    assert candidate.resume_quality.overall_score == 84
    assert candidate.match_report.total_score == 42
    assert candidate.match_report.dimension_scores["AIGC工具生态"] == 26
    assert any(
        item.dimension == "内容生产方法" and item.requirement == "能沉淀 AI 内容 SOP"
        for item in candidate.match_report.requirement_matches
    )
    stored = pipeline.get_run(report.run_id)
    assert stored.candidates[0].match_report.dimension_scores["平台与案例"] == 16


def test_pipeline_stores_hashes_model_and_prompt_versions(tmp_path):
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
    jd_text = "Python 后端工程师，负责 FastAPI 和 RAG。"
    resume_text = "小王\n项目经历\n• FastAPI RAG 检索系统。"

    report = pipeline.run(jd_text, [("小王.txt", resume_text)])

    assert report.metadata.jd_text_hash == hashlib.sha256(jd_text.encode("utf-8")).hexdigest()
    assert report.metadata.llm_model == "demo-offline"
    assert report.metadata.scoring_policy_version == "backend_score_policy@v1"
    assert "requirement_matching" in report.metadata.prompt_versions
    candidate = report.candidates[0]
    assert candidate.resume_text_hash == hashlib.sha256(resume_text.encode("utf-8")).hexdigest()
    stored = pipeline.get_run(report.run_id)
    assert stored.metadata.jd_text_hash == report.metadata.jd_text_hash
    assert stored.candidates[0].resume_text_hash == candidate.resume_text_hash


def test_pipeline_logs_and_audits_llm_matching_fallback(tmp_path, caplog, monkeypatch):
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
    pipeline.llm = QueueLLM(
        [
            {
                "key_points": [
                    {
                        "topic": "核心职责",
                        "summary": "有 RAG / Agent 系统落地经验",
                        "evidence": "有 RAG / Agent 系统落地经验",
                        "importance": "high",
                        "category": "responsibility",
                    }
                ]
            },
            {
                "profile": {
                    "name": "候选人",
                    "projects": ["RAG 项目"],
                    "skills": ["RAG"],
                },
                "facts": [
                    {
                        "label": "项目经验",
                        "category": "project",
                        "summary": "RAG 项目",
                        "evidence": "• RAG 项目",
                        "section": "projects",
                        "importance": "high",
                    }
                ],
            },
            _resume_quality_payload(),
            {
                "rubric": [
                    {
                        "dimension": "项目深度",
                        "requirement": "有 RAG / Agent 系统落地经验",
                        "requirement_type": "project_depth",
                        "max_score": 100,
                        "priority": "must_have",
                    }
                ]
            },
            {
                "matches": [
                    {
                        "requirement": "有 RAG / Agent 系统落地经验",
                        "status": "强匹配",
                        "confidence": 0.9,
                        "reason": "模型声称强匹配，但没有引用证据",
                        "evidence_indexes": [],
                    }
                ]
            },
        ]
    )

    def low_fallback(*args, **kwargs):
        return MatchReport(
            total_score=39,
            decision="",
            dimension_scores={},
            score_breakdown=ScoreBreakdown(),
            match_reasons=["fallback"],
            gap_reasons=["fallback"],
        )

    monkeypatch.setattr("app.pipeline.score_candidate", low_fallback)
    caplog.set_level(logging.WARNING)

    report = pipeline.run(
        "Agent 工程师，需要有 RAG / Agent 系统落地经验。",
        [("小王.txt", "小王\n项目经历\n• RAG 项目")],
    )

    assert "scoring.llm_matching_invalid" in caplog.text
    assert "missing_evidence_for_positive_match" in caplog.text
    assert report.audit_events
    event = report.audit_events[0]
    assert event.event == "scoring.llm_matching_invalid"
    assert event.failure_code == "missing_evidence_for_positive_match"
    assert event.fallback_strategy == "local_rule_scorer"
    assert report.candidates[0].match_report.total_score == 39


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
    source_bytes = resume_path.read_bytes()

    response = client.post(
        "/api/runs",
        data={
            "jd_text": "海外内容运营，熟悉 TikTok Shop、AI 视频营销、跨境电商和数据分析。",
        },
        files={"resume_files": (resume_path.name, source_bytes, "application/pdf")},
    )

    assert response.status_code == 200
    report = response.json()
    candidate = report["candidates"][0]
    assert candidate["profile"]["name"] == "小黄"
    assert candidate["source_name"] == resume_path.name
    assert candidate["source_file"] == {
        "filename": resume_path.name,
        "content_type": "application/pdf",
    }

    source_response = client.get(
        f"/api/runs/{report['run_id']}/candidates/{candidate['candidate_id']}/source-file"
    )
    assert source_response.status_code == 200
    assert source_response.content == source_bytes
    assert source_response.headers["content-type"].startswith("application/pdf")
