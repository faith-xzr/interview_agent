from app.extraction.llm_resume_extractor import PROMPT_PATH, extract_resume_with_llm


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


def test_llm_resume_extractor_uses_external_prompt_and_returns_supported_chinese_profile():
    resume_text = """
小梁
求职意向：全栈开发工程师
教育背景
某理工大学 计算机科学与技术 本科 3.7/4.0
实习经历
头部互联网平台｜后端开发实习生
• 参与招聘智能体后台接口与数据处理，负责 FastAPI 服务、SQL 查询和接口联调。
专业技能
FastAPI、SQL、React
"""
    llm = CapturingLLM(
        {
            "profile": {
                "name": "候选人",
                "education": ["某理工大学计算机科学与技术本科，GPA 3.7/4.0。"],
                "work_experiences": [
                    "头部互联网平台后端开发实习生：参与招聘智能体后台接口与数据处理，负责 FastAPI 服务、SQL 查询和接口联调。"
                ],
                "skills": ["FastAPI", "SQL", "React"],
                "highlights": ["参与招聘智能体后台接口与数据处理。"],
            },
            "facts": [
                {
                    "label": "学历背景",
                    "category": "education_summary",
                    "summary": "某理工大学计算机科学与技术本科，GPA 3.7/4.0。",
                    "evidence": "某理工大学 计算机科学与技术 本科 3.7/4.0",
                    "section": "education",
                    "importance": "medium",
                },
                {
                    "label": "实习/工作经验",
                    "category": "work_summary",
                    "summary": "头部互联网平台后端开发实习生：参与招聘智能体后台接口与数据处理，负责 FastAPI 服务、SQL 查询和接口联调。",
                    "evidence": "头部互联网平台｜后端开发实习生\n• 参与招聘智能体后台接口与数据处理，负责 FastAPI 服务、SQL 查询和接口联调。",
                    "section": "experience",
                    "importance": "high",
                },
                {
                    "label": "专业技能",
                    "category": "skill",
                    "summary": "FastAPI",
                    "evidence": "FastAPI、SQL、React",
                    "section": "skills",
                    "importance": "medium",
                },
            ],
        }
    )

    result = extract_resume_with_llm(llm, resume_text, "小梁.txt")

    assert result is not None
    profile, facts = result
    assert PROMPT_PATH.exists()
    assert "简历关键能力抽取" in llm.user_prompt
    assert "不要输出 domain_evidence" in llm.user_prompt
    assert "相邻行表达同一段职责、项目或亮点时，必须合并成一条完整短句" in llm.user_prompt
    assert "{{RESUME_TEXT}}" not in llm.user_prompt
    assert profile.education == ["某理工大学计算机科学与技术本科，GPA 3.7/4.0。"]
    assert profile.work_experiences == [
        "头部互联网平台后端开发实习生：参与招聘智能体后台接口与数据处理，负责 FastAPI 服务、SQL 查询和接口联调。"
    ]
    assert profile.contacts == {}
    assert not profile.location
    assert all(fact.section != "basic" for fact in facts)
    assert any(fact.fact_type == "education_summary" and fact.value.startswith("某理工大学") for fact in facts)
    assert any(fact.fact_type == "work_summary" and "后端开发实习生" in fact.value for fact in facts)
    assert all(fact.extractor == "llm_resume" for fact in facts)


def test_llm_resume_extractor_rejects_hallucinated_profile_values_and_facts():
    resume_text = "专业技能\nPython、SQL"
    llm = CapturingLLM(
        {
            "profile": {
                "skills": ["Python", "Kubernetes"],
                "projects": ["从零搭建 Kubernetes 集群。"],
            },
            "facts": [
                {
                    "label": "专业技能",
                    "category": "skill",
                    "summary": "Kubernetes",
                    "evidence": "熟悉 Kubernetes 集群调优",
                    "section": "skills",
                    "importance": "high",
                }
            ],
        }
    )

    result = extract_resume_with_llm(llm, resume_text, "resume.txt")

    assert result is not None
    profile, facts = result
    assert profile.skills == ["Python"]
    assert profile.projects == []
    assert facts == []
