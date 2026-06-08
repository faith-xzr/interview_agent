from app.extraction.llm_jd_extractor import PROMPT_PATH, extract_jd_with_llm


class CapturingLLM:
    available = True

    def __init__(self, payload):
        self.payload = payload
        self.system_prompt = ""
        self.user_prompt = ""

    def complete_json(self, system_prompt: str, user_prompt: str):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.payload


def test_llm_jd_extractor_uses_top_level_job_title_for_profile():
    jd_text = """
岗位名称：高级推荐系统后端工程师
职责：负责推荐平台 API 建设和推荐链路稳定性优化。
要求：熟悉 Python、FastAPI、Kafka 和 Flink。
"""
    llm = CapturingLLM(
        {
            "job_title": "高级推荐系统后端工程师",
            "key_points": [
                {
                    "topic": "核心职责",
                    "summary": "负责推荐平台 API 建设和推荐链路稳定性优化",
                    "evidence": "负责推荐平台 API 建设和推荐链路稳定性优化",
                    "importance": "high",
                    "category": "responsibility",
                },
                {
                    "topic": "必备技能",
                    "summary": "熟悉 Python、FastAPI、Kafka 和 Flink",
                    "evidence": "熟悉 Python、FastAPI、Kafka 和 Flink",
                    "importance": "high",
                    "category": "skill",
                },
            ],
        }
    )

    result = extract_jd_with_llm(llm, jd_text)

    assert result is not None
    profile, facts = result
    assert PROMPT_PATH.exists()
    assert '"job_title"' in llm.user_prompt
    assert "岗位名称" in llm.user_prompt
    assert profile.job_title == "高级推荐系统后端工程师"
    assert any(fact.value == "负责推荐平台 API 建设和推荐链路稳定性优化" for fact in facts)


def test_llm_jd_extractor_ignores_hallucinated_job_title_and_uses_raw_jd_title():
    jd_text = "AIGC 内容运营，要求熟练运用 ChatGPT 和 Midjourney，并沉淀 AI 内容 SOP。"
    llm = CapturingLLM(
        {
            "job_title": "区块链架构师",
            "key_points": [
                {
                    "topic": "必备技能",
                    "summary": "要求熟练运用 ChatGPT 和 Midjourney",
                    "evidence": "要求熟练运用 ChatGPT 和 Midjourney",
                    "importance": "high",
                    "category": "skill",
                },
                {
                    "topic": "核心职责",
                    "summary": "沉淀 AI 内容 SOP",
                    "evidence": "沉淀 AI 内容 SOP",
                    "importance": "high",
                    "category": "responsibility",
                },
            ],
        }
    )

    result = extract_jd_with_llm(llm, jd_text)

    assert result is not None
    profile, _ = result
    assert profile.job_title == "AIGC 内容运营"
