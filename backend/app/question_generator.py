from typing import List

from app.schemas import CandidateProfile, FollowUpQuestion, InterviewQuestion, JDProfile, MatchReport


def generate_interview_questions(
    jd: JDProfile, candidate: CandidateProfile, match: MatchReport
) -> List[InterviewQuestion]:
    difficulty = "高级" if jd.seniority in {"高级", "资深", "专家", "负责人"} else "中级"
    questions: List[InterviewQuestion] = []

    for skill in (jd.required_skills or candidate.skills)[:5]:
        questions.append(
            InterviewQuestion(
                question=f"请结合你最近的项目，说明你如何使用 {skill} 解决一个真实业务问题？",
                focus=f"{skill} 的实际应用深度",
                difficulty=difficulty,
                scoring_criteria="优秀回答应包含业务背景、技术选型、关键实现、权衡取舍和量化结果。",
                evidence=_first_evidence(match),
            )
        )

    if candidate.projects:
        questions.append(
            InterviewQuestion(
                question=f"请完整复盘这个项目：{candidate.projects[0]}。你个人负责哪一部分，最终结果如何衡量？",
                focus="项目真实性、个人贡献和结果指标",
                difficulty=difficulty,
                scoring_criteria="重点看候选人是否能讲清目标、架构、难点、协作边界和可验证结果。",
                evidence=candidate.projects[0],
            )
        )

    scenario_title = jd.job_title or "该岗位"
    base_questions = [
        (
            f"如果入职后需要在两周内交付一个 {scenario_title} 相关的最小可用方案，你会如何拆解计划？",
            "业务拆解和交付节奏",
            "中级",
            "应能说明目标澄清、优先级、风险识别、里程碑和验收口径。",
        ),
        (
            "请描述一次你排查线上问题或复杂故障的经历，你如何定位根因并防止复发？",
            "问题定位和工程稳定性",
            "中级",
            "关注定位路径、数据证据、临时止血、长期修复和复盘机制。",
        ),
        (
            "当业务方提出的需求和技术实现成本冲突时，你通常如何沟通并推动决策？",
            "跨团队沟通和业务判断",
            "中级",
            "优秀回答应体现约束澄清、方案对比、影响评估和共同决策。",
        ),
        (
            "请举例说明你如何评估一个技术方案是否值得上线。",
            "技术判断和风险意识",
            "中级",
            "应覆盖收益、成本、风险、监控、回滚和后续维护。",
        ),
        (
            "如果面试官要求你现场优化一个现有系统，你会先看哪些指标和代码路径？",
            "系统化分析能力",
            "高级",
            "重点看是否先定义瓶颈、收集证据，再提出可验证优化。",
        ),
        (
            "请说明你过去一次学习新技术并落地到项目中的过程。",
            "学习能力和落地能力",
            "初级",
            "应包含学习路径、验证方式、踩坑复盘和业务价值。",
        ),
        (
            "如果你和同事对技术方案有明显分歧，你会如何处理？",
            "协作方式和冲突处理",
            "中级",
            "关注候选人是否能基于事实、实验和共同目标推进。",
        ),
        (
            "你认为这个岗位最容易失败的风险是什么？你会如何提前规避？",
            "岗位理解和风险预判",
            "高级",
            "优秀回答应能结合 JD 的职责、约束和候选人自身经验提出具体措施。",
        ),
    ]
    for question, focus, level, criteria in base_questions:
        questions.append(
            InterviewQuestion(
                question=question,
                focus=focus,
                difficulty=level,
                scoring_criteria=criteria,
                evidence=_first_evidence(match),
            )
        )

    return questions[: max(10, len(questions))]


def generate_followups(candidate: CandidateProfile, match: MatchReport) -> List[FollowUpQuestion]:
    questions: List[FollowUpQuestion] = []
    for point in candidate.ambiguous_points:
        questions.append(
            FollowUpQuestion(
                question=f"简历中“{point}”，请你补充具体背景、你的职责和可验证结果。",
                reason="简历存在模糊点，需要验证真实性和贡献边界。",
                related_evidence=_first_evidence(match),
            )
        )
    for gap in match.gap_reasons:
        if len(questions) >= 5:
            break
        questions.append(
            FollowUpQuestion(
                question=f"关于“{gap}”，你是否有未写在简历中的经历可以补充？",
                reason="匹配评分中的缺口项需要在面试中澄清。",
                related_evidence=_first_evidence(match),
            )
        )
    pads = [
        "请补充最近一个项目的团队规模、周期和你的关键产出。",
        "请说明你在项目中做过的最困难技术决策，以及当时的替代方案。",
        "请用一个具体案例说明你的能力如何迁移到当前 JD 的核心职责。",
    ]
    for question in pads:
        if len(questions) >= 3:
            break
        questions.append(
            FollowUpQuestion(
                question=question,
                reason="用于补足面试追问的基础验证问题。",
                related_evidence=_first_evidence(match),
            )
        )
    return questions[:5]


def _first_evidence(match: MatchReport) -> str:
    return match.evidence_snippets[0].text if match.evidence_snippets else None

