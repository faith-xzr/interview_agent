# Structured Extraction And Flow Refactor Design

## Goal

Improve the first stage of the recruiting demo so JD and resume extraction is concrete, evidence-backed, and easier to explain in the UI. At the same time, reorganize backend code around the four product flows:

- Structured extraction
- Matching score
- Interview question generation
- Follow-up simulation

The refactor should make the project easier to present in README and demo material without turning the deterministic pipeline into a heavyweight agent graph.

## Current State

File parsing already happens in `backend/app/document_parser.py`:

- PDF: use `pypdf` page text extraction first; if no text is found, fall back to the macOS Vision OCR Swift script.
- DOCX: use `python-docx` and read paragraph text.
- Other files: decode as plain text with `utf-8`, `gb18030`, then `latin-1`.

The parser only needs to return normalized text. The chosen parsing path does not need to be exposed as downstream metadata.

Structured extraction already exists, but the current behavior has three gaps:

- Resume section detection only recognizes exact plain headers, so titles such as `【个人评价】` and `【教育背景】` fall into `basic`.
- JD extraction is LLM-first with local fallback, while resume extraction is rule-first but lets the LLM modify only `CandidateProfile`, not the evidence-backed fact list.
- The frontend displays facts as a flat ranked list. Skill facts dominate the visible list, and repeated facts from the same evidence line look abstract.

## Recommended Backend Structure

Keep cross-flow infrastructure in `backend/app`:

```text
backend/app/
  main.py
  pipeline.py
  schemas.py
  config.py
  llm_client.py
  privacy.py
  storage.py
  vector_store.py
  text_utils.py
```

Move business-flow modules into packages:

```text
backend/app/
  extraction/
    __init__.py
    document_parser.py
    jd_extractor.py
    resume_extractor.py
    postprocessor.py

  scoring/
    __init__.py
    scorer.py

  question_generation/
    __init__.py
    generator.py

  followups/
    __init__.py
    generator.py
```

`pipeline.py` remains the orchestration entrypoint. It imports the four flow packages and keeps the execution order explicit:

```text
parse input -> extract JD/resume -> score -> generate questions -> generate follow-ups
```

This keeps the architecture understandable while making each flow independently explainable.

## Structured Extraction Flow

JD and resume extraction should both use the same shape:

```text
raw text
-> rule-based section split
-> rule-based profile and facts
-> optional LLM postprocessing
-> validated profile and facts
```

Rules stay first because they provide stable provenance and offline fallback. LLM postprocessing should use the configured model, currently expected to be DeepSeek-compatible when the environment is set:

```text
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

The LLM postprocessor must not invent evidence. It can:

- Reclassify a fact into a better section or fact type.
- Merge duplicate facts from the same evidence line.
- Add semantic fields that are supported by existing evidence.
- Add ambiguity or risk notes when information is missing.

It must return data that can be validated by the existing Pydantic schemas. If validation fails or the model is unavailable, the local rule result remains the source of truth.

Resume sections should include the user-facing buckets:

- `education`: 学历背景
- `projects`: 项目经验
- `experience`: 实习经验 / 工作经验
- `skills`: 专业技能
- `summary`: 自我评价 / 个人评价
- `basic`: 基本信息
- `certifications`: 证书资质

Header matching should support plain titles and decorated titles such as `【个人评价】`, `个人评价:`, `教育背景`, `项目经验`, and similar Chinese resume variants.

Skill extraction should still split skills into normalized values for scoring, but the display layer should be able to show the original evidence line once, with compact skill chips underneath.

## Frontend Extraction View

The `结构化提取` tab should move from a flat card list to section groups.

Each section group should show:

- The section label, such as `学历背景` or `项目经验`.
- A concise structured summary when available.
- Evidence-backed facts with line number and extractor.
- Skill values as compact chips rather than repeated large cards.

The view should prioritize coverage across sections before showing many facts from one section. For example, show at least one useful item from education, experience, projects, skills, and summary before filling extra slots.

This directly addresses the current issue where a single skills line produces many repeated `SKILL` cards and hides stronger signals from work or project experience.

## SVG Assets

Create an `assets/` directory at the repo root:

```text
assets/
  structured-extraction-flow.svg
  scoring-flow.svg
  question-generation-flow.svg
  followup-flow.svg
```

The diagrams are documentation assets for README, demo, and interview explanation. They are not loaded by the application at runtime.

Each SVG should show:

- Inputs
- Main processing steps
- Fallback behavior
- Outputs used by the next flow

## Error Handling

File parsing errors continue to become warnings when text fallback exists, and API validation still rejects empty JD or resume input.

LLM failures should not block the demo. The pipeline should append a warning and continue with rule-based extraction.

Invalid LLM postprocessing output should be ignored for that candidate or JD only, preserving the rule-based result.

## Testing

Backend tests should cover:

- Decorated section headers in real sample-style resumes.
- Rule-first extraction still works without an LLM key.
- LLM postprocessing can merge or reclassify facts when valid.
- Invalid LLM output falls back to rule facts.
- Import paths work after the package refactor.

Frontend tests should cover:

- The extraction tab renders grouped sections.
- Repeated skill facts from one evidence line render compactly.
- Project, experience, education, and skill facts are all visible when present.

Verification commands:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
cd frontend && npm test
cd frontend && npm run build
```

After frontend changes, verify the running app in the browser at `http://127.0.0.1:5173/` with a sample JD and resume.
