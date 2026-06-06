from dataclasses import dataclass
from typing import List, Optional

from app.schemas import ExtractedFact, JDProfile
from app.text_utils import split_sentences


@dataclass
class JDLine:
    line_number: int
    text: str


def extract_jd_facts(text: str, profile: JDProfile) -> List[ExtractedFact]:
    lines = _split_lines(text)
    facts: List[ExtractedFact] = []

    facts.extend(_facts_from_values("job_title", [profile.job_title], lines, confidence=0.82))
    facts.extend(_facts_from_values("responsibility", profile.responsibilities, lines, confidence=0.86))
    facts.extend(_facts_from_values("required_skill", profile.required_skills, lines, confidence=0.9))
    facts.extend(_facts_from_values("nice_to_have_skill", profile.nice_to_have_skills, lines, confidence=0.82))
    if profile.years_required:
        facts.extend(_facts_from_values("years_required", [str(profile.years_required)], lines, confidence=0.88))
    if profile.seniority and profile.seniority != "未说明":
        facts.extend(_facts_from_values("seniority", [profile.seniority], lines, confidence=0.84))
    facts.extend(_facts_from_values("industry", profile.industry_background, lines, confidence=0.78))
    facts.extend(_facts_from_values("hard_requirement", profile.hard_requirements, lines, confidence=0.86))
    return _dedupe_facts(facts)


def _split_lines(text: str) -> List[JDLine]:
    lines = []
    for line_number, raw_line in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), start=1):
        stripped = raw_line.strip()
        if stripped:
            lines.append(JDLine(line_number=line_number, text=stripped))
    if lines:
        return lines
    return [JDLine(line_number=1, text=sentence) for sentence in split_sentences(text)]


def _facts_from_values(
    fact_type: str,
    values: List[str],
    lines: List[JDLine],
    confidence: float,
) -> List[ExtractedFact]:
    facts = []
    for value in values:
        match = _best_evidence_line(value, lines)
        evidence = match.text if match else value
        facts.append(
            ExtractedFact(
                fact_type=fact_type,
                value=value,
                evidence=evidence,
                section="jd",
                line_start=match.line_number if match else None,
                line_end=match.line_number if match else None,
                confidence=confidence,
                extractor="jd_profile_projection",
            )
        )
    return facts


def _best_evidence_line(value: str, lines: List[JDLine]) -> Optional[JDLine]:
    normalized_value = value.lower()
    exact = [line for line in lines if normalized_value in line.text.lower()]
    if exact:
        return exact[0]
    tokens = [token.lower() for token in split_sentences(value) if token.strip()]
    if not tokens:
        tokens = [normalized_value]
    for line in lines:
        line_text = line.text.lower()
        if any(token and token in line_text for token in tokens):
            return line
    return lines[0] if lines else None


def _dedupe_facts(facts: List[ExtractedFact]) -> List[ExtractedFact]:
    seen = set()
    result = []
    for fact in facts:
        key = (fact.fact_type, fact.value.lower(), fact.evidence.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(fact)
    return result
