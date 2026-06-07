# Remove Match Decision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the premature advance/not-advance conclusion from matching results while keeping scores, evidence, and gaps useful.

**Architecture:** Keep the existing pipeline and report shape. Make `decision` an empty compatibility field from the backend, and update the React UI so candidate summaries show score plus either positive match evidence or gap reasons, without rendering advance decision pills.

**Tech Stack:** FastAPI, Pydantic, pytest, React, TypeScript, Vitest.

---

### Task 1: Backend Scoring Contract

**Files:**
- Modify: `backend/tests/test_scoring_and_generation.py`
- Modify: `backend/tests/test_api_pipeline.py`
- Modify: `backend/app/scoring/scorer.py`

- [x] **Step 1: Write failing backend tests**

Update scoring and API tests to assert `decision` is blank while `total_score`, `match_reasons`, and `gap_reasons` remain available.

- [x] **Step 2: Run backend tests to verify failure**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_scoring_and_generation.py backend/tests/test_api_pipeline.py -q`

Expected: failure because `score_candidate` still returns `推荐推进` or `暂不推进`.

- [x] **Step 3: Remove backend decision classification**

Change `score_candidate` to return `decision=""` and remove the private `_decision` threshold function.

- [x] **Step 4: Run backend tests to verify pass**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_scoring_and_generation.py backend/tests/test_api_pipeline.py -q`

Expected: pass.

### Task 2: Frontend Summary UI

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [x] **Step 1: Write failing frontend tests**

Update the app test data to include one high-score and one low-score candidate. Assert overview and ranking views do not show decision labels, high-score rows show match reasons, and low-score rows show gap reasons.

- [x] **Step 2: Run frontend test to verify failure**

Run: `cd frontend && npm test -- --run App.test.tsx`

Expected: failure because the UI still renders decision labels and always uses `match_reasons[0]`.

- [x] **Step 3: Implement frontend summary helpers**

Add helper functions to choose candidate summary text and hide blank decisions from summary/detail headers.

- [x] **Step 4: Run frontend test to verify pass**

Run: `cd frontend && npm test -- --run App.test.tsx`

Expected: pass.

### Task 3: Verification

**Files:**
- No new files.

- [x] **Step 1: Run backend tests**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q`

Expected: pass.

- [x] **Step 2: Run frontend tests and build**

Run: `cd frontend && npm test`

Run: `cd frontend && npm run build`

Expected: pass.
