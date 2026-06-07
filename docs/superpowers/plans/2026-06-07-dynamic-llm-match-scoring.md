# Dynamic LLM Match Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build LLM-first dynamic matching that turns extracted JD facts into a per-JD scoring rubric, scores candidate facts against every rubric item, and falls back to the existing rule scorer when LLM scoring is unavailable or invalid.

**Architecture:** Add a focused LLM scorer beside the existing deterministic scorer. The LLM scorer owns rubric generation, requirement matching, result validation, and conversion back into the existing `MatchReport` shape so the frontend can keep rendering dynamic `RequirementMatch` rows. `RecruitingPipeline` calls the LLM scorer with JD facts, candidate facts, and evidence snippets, then falls back to `score_candidate` when needed.

**Tech Stack:** FastAPI backend, Pydantic schemas, pytest, existing OpenAI-compatible `LLMClient.complete_json`, Markdown prompt templates under `backend/prompts`.

---

### Task 1: Add Dynamic Rubric Models And Unit Tests

**Files:**
- Create: `backend/tests/test_llm_scoring.py`
- Create: `backend/app/scoring/llm_scorer.py`

- [x] **Step 1: Write a failing test for JD-fact-driven rubric generation**

Add `test_generate_scoring_rubric_uses_jd_facts_and_normalizes_to_100` in `backend/tests/test_llm_scoring.py`. The test uses a fake LLM payload with JD-specific AIGC requirements and asserts the returned rubric keeps those requirements and sums max scores to 100.

- [x] **Step 2: Run the focused test and confirm it fails**

Run: `PYTHONPATH=backend pytest backend/tests/test_llm_scoring.py::test_generate_scoring_rubric_uses_jd_facts_and_normalizes_to_100 -q`

Expected: import failure or missing function failure for `generate_scoring_rubric`.

- [x] **Step 3: Implement minimal rubric parsing and normalization**

Create `ScoringRubricItem`, `ScoringRubric`, and `generate_scoring_rubric(...)` in `backend/app/scoring/llm_scorer.py`. Read prompt content from `backend/prompts/matching/rubric_generation.md`, call `llm.complete_json(...)`, validate items, clamp scores, and normalize total `max_score` to 100.

- [x] **Step 4: Run the focused test and confirm it passes**

Run: `PYTHONPATH=backend pytest backend/tests/test_llm_scoring.py::test_generate_scoring_rubric_uses_jd_facts_and_normalizes_to_100 -q`

Expected: one passing test.

### Task 2: Add Requirement Matching And MatchReport Conversion

**Files:**
- Modify: `backend/tests/test_llm_scoring.py`
- Modify: `backend/app/scoring/llm_scorer.py`
- Create: `backend/prompts/matching/rubric_generation.md`
- Create: `backend/prompts/matching/requirement_matching.md`

- [x] **Step 1: Write failing tests for matching all rubric dimensions**

Add `test_score_candidate_with_llm_matches_all_dynamic_requirements` and `test_score_candidate_with_llm_rejects_invalid_payload` in `backend/tests/test_llm_scoring.py`. The first test asserts AIGC tool, content-production, and SOP requirements can all appear as dynamic rows with custom max scores. The second asserts invalid totals or missing matches return `None`.

- [x] **Step 2: Run the tests and confirm they fail**

Run: `PYTHONPATH=backend pytest backend/tests/test_llm_scoring.py -q`

Expected: failures because `score_candidate_with_llm` is missing or incomplete.

- [x] **Step 3: Implement matching and report conversion**

Add `score_candidate_with_llm(...)` that generates a rubric, calls the matching prompt, validates every rubric item has a match, clamps `status`, `confidence`, and `contribution`, converts cited evidence indexes to `EvidenceSnippet`, builds `dimension_explanations`, `dimension_scores`, `score_breakdown`, `match_reasons`, `gap_reasons`, and returns a `MatchReport`.

- [x] **Step 4: Run the tests and confirm they pass**

Run: `PYTHONPATH=backend pytest backend/tests/test_llm_scoring.py -q`

Expected: all tests in the new file pass.

### Task 3: Wire Pipeline With Rule Fallback

**Files:**
- Modify: `backend/app/pipeline.py`
- Modify: `backend/app/scoring/__init__.py`
- Modify: `backend/tests/test_api_pipeline.py`

- [x] **Step 1: Write a failing pipeline test**

Add `test_pipeline_uses_llm_dynamic_match_scoring_when_available` to `backend/tests/test_api_pipeline.py`. The fake LLM queue should include JD extraction, resume extraction, rubric generation, and requirement matching payloads. Assert the report contains dynamic AIGC requirements and custom scores.

- [x] **Step 2: Run the focused pipeline test and confirm it fails**

Run: `PYTHONPATH=backend pytest backend/tests/test_api_pipeline.py::test_pipeline_uses_llm_dynamic_match_scoring_when_available -q`

Expected: failure because pipeline still calls only `score_candidate`.

- [x] **Step 3: Wire LLM scorer into `RecruitingPipeline.run`**

Call `score_candidate_with_llm(...)` after evidence retrieval. If it returns `None`, call the existing `score_candidate(...)`. Pass `jd_extraction_facts` and candidate `extraction_facts` into the LLM scorer.

- [x] **Step 4: Run backend tests**

Run: `PYTHONPATH=backend pytest backend/tests/test_llm_scoring.py backend/tests/test_api_pipeline.py backend/tests/test_scoring_and_generation.py -q`

Expected: all selected backend tests pass.

### Task 4: Verify Frontend Compatibility

**Files:**
- Modify only if tests reveal a type or rendering issue: `frontend/src/types.ts`, `frontend/src/App.tsx`

- [x] **Step 1: Run frontend tests**

Run: `npm --prefix frontend test -- --run`

Expected: existing frontend tests pass because output schema remains compatible.

- [x] **Step 2: Inspect final diff**

Run: `git diff --stat` and `git diff -- backend/app backend/tests backend/prompts docs/superpowers/plans/2026-06-07-dynamic-llm-match-scoring.md`

Expected: diff contains dynamic scoring files, prompts, tests, and pipeline wiring only.

### Self-Review

- Spec coverage: dynamic JD requirement dimensions, LLM rubric, LLM matching, prompt separation, persistence through existing `RunReport`, and rule fallback are covered.
- Placeholder scan: no implementation step relies on unspecified future work.
- Type consistency: new scorer returns existing `MatchReport`; pipeline keeps the same public API response shape.
