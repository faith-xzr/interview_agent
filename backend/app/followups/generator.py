from typing import List

from app.schemas import CandidateProfile, FollowUpQuestion, MatchReport


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
