import json
from pathlib import Path
from typing import Any, Iterable, List, Optional

from app.schemas import CandidateProfile, ExtractedFact, InterviewQuestion, JDProfile, MatchReport


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "question_generation" / "interview_questions.md"
SYSTEM_PROMPT = "你是招聘面试题生成助手。只输出 JSON，不要输出解释文本。"

TECHNICAL_CATEGORY = "technical_business"
HR_CATEGORY = "hr"
RESUME_BASIS = "resume"


def generate_interview_questions(
    jd: JDProfile,
    candidate: CandidateProfile,
    match: MatchReport,
    llm: Any = None,
    jd_text: str = "",
    resume_text: str = "",
    extraction_facts: Optional[Iterable[ExtractedFact]] = None,
) -> List[InterviewQuestion]:
    llm_questions = _generate_with_llm(llm, jd, candidate, match, jd_text, resume_text, extraction_facts or [])
    if llm_questions is not None:
        return llm_questions
    return _generate_with_rules(jd, candidate, match)


def _generate_with_llm(
    llm: Any,
    jd: JDProfile,
    candidate: CandidateProfile,
    match: MatchReport,
    jd_text: str,
    resume_text: str,
    extraction_facts: Iterable[ExtractedFact],
) -> Optional[List[InterviewQuestion]]:
    if not getattr(llm, "available", False):
        return None
    try:
        payload = llm.complete_json(
            SYSTEM_PROMPT,
            _build_user_prompt(jd, candidate, match, jd_text, resume_text, list(extraction_facts)),
        )
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return _parse_llm_questions(payload.get("questions"))


def _build_user_prompt(
    jd: JDProfile,
    candidate: CandidateProfile,
    match: MatchReport,
    jd_text: str,
    resume_text: str,
    extraction_facts: List[ExtractedFact],
) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    context = {
        "jd_profile": jd.model_dump(mode="json"),
        "jd_text": _trim_text(jd_text, 4000),
        "candidate_profile": candidate.model_dump(mode="json"),
        "resume_text": _trim_text(resume_text, 6000),
        "resume_facts": [
            {
                "fact_type": fact.fact_type,
                "value": fact.value,
                "section": fact.section,
                "evidence": fact.evidence,
                "confidence": fact.confidence,
            }
            for fact in extraction_facts[:30]
        ],
        "match_context": {
            "total_score": match.total_score,
            "match_reasons": match.match_reasons,
            "gap_reasons": match.gap_reasons,
            "requirement_matches": [
                {
                    "dimension": item.dimension,
                    "requirement": item.requirement,
                    "status": item.status,
                    "reason": item.reason,
                }
                for item in match.requirement_matches[:20]
            ],
            "dimension_explanations": [
                item.model_dump(mode="json") for item in match.dimension_explanations[:10]
            ],
        },
        "generation_policy": {
            "total_questions": 10,
            "technical_business_questions": "8-9",
            "hr_questions": "1-2",
            "resume_centered_technical_business_questions": "6-7",
            "public_output_fields": ["question", "focus", "scoring_criteria"],
        },
    }
    return template.replace("{{QUESTION_CONTEXT_JSON}}", json.dumps(context, ensure_ascii=False, indent=2))


def _parse_llm_questions(raw_questions: Any) -> Optional[List[InterviewQuestion]]:
    if not isinstance(raw_questions, list) or len(raw_questions) != 10:
        return None

    parsed: List[InterviewQuestion] = []
    technical_count = 0
    hr_count = 0
    resume_centered_count = 0
    seen_questions: set[str] = set()

    for raw in raw_questions:
        if not isinstance(raw, dict):
            return None
        question = _clean_text(raw.get("question"))
        focus = _clean_text(raw.get("focus"))
        scoring_criteria = _clean_text(raw.get("scoring_criteria"))
        category = _normalize_category(raw.get("category"))
        basis = _normalize_basis(raw.get("basis"))
        if not question or not focus or not scoring_criteria:
            return None
        question_key = question.lower()
        if question_key in seen_questions:
            return None
        seen_questions.add(question_key)

        if category == TECHNICAL_CATEGORY:
            technical_count += 1
            if basis == RESUME_BASIS:
                resume_centered_count += 1
        elif category == HR_CATEGORY:
            hr_count += 1
        else:
            return None

        parsed.append(
            InterviewQuestion(
                question=question,
                focus=focus,
                scoring_criteria=scoring_criteria,
            )
        )

    if technical_count not in {8, 9}:
        return None
    if hr_count not in {1, 2}:
        return None
    if resume_centered_count not in {6, 7}:
        return None
    return parsed


def _generate_with_rules(jd: JDProfile, candidate: CandidateProfile, match: MatchReport) -> List[InterviewQuestion]:
    technical_questions: List[InterviewQuestion] = []

    for skill in _unique_texts(candidate.skills + jd.required_skills)[:4]:
        technical_questions.append(
            _question(
                f"请结合你最近的项目，说明你如何使用 {skill} 解决一个真实业务问题？",
                f"{skill} 的实际应用深度",
                "优秀回答应包含业务背景、个人职责、关键实现、权衡取舍和量化结果。",
            )
        )

    for project in candidate.projects[:2]:
        technical_questions.append(
            _question(
                f"请完整复盘这个项目：{project}。你个人负责哪一部分，最终结果如何衡量？",
                "项目真实性、个人贡献和结果指标",
                "重点看候选人是否能讲清目标、架构、难点、协作边界和可验证结果。",
            )
        )

    for highlight in candidate.highlights[:1]:
        technical_questions.append(
            _question(
                f"简历中提到“{highlight}”，请说明它对应的真实场景、你的贡献和可验证结果。",
                "简历亮点的真实性和深度",
                "优秀回答应给出背景、行动、个人贡献、指标和复盘。",
            )
        )

    scenario_title = jd.job_title or "该岗位"
    gap = match.gap_reasons[0] if match.gap_reasons else "当前 JD 的核心职责"
    jd_questions = [
        _question(
            f"如果入职后需要在两周内交付一个 {scenario_title} 相关的最小可用方案，你会如何拆解计划？",
            "业务拆解和交付节奏",
            "应能说明目标澄清、优先级、风险识别、里程碑和验收口径。",
        ),
        _question(
            f"针对“{gap}”这个待确认点，你会如何证明自己可以胜任？",
            "匹配缺口澄清",
            "优秀回答应结合过往经历、补充证据、学习计划和落地路径。",
        ),
        _question(
            "请描述一次你排查线上问题或复杂故障的经历，你如何定位根因并防止复发？",
            "问题定位和工程稳定性",
            "关注定位路径、数据证据、临时止血、长期修复和复盘机制。",
        ),
        _question(
            "当业务方提出的需求和技术实现成本冲突时，你通常如何沟通并推动决策？",
            "跨团队沟通和业务判断",
            "优秀回答应体现约束澄清、方案对比、影响评估和共同决策。",
        ),
        _question(
            "请举例说明你如何评估一个技术方案是否值得上线。",
            "技术判断和风险意识",
            "应覆盖收益、成本、风险、监控、回滚和后续维护。",
        ),
        _question(
            "你认为这个岗位最容易失败的风险是什么？你会如何提前规避？",
            "岗位理解和风险预判",
            "优秀回答应能结合 JD 的职责、约束和候选人自身经验提出具体措施。",
        ),
    ]
    for item in jd_questions:
        if len(technical_questions) >= 9:
            break
        technical_questions.append(item)

    while len(technical_questions) < 9:
        technical_questions.append(
            _question(
                "请用一个具体案例说明你的能力如何迁移到当前 JD 的核心职责。",
                "能力迁移和岗位适配",
                "优秀回答应包含相似场景、可迁移能力、差异风险和落地验证方式。",
            )
        )

    hr_questions = [
        _question(
            "你为什么考虑这个岗位，最希望在下一份工作里获得什么成长？",
            "求职动机与岗位稳定性",
            "优秀回答应真实说明动机、岗位匹配点、成长目标和稳定性判断。",
        ),
        _question(
            "你偏好的团队协作方式是什么？遇到明显分歧时通常如何处理？",
            "协作偏好和冲突处理",
            "关注候选人是否能基于事实、实验和共同目标推进协作。",
        ),
    ]
    return [*technical_questions[:9], hr_questions[0]][:10]


def _question(question: str, focus: str, scoring_criteria: str) -> InterviewQuestion:
    return InterviewQuestion(
        question=question,
        focus=focus,
        scoring_criteria=scoring_criteria,
    )


def _normalize_category(value: Any) -> str:
    text = _clean_text(value).lower().replace("-", "_").replace("/", "_")
    if text in {"technical_business", "technical", "business", "tech_business"}:
        return TECHNICAL_CATEGORY
    if text in {"hr", "human_resources", "culture", "motivation"}:
        return HR_CATEGORY
    if text in {"技术业务", "技术/业务", "业务技术"}:
        return TECHNICAL_CATEGORY
    return text


def _normalize_basis(value: Any) -> str:
    text = _clean_text(value).lower()
    if text in {"resume", "candidate", "profile", "简历", "候选人"}:
        return RESUME_BASIS
    if text in {"jd", "job", "requirement", "岗位"}:
        return "jd"
    if text in {"general", "hr", "通用"}:
        return "general"
    return text


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _unique_texts(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        text = _clean_text(item)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _trim_text(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."
