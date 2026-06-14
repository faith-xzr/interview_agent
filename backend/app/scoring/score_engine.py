STATUS_MULTIPLIERS = {
    "强匹配": 1.0,
    "直接匹配": 0.9,
    "相关匹配": 0.55,
    "弱匹配": 0.25,
    "未匹配": 0.0,
}


def compute_contribution(max_score: float, status: str, confidence: float) -> float:
    multiplier = STATUS_MULTIPLIERS.get(status)
    if multiplier is None or status == "未匹配":
        return 0.0
    effective_confidence = max(0.5, min(1.0, float(confidence)))
    contribution = max_score * multiplier * effective_confidence
    return round(max(0.0, min(max_score, contribution)), 1)
