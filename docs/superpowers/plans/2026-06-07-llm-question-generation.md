# LLM Question Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM-backed interview question generation that creates exactly 10 lightweight questions from both JD and resume context, with the existing rule generator as fallback.

**Architecture:** Keep `RecruitingPipeline` as the deterministic workflow owner. Add a focused question-generation prompt under `backend/prompts/question_generation/`, parse and validate the model JSON in `backend/app/question_generation/generator.py`, then fall back to the current rule generator if LLM output is unavailable or invalid.

**Tech Stack:** FastAPI backend, Pydantic schemas, existing OpenAI-compatible `LLMClient.complete_json`, pytest, React/Vite frontend types.

---

### Task 1: Simplify Question Contract

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/App.tsx`
- Test: `backend/tests/test_scoring_and_generation.py`

- [ ] Update `InterviewQuestion` to keep only `question`, `focus`, and `scoring_criteria`.
- [ ] Update frontend rendering to stop displaying difficulty.
- [ ] Adjust existing tests that asserted `difficulty`.

### Task 2: Add LLM Question Generator

**Files:**
- Create: `backend/prompts/question_generation/interview_questions.md`
- Modify: `backend/app/question_generation/generator.py`
- Test: `backend/tests/test_scoring_and_generation.py`

- [ ] Write tests for exactly 10 questions, 8-9 technical/business questions, 1-2 HR questions, and 6-7 resume-centered questions.
- [ ] Add prompt loading from the separate prompt file.
- [ ] Add input context with JD profile, candidate profile, raw resume text, extracted resume facts, match context, and policy.
- [ ] Parse and validate LLM JSON, dropping invalid payloads.
- [ ] Keep rule fallback available.

### Task 3: Wire Pipeline

**Files:**
- Modify: `backend/app/pipeline.py`
- Test: `backend/tests/test_api_pipeline.py`

- [ ] Pass `self.llm`, raw resume text, and candidate extraction facts into question generation.
- [ ] Mask raw resume PII before including it in the LLM prompt.
- [ ] Add a pipeline test showing the LLM queue includes question generation after matching.

### Task 4: Verification

**Commands:**
- `PYTHONPATH=backend pytest backend/tests/test_scoring_and_generation.py backend/tests/test_api_pipeline.py -q`
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`

- [ ] Run targeted backend tests.
- [ ] Run frontend tests/build after type changes.
- [ ] Report any pre-existing unrelated dirty files separately.
