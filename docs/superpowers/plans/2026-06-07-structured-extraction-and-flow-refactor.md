# Structured Extraction And Flow Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the backend around the four recruiting flows and make structured JD/resume extraction more concrete in both backend facts and frontend presentation.

**Architecture:** Keep `backend/app/main.py`, `pipeline.py`, `schemas.py`, and shared infrastructure in the root package. Move business modules into flow packages, then improve extraction with rule-first LLM postprocessing and grouped frontend rendering. Add static SVG assets under repo-root `assets/` for README/demo explanation.

**Tech Stack:** FastAPI, Pydantic, pytest, React, TypeScript, Vitest, CSS, SVG.

---

## File Structure

Create:

- `backend/app/extraction/__init__.py`: exports extraction entrypoints.
- `backend/app/extraction/postprocessor.py`: validates optional LLM postprocessing for JD and resume facts.
- `backend/app/scoring/__init__.py`: exports scoring entrypoints.
- `backend/app/question_generation/__init__.py`: exports interview question generation.
- `backend/app/followups/__init__.py`: exports follow-up generation.
- `assets/structured-extraction-flow.svg`: diagram for parsing, rule extraction, LLM postprocessing, validated facts.
- `assets/scoring-flow.svg`: diagram for JD requirements, evidence retrieval, requirement scoring.
- `assets/question-generation-flow.svg`: diagram for match report to interview questions.
- `assets/followup-flow.svg`: diagram for ambiguities/gaps to follow-up questions.
- `backend/tests/test_extraction_postprocessor.py`: backend tests for LLM postprocessing behavior.

Move:

- `backend/app/document_parser.py` -> `backend/app/extraction/document_parser.py`
- `backend/app/jd_extractor.py` -> `backend/app/extraction/jd_extractor.py`
- `backend/app/resume_extractor.py` -> `backend/app/extraction/resume_extractor.py`
- `backend/app/scoring.py` -> `backend/app/scoring/scorer.py`
- `backend/app/question_generator.py` -> `backend/app/question_generation/generator.py`

Split:

- Keep `generate_interview_questions` in `backend/app/question_generation/generator.py`.
- Move `generate_followups` into `backend/app/followups/generator.py`.

Modify:

- `backend/app/main.py`: import document parsing from `app.extraction.document_parser`.
- `backend/app/pipeline.py`: import the four flow packages and run rule-first extraction plus optional postprocessing.
- `backend/tests/test_privacy_and_parsing.py`: update import paths.
- `backend/tests/test_resume_extractor.py`: update import paths and add decorated-header coverage.
- `backend/tests/test_api_pipeline.py`: assert decorated PDF-style sections flow through the API.
- `backend/tests/test_scoring_and_generation.py`: update scoring/question/follow-up imports.
- `frontend/src/App.tsx`: render extraction facts grouped by section, compact repeated skills.
- `frontend/src/styles.css`: add section group and skill-chip styles.
- `frontend/src/App.test.tsx`: assert grouped extraction sections and compact skills.

### Task 1: Package Refactor Without Behavior Changes

**Files:**
- Move: `backend/app/document_parser.py`
- Move: `backend/app/jd_extractor.py`
- Move: `backend/app/resume_extractor.py`
- Move: `backend/app/scoring.py`
- Move: `backend/app/question_generator.py`
- Create: `backend/app/extraction/__init__.py`
- Create: `backend/app/scoring/__init__.py`
- Create: `backend/app/question_generation/__init__.py`
- Create: `backend/app/followups/__init__.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/pipeline.py`
- Modify: `backend/tests/test_privacy_and_parsing.py`
- Modify: `backend/tests/test_resume_extractor.py`
- Modify: `backend/tests/test_scoring_and_generation.py`

- [ ] **Step 1: Move files into flow packages**

Run:

```bash
mkdir -p backend/app/extraction backend/app/scoring backend/app/question_generation backend/app/followups
git mv backend/app/document_parser.py backend/app/extraction/document_parser.py
git mv backend/app/jd_extractor.py backend/app/extraction/jd_extractor.py
git mv backend/app/resume_extractor.py backend/app/extraction/resume_extractor.py
git mv backend/app/scoring.py backend/app/scoring/scorer.py
git mv backend/app/question_generator.py backend/app/question_generation/generator.py
```

- [ ] **Step 2: Create package exports**

Create `backend/app/extraction/__init__.py`:

```python
from app.extraction.document_parser import DocumentParseError, extract_text_from_bytes
from app.extraction.jd_extractor import extract_jd_facts
from app.extraction.resume_extractor import ResumeExtractionResult, extract_resume_profile, split_resume_sections

__all__ = [
    "DocumentParseError",
    "ResumeExtractionResult",
    "extract_jd_facts",
    "extract_resume_profile",
    "extract_text_from_bytes",
    "split_resume_sections",
]
```

Create `backend/app/scoring/__init__.py`:

```python
from app.scoring.scorer import score_candidate

__all__ = ["score_candidate"]
```

Create `backend/app/question_generation/__init__.py`:

```python
from app.question_generation.generator import generate_interview_questions

__all__ = ["generate_interview_questions"]
```

Create `backend/app/followups/__init__.py`:

```python
from app.followups.generator import generate_followups

__all__ = ["generate_followups"]
```

- [ ] **Step 3: Split follow-up generation out of the question module**

Remove `FollowUpQuestion` import and the `generate_followups` function from `backend/app/question_generation/generator.py`.

Create `backend/app/followups/generator.py`:

```python
from typing import List

from app.schemas import CandidateProfile, FollowUpQuestion, MatchReport


def generate_followups(candidate: CandidateProfile, match: MatchReport) -> List[FollowUpQuestion]:
    questions = []
    for point in candidate.ambiguous_points[:3]:
        questions.append(
            FollowUpQuestion(
                question=f"请补充说明：{point}",
                reason="该信息会影响岗位匹配判断，需要候选人进一步澄清。",
                related_evidence=point,
            )
        )
    for gap in match.gap_reasons[:2]:
        questions.append(
            FollowUpQuestion(
                question=f"针对差距项“{gap}”，你有哪些补充经验或可迁移案例？",
                reason="匹配报告提示该方向存在不确定性。",
                related_evidence=gap,
            )
        )
    if not questions:
        questions.append(
            FollowUpQuestion(
                question="请用一个具体案例说明你的能力如何迁移到当前 JD 的核心职责。",
                reason="候选人与 JD 已有较高匹配度，追问用于验证真实深度。",
                related_evidence=None,
            )
        )
    return questions[:5]
```

- [ ] **Step 4: Update imports**

Change `backend/app/main.py`:

```python
from app.extraction.document_parser import DocumentParseError, extract_text_from_bytes
```

Change `backend/app/pipeline.py` imports:

```python
from app.extraction.jd_extractor import extract_jd_facts
from app.extraction.resume_extractor import extract_resume_profile
from app.followups import generate_followups
from app.question_generation import generate_interview_questions
from app.scoring import score_candidate
```

Change backend tests:

```python
from app.extraction.document_parser import extract_text_from_bytes
from app.extraction.resume_extractor import extract_resume_profile
from app.question_generation import generate_interview_questions
from app.followups import generate_followups
from app.scoring import score_candidate
```

- [ ] **Step 5: Run backend tests for import regressions**

Run:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
```

Expected: all existing backend tests pass with no import errors.

- [ ] **Step 6: Commit package refactor**

Run:

```bash
git add backend/app backend/tests
git commit -m "refactor: split recruiting flow packages"
```

### Task 2: Improve Resume Section Detection

**Files:**
- Modify: `backend/app/extraction/resume_extractor.py`
- Modify: `backend/tests/test_resume_extractor.py`
- Modify: `backend/tests/test_api_pipeline.py`

- [ ] **Step 1: Write failing test for decorated headers**

Add to `backend/tests/test_resume_extractor.py`:

```python
def test_section_split_supports_decorated_resume_headers():
    text = """
小周
求职意向：AI产品经理 / Agent 应用架构师
【个人评价】
• 精通 Agent 编排与 RAG 链路设计，曾主导多个企业级智能助手从0到1的落地。
【教育背景】
• 某重点理工类大学（985）| 计算机科学与技术 | 本科 | 2022.09-2026.06
【项目经验】
• 企业级智能助手项目：负责需求拆解、RAG 召回评估和上线验收。
【专业技能】
Python | SQL | RAG | Agent 编排
"""

    result = extract_resume_profile(text, "decorated.pdf")

    assert "summary" in result.sections
    assert "education" in result.sections
    assert "projects" in result.sections
    assert "skills" in result.sections
    assert any(fact.section == "summary" for fact in result.facts)
    assert any(fact.section == "education" and fact.fact_type == "education" for fact in result.facts)
    assert any(fact.section == "projects" and fact.fact_type == "project" for fact in result.facts)
    assert any(fact.section == "skills" and fact.value == "Agent 编排" for fact in result.facts)
```

Add to `backend/tests/test_api_pipeline.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_resume_extractor.py::test_section_split_supports_decorated_resume_headers backend/tests/test_api_pipeline.py::test_run_pipeline_preserves_decorated_resume_sections -q
```

Expected: fail because decorated headers are not recognized and summary/project facts are missing.

- [ ] **Step 3: Implement decorated header normalization and summary facts**

In `backend/app/extraction/resume_extractor.py`, expand `SECTION_HEADERS`:

```python
SECTION_HEADERS = {
    "基本信息": "basic",
    "个人信息": "basic",
    "求职意向": "basic",
    "教育经历": "education",
    "教育背景": "education",
    "学历背景": "education",
    "学习经历": "education",
    "工作经历": "experience",
    "工作经验": "experience",
    "职业经历": "experience",
    "实习经历": "experience",
    "实习经验": "experience",
    "项目经历": "projects",
    "项目经验": "projects",
    "项目实践": "projects",
    "专业技能": "skills",
    "技能": "skills",
    "技能清单": "skills",
    "证书": "certifications",
    "资格证书": "certifications",
    "证书资质": "certifications",
    "自我评价": "summary",
    "个人评价": "summary",
    "个人总结": "summary",
    "个人优势": "summary",
}
```

Replace `_match_section_header`:

```python
def _match_section_header(text: str) -> Optional[str]:
    normalized = _normalize_header_text(text)
    return SECTION_HEADERS.get(normalized)


def _normalize_header_text(text: str) -> str:
    normalized = text.strip()
    normalized = re.sub(r"^[【\\[（(]+", "", normalized)
    normalized = re.sub(r"[】\\]）)]+$", "", normalized)
    normalized = normalized.strip().strip(":：")
    normalized = re.sub(r"\\s+", "", normalized)
    return normalized
```

In `extract_resume_profile`, call summary handling after skills:

```python
    _apply_skills_section(profile, facts, sections.get("skills", []))
    _apply_summary_section(profile, facts, sections.get("summary", []))
    _apply_certification_section(profile, facts, sections.get("certifications", []))
```

Add `_apply_summary_section`:

```python
def _apply_summary_section(profile: CandidateProfile, facts: List[ExtractedFact], lines: List[ResumeLine]) -> None:
    if not lines:
        return
    highlights = [_strip_bullet(line.text) for line in lines if _strip_bullet(line.text)]
    if highlights:
        profile.highlights = unique_preserve_order(profile.highlights + highlights)[:8]
    for line, value in zip(lines, highlights):
        facts.append(_fact("summary", value, line, "summary", confidence=0.8))
```

- [ ] **Step 4: Run tests to verify green**

Run:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_resume_extractor.py::test_section_split_supports_decorated_resume_headers backend/tests/test_api_pipeline.py::test_run_pipeline_preserves_decorated_resume_sections -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit section detection**

Run:

```bash
git add backend/app/extraction/resume_extractor.py backend/tests/test_resume_extractor.py backend/tests/test_api_pipeline.py
git commit -m "feat: recognize decorated resume sections"
```

### Task 3: Add Rule-First LLM Extraction Postprocessing

**Files:**
- Create: `backend/app/extraction/postprocessor.py`
- Modify: `backend/app/pipeline.py`
- Modify: `backend/app/extraction/__init__.py`
- Create: `backend/tests/test_extraction_postprocessor.py`
- Modify: `backend/tests/test_api_pipeline.py`

- [ ] **Step 1: Write failing postprocessor tests**

Create `backend/tests/test_extraction_postprocessor.py`:

```python
from app.extraction.postprocessor import postprocess_extraction
from app.schemas import CandidateProfile, ExtractedFact


class FakeLLM:
    available = True

    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, system_prompt: str, user_prompt: str):
        return self.payload


def test_postprocessor_accepts_supported_fact_reclassification():
    text = "【项目经验】\n• 企业级智能助手项目：负责 RAG 召回评估和上线验收。"
    profile = CandidateProfile(name="小周")
    facts = [
        ExtractedFact(
            fact_type="summary",
            value="企业级智能助手项目",
            evidence="• 企业级智能助手项目：负责 RAG 召回评估和上线验收。",
            section="summary",
            line_start=2,
            line_end=2,
            confidence=0.6,
            extractor="section_rules",
        )
    ]
    llm = FakeLLM(
        {
            "profile": {"name": "小周", "projects": ["企业级智能助手项目：负责 RAG 召回评估和上线验收。"]},
            "facts": [
                {
                    "fact_type": "project",
                    "value": "企业级智能助手项目",
                    "evidence": "• 企业级智能助手项目：负责 RAG 召回评估和上线验收。",
                    "section": "projects",
                    "line_start": 2,
                    "line_end": 2,
                    "confidence": 0.86,
                    "extractor": "llm_postprocess",
                }
            ],
        }
    )
    warnings = []

    result_profile, result_facts = postprocess_extraction(
        llm=llm,
        text=text,
        profile=profile,
        facts=facts,
        warnings=warnings,
        label="小周",
    )

    assert warnings == []
    assert "企业级智能助手项目：负责 RAG 召回评估和上线验收。" in result_profile.projects
    assert any(fact.fact_type == "project" and fact.section == "projects" for fact in result_facts)
    assert any(fact.extractor == "llm_postprocess" for fact in result_facts)


def test_postprocessor_rejects_facts_without_source_evidence():
    text = "【专业技能】\nPython | SQL"
    profile = CandidateProfile(name="小周", skills=["Python", "SQL"])
    facts = [
        ExtractedFact(
            fact_type="skill",
            value="Python",
            evidence="Python | SQL",
            section="skills",
            line_start=2,
            line_end=2,
            confidence=0.9,
            extractor="section_rules",
        )
    ]
    llm = FakeLLM(
        {
            "profile": {"name": "小周", "skills": ["Python", "SQL", "Kubernetes"]},
            "facts": [
                {
                    "fact_type": "skill",
                    "value": "Kubernetes",
                    "evidence": "熟悉 Kubernetes 集群调优",
                    "section": "skills",
                    "confidence": 0.9,
                    "extractor": "llm_postprocess",
                }
            ],
        }
    )
    warnings = []

    result_profile, result_facts = postprocess_extraction(
        llm=llm,
        text=text,
        profile=profile,
        facts=facts,
        warnings=warnings,
        label="小周",
    )

    assert "Kubernetes" not in result_profile.skills
    assert not any(fact.value == "Kubernetes" for fact in result_facts)
    assert warnings == []


def test_postprocessor_falls_back_when_payload_is_invalid():
    text = "小周\n【专业技能】\nPython | SQL"
    profile = CandidateProfile(name="小周", skills=["Python", "SQL"])
    facts = [
        ExtractedFact(
            fact_type="skill",
            value="Python",
            evidence="Python | SQL",
            section="skills",
            line_start=3,
            line_end=3,
            confidence=0.9,
            extractor="section_rules",
        )
    ]
    warnings = []

    result_profile, result_facts = postprocess_extraction(
        llm=FakeLLM({"profile": {"name": []}, "facts": "not-a-list"}),
        text=text,
        profile=profile,
        facts=facts,
        warnings=warnings,
        label="小周",
    )

    assert result_profile == profile
    assert result_facts == facts
    assert warnings == ["小周 的 LLM 抽取后处理结果结构不合法，已使用本地规则结果。"]
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_extraction_postprocessor.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'app.extraction.postprocessor'`.

- [ ] **Step 3: Implement postprocessor**

Create `backend/app/extraction/postprocessor.py`:

```python
from typing import Any, Iterable, List, Tuple, TypeVar

from pydantic import BaseModel, Field

from app.schemas import CandidateProfile, ExtractedFact, JDProfile
from app.text_utils import unique_preserve_order

ProfileT = TypeVar("ProfileT", CandidateProfile, JDProfile)


class ExtractionPostprocessPayload(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    facts: List[ExtractedFact] = Field(default_factory=list)


def postprocess_extraction(
    llm,
    text: str,
    profile: ProfileT,
    facts: List[ExtractedFact],
    warnings: List[str],
    label: str,
) -> Tuple[ProfileT, List[ExtractedFact]]:
    if not getattr(llm, "available", False):
        return profile, facts

    payload = llm.complete_json(
        "你是招聘结构化抽取后处理助手，只输出 JSON。所有 facts 必须来自原文 evidence，禁止编造。",
        _build_prompt(text, profile, facts),
    )
    if not payload:
        warnings.append(f"{label} 的 LLM 抽取后处理失败，已使用本地规则结果。")
        return profile, facts

    try:
        parsed = ExtractionPostprocessPayload.model_validate(payload)
        profile_type = type(profile)
        supported_facts = _filter_supported_facts(parsed.facts, text)
        merged_profile = _merge_profile(profile, profile_type.model_validate(parsed.profile), supported_facts)
        return merged_profile, _dedupe_facts([*facts, *supported_facts])
    except Exception:
        warnings.append(f"{label} 的 LLM 抽取后处理结果结构不合法，已使用本地规则结果。")
        return profile, facts


def _build_prompt(text: str, profile: BaseModel, facts: Iterable[ExtractedFact]) -> str:
    local_payload = {
        "profile": profile.model_dump(mode="json"),
        "facts": [fact.model_dump(mode="json") for fact in facts],
    }
    return (
        "请基于原文和本地规则抽取结果做后处理。可以合并重复事实、修正 fact_type/section、补充有 evidence 支撑的字段。"
        "返回 JSON: {\"profile\": {...}, \"facts\": [...]}。\n\n"
        f"原文:\n{text}\n\n"
        f"本地规则结果:\n{local_payload}"
    )


def _filter_supported_facts(facts: Iterable[ExtractedFact], text: str) -> List[ExtractedFact]:
    supported = []
    normalized_text = _normalize_for_evidence(text)
    for fact in facts:
        if not fact.evidence.strip():
            continue
        if _normalize_for_evidence(fact.evidence) not in normalized_text:
            continue
        if fact.extractor == "section_rules":
            fact.extractor = "llm_postprocess"
        supported.append(fact)
    return supported


def _merge_profile(profile: ProfileT, proposed: ProfileT, supported_facts: List[ExtractedFact]) -> ProfileT:
    if isinstance(profile, CandidateProfile):
        return _merge_candidate_profile(profile, proposed, supported_facts)  # type: ignore[arg-type, return-value]
    if isinstance(profile, JDProfile):
        return _merge_jd_profile(profile, proposed, supported_facts)  # type: ignore[arg-type, return-value]
    return profile


def _merge_candidate_profile(
    profile: CandidateProfile, proposed: CandidateProfile, supported_facts: List[ExtractedFact]
) -> CandidateProfile:
    merged = profile.model_copy(deep=True)
    supported_values = _supported_values(supported_facts)
    for field_name in ("education", "work_experiences", "projects", "skills", "certifications", "highlights"):
        current = list(getattr(merged, field_name))
        additions = [value for value in getattr(proposed, field_name) if _is_supported_value(value, supported_values)]
        setattr(merged, field_name, unique_preserve_order(current + additions))
    for field_name in ("risk_points", "ambiguous_points"):
        current = list(getattr(merged, field_name))
        setattr(merged, field_name, unique_preserve_order(current + list(getattr(proposed, field_name)))[:8])
    if not merged.target_role and proposed.target_role:
        merged.target_role = proposed.target_role
    if not merged.location and proposed.location:
        merged.location = proposed.location
    return merged


def _merge_jd_profile(profile: JDProfile, proposed: JDProfile, supported_facts: List[ExtractedFact]) -> JDProfile:
    merged = profile.model_copy(deep=True)
    supported_values = _supported_values(supported_facts)
    for field_name in ("responsibilities", "required_skills", "nice_to_have_skills", "industry_background", "hard_requirements"):
        current = list(getattr(merged, field_name))
        additions = [value for value in getattr(proposed, field_name) if _is_supported_value(value, supported_values)]
        setattr(merged, field_name, unique_preserve_order(current + additions))
    if merged.job_title == "未命名岗位" and proposed.job_title:
        merged.job_title = proposed.job_title
    if not merged.years_required and proposed.years_required:
        merged.years_required = proposed.years_required
    if merged.seniority == "未说明" and proposed.seniority:
        merged.seniority = proposed.seniority
    return merged


def _supported_values(facts: Iterable[ExtractedFact]) -> List[str]:
    values = []
    for fact in facts:
        values.extend([fact.value, fact.evidence])
    return [_normalize_for_evidence(value) for value in values if value]


def _is_supported_value(value: str, supported_values: List[str]) -> bool:
    normalized = _normalize_for_evidence(value)
    if not normalized:
        return False
    return any(normalized in supported or supported in normalized for supported in supported_values)


def _normalize_for_evidence(text: str) -> str:
    return "".join(str(text).lower().split())


def _dedupe_facts(facts: List[ExtractedFact]) -> List[ExtractedFact]:
    seen = set()
    result = []
    for fact in facts:
        key = (fact.fact_type, fact.value.lower(), fact.evidence.lower(), fact.section)
        if key in seen:
            continue
        seen.add(key)
        result.append(fact)
    return result
```

- [ ] **Step 4: Export postprocessor**

Update `backend/app/extraction/__init__.py`:

```python
from app.extraction.postprocessor import postprocess_extraction
```

Add `"postprocess_extraction"` to `__all__`.

- [ ] **Step 5: Run postprocessor tests to verify green**

Run:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_extraction_postprocessor.py -q
```

Expected: all postprocessor tests pass.

- [ ] **Step 6: Wire rule-first JD and resume postprocessing into pipeline**

Update `backend/app/pipeline.py` imports:

```python
from app.extraction.postprocessor import postprocess_extraction
```

Replace `_extract_jd`:

```python
    def _extract_jd(self, text: str, warnings: List[str]) -> Tuple[JDProfile, List[ExtractedFact]]:
        initial_profile = extract_jd_profile(text)
        initial_facts = extract_jd_facts(text, initial_profile)
        return postprocess_extraction(
            llm=self.llm,
            text=text,
            profile=initial_profile,
            facts=initial_facts,
            warnings=warnings,
            label="JD",
        )
```

Update `run`:

```python
        jd_profile, jd_extraction_facts = self._extract_jd(jd_text, warnings)
```

Replace `_extract_candidate` body:

```python
        initial_result = extract_resume_profile(text, source_name)
        initial_profile = initial_result.profile
        masked = mask_pii(text, candidate_name=initial_profile.name)
        processed_profile, processed_facts = postprocess_extraction(
            llm=self.llm,
            text=masked.text,
            profile=initial_profile,
            facts=initial_result.facts,
            warnings=warnings,
            label=source_name,
        )
        restored = restore_pii_in_data(processed_profile.model_dump(mode="json"), masked.replacements)
        profile = CandidateProfile.model_validate(restored)
        return _merge_candidate_profile(profile, initial_profile), processed_facts
```

- [ ] **Step 7: Update API test for rule-first JD facts**

In `backend/tests/test_api_pipeline.py`, keep the existing assertions that `required_skill`, `years_required`, and `responsibility` facts are present. They verify rule-first JD extraction still emits local facts without an LLM key.

- [ ] **Step 8: Run pipeline and backend tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_api_pipeline.py backend/tests/test_extraction_postprocessor.py -q
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
```

Expected: all backend tests pass.

- [ ] **Step 9: Commit extraction postprocessing**

Run:

```bash
git add backend/app/extraction backend/app/pipeline.py backend/tests
git commit -m "feat: add rule-first extraction postprocessing"
```

### Task 4: Group Extraction Facts In The Frontend

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Write failing frontend test**

Update the `shows result navigation and detail views` test in `frontend/src/App.test.tsx` after clicking `结构化提取`:

```tsx
    expect(screen.getByText("抽取过程")).toBeInTheDocument();
    expect(screen.getByText("JD 核心要求")).toBeInTheDocument();
    expect(screen.getByText("简历抽取事实")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "专业技能" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "项目经验" })).toBeInTheDocument();
    expect(screen.getByText("Python")).toHaveClass("skill-chip");
    expect(screen.getByText("FastAPI")).toHaveClass("skill-chip");
    expect(screen.getByText("专业技能：Python | FastAPI | SQL")).toBeInTheDocument();
```

Update the mock candidate facts at the top of `frontend/src/App.test.tsx` so they include a project fact:

```tsx
        {
          fact_type: "project",
          value: "RAG 平台建设",
          evidence: "项目经验：RAG 平台建设，负责召回评估和上线。",
          section: "projects",
          line_start: 8,
          line_end: 8,
          confidence: 0.86,
          extractor: "section_rules"
        }
```

- [ ] **Step 2: Run frontend test to verify red**

Run:

```bash
cd frontend && npm test -- --run App.test.tsx
```

Expected: fail because extraction facts still render as flat cards and no `.skill-chip` elements exist.

- [ ] **Step 3: Replace flat extraction rendering with grouped rendering**

In `frontend/src/App.tsx`, replace `ExtractionProcess`, `ExtractionColumn`, `FactRow`, and `prioritizeResumeFacts` with:

```tsx
const SECTION_LABELS: Record<string, string> = {
  basic: "基本信息",
  education: "学历背景",
  experience: "实习/工作经验",
  projects: "项目经验",
  skills: "专业技能",
  summary: "自我评价",
  certifications: "证书资质",
  jd: "JD 核心要求"
};

const SECTION_ORDER = ["basic", "education", "experience", "projects", "skills", "summary", "certifications"];

function ExtractionProcess({ jdFacts, resumeFacts }: { jdFacts?: ExtractedFact[]; resumeFacts?: ExtractedFact[] }) {
  const visibleJdFacts = (jdFacts ?? []).slice(0, 12);
  const groupedResumeFacts = groupResumeFacts(resumeFacts ?? []);
  return (
    <div className="extraction-grid">
      <ExtractionColumn title="JD 核心要求" facts={visibleJdFacts} emptyText="暂无 JD 抽取事实" />
      <ResumeExtractionColumn groups={groupedResumeFacts} />
    </div>
  );
}

function ExtractionColumn({ title, facts, emptyText }: { title: string; facts: ExtractedFact[]; emptyText: string }) {
  return (
    <div className="extraction-column">
      <div className="extraction-column-header">
        <strong>{title}</strong>
        <span>{facts.length} 项</span>
      </div>
      {facts.length ? (
        <div className="fact-list">
          {facts.map((fact, index) => (
            <FactRow fact={fact} key={`${fact.fact_type}-${fact.value}-${index}`} />
          ))}
        </div>
      ) : (
        <p className="empty-facts">{emptyText}</p>
      )}
    </div>
  );
}

function ResumeExtractionColumn({ groups }: { groups: FactGroup[] }) {
  const total = groups.reduce((sum, group) => sum + group.facts.length, 0);
  return (
    <div className="extraction-column">
      <div className="extraction-column-header">
        <strong>简历抽取事实</strong>
        <span>{total} 项</span>
      </div>
      {groups.length ? (
        <div className="section-fact-list">
          {groups.map((group) => (
            <FactSection group={group} key={group.section} />
          ))}
        </div>
      ) : (
        <p className="empty-facts">暂无简历抽取事实</p>
      )}
    </div>
  );
}

interface FactGroup {
  section: string;
  facts: ExtractedFact[];
}

function FactSection({ group }: { group: FactGroup }) {
  const skillFacts = group.facts.filter((fact) => fact.fact_type === "skill");
  const otherFacts = group.facts.filter((fact) => fact.fact_type !== "skill").slice(0, 4);
  const skillEvidence = skillFacts[0];
  return (
    <section className="fact-section">
      <div className="fact-section-header">
        <h4>{SECTION_LABELS[group.section] ?? group.section}</h4>
        <span>{group.facts.length} 项</span>
      </div>
      {skillFacts.length ? (
        <article className="fact-row compact-skill-row">
          <div className="fact-row-top">
            <span className="fact-type">skill</span>
            <span className="fact-confidence">{Math.round(Math.max(...skillFacts.map((fact) => fact.confidence)) * 100)}%</span>
          </div>
          <div className="skill-chip-list">
            {skillFacts.map((fact) => (
              <span className="skill-chip" key={`${fact.value}-${fact.line_start ?? "line"}`}>
                {fact.value}
              </span>
            ))}
          </div>
          {skillEvidence ? <p>{skillEvidence.evidence}</p> : null}
          {skillEvidence ? <span className="fact-meta">{formatFactMeta(skillEvidence)}</span> : null}
        </article>
      ) : null}
      {otherFacts.map((fact, index) => (
        <FactRow fact={fact} key={`${fact.fact_type}-${fact.value}-${index}`} />
      ))}
    </section>
  );
}

function FactRow({ fact }: { fact: ExtractedFact }) {
  return (
    <article className="fact-row">
      <div className="fact-row-top">
        <span className="fact-type">{fact.fact_type}</span>
        <span className="fact-confidence">{Math.round(fact.confidence * 100)}%</span>
      </div>
      <strong>{fact.value}</strong>
      <p>{fact.evidence}</p>
      <span className="fact-meta">{formatFactMeta(fact)}</span>
    </article>
  );
}

function groupResumeFacts(facts: ExtractedFact[]): FactGroup[] {
  const bySection = new Map<string, ExtractedFact[]>();
  for (const fact of facts) {
    const section = fact.section || "unknown";
    bySection.set(section, [...(bySection.get(section) ?? []), fact]);
  }
  return [...bySection.entries()]
    .map(([section, sectionFacts]) => ({ section, facts: sortFactsWithinSection(sectionFacts).slice(0, 6) }))
    .sort((left, right) => sectionRank(left.section) - sectionRank(right.section));
}

function sortFactsWithinSection(facts: ExtractedFact[]) {
  const rank: Record<string, number> = {
    experience_position: 1,
    project: 1,
    responsibility: 2,
    education: 2,
    degree: 3,
    skill: 4,
    certification: 5,
    metric: 6,
    domain_evidence: 7,
    summary: 8
  };
  return [...facts].sort((left, right) => (rank[left.fact_type] ?? 99) - (rank[right.fact_type] ?? 99));
}

function sectionRank(section: string) {
  const index = SECTION_ORDER.indexOf(section);
  return index === -1 ? 99 : index;
}
```

- [ ] **Step 4: Add grouped extraction styles**

Append to `frontend/src/styles.css` near existing extraction styles:

```css
.section-fact-list {
  display: grid;
  gap: 14px;
}

.fact-section {
  border: 1px solid #d9dee8;
  border-radius: 8px;
  padding: 14px;
  background: #ffffff;
}

.fact-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.fact-section-header h4 {
  margin: 0;
  font-size: 0.98rem;
  color: #111827;
}

.fact-section-header span {
  color: #667085;
  font-size: 0.86rem;
}

.compact-skill-row {
  gap: 10px;
}

.skill-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.skill-chip {
  border: 1px solid #b9c4d6;
  border-radius: 999px;
  padding: 4px 9px;
  background: #f6f8fb;
  color: #25324a;
  font-size: 0.86rem;
  line-height: 1.25;
}
```

- [ ] **Step 5: Run frontend test to verify green**

Run:

```bash
cd frontend && npm test -- --run App.test.tsx
```

Expected: App tests pass.

- [ ] **Step 6: Commit grouped extraction UI**

Run:

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/styles.css
git commit -m "feat: group extraction facts in UI"
```

### Task 5: Add Flow SVG Assets

**Files:**
- Create: `assets/structured-extraction-flow.svg`
- Create: `assets/scoring-flow.svg`
- Create: `assets/question-generation-flow.svg`
- Create: `assets/followup-flow.svg`

- [ ] **Step 1: Create SVG assets**

Create `assets/structured-extraction-flow.svg` with four boxes:

```text
Input Files/Text -> Python Parser -> Rule-Based Extraction -> LLM Postprocess -> Profile + Evidence Facts
```

Create `assets/scoring-flow.svg` with four boxes:

```text
JD Requirements -> Candidate Facts -> Evidence Retrieval -> Requirement Scores -> 0-100 Decision
```

Create `assets/question-generation-flow.svg` with four boxes:

```text
JD Profile -> Match Report -> Evidence-Grounded Questions -> 10 Interview Questions
```

Create `assets/followup-flow.svg` with four boxes:

```text
Gaps + Ambiguities -> Risk Review -> Clarification Prompts -> 3-5 Follow-Up Questions
```

Use simple inline SVG: fixed `viewBox`, readable text, no external dependencies.

- [ ] **Step 2: Verify asset files exist**

Run:

```bash
test -f assets/structured-extraction-flow.svg
test -f assets/scoring-flow.svg
test -f assets/question-generation-flow.svg
test -f assets/followup-flow.svg
```

Expected: all commands exit 0.

- [ ] **Step 3: Commit SVG assets**

Run:

```bash
git add assets
git commit -m "docs: add recruiting flow diagrams"
```

### Task 6: Full Verification And Browser Smoke Test

**Files:**
- No planned source edits unless verification finds a bug.

- [ ] **Step 1: Run backend tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
```

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend tests**

Run:

```bash
cd frontend && npm test
```

Expected: all frontend tests pass.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: build exits 0.

- [ ] **Step 4: Start local servers if not already running**

Backend:

```bash
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

- [ ] **Step 5: Browser smoke test**

Open `http://127.0.0.1:5173/`, submit:

JD:

```text
AI产品经理，负责 Agent 应用、RAG 链路设计、项目落地和数据分析。
```

Resume:

```text
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
```

Expected: the `结构化提取` tab shows section groups and compact skill chips, and the matching/question/follow-up tabs still render.
