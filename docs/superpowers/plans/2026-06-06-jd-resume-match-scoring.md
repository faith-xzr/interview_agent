# JD Resume Match Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace coarse match explanations with a requirement-level JD/resume scoring matrix that exposes contribution, evidence, and match gaps.

**Architecture:** Keep the synchronous pipeline shape. Extend backend schemas with requirement-level match details, pass resume extraction facts into scoring, and render the new explainability model in the candidate detail page. Keep risk deductions present but visually secondary.

**Tech Stack:** FastAPI, Pydantic, pytest, React, TypeScript, Vitest.

---

### Task 1: Backend Scoring Contract

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/scoring.py`
- Modify: `backend/app/pipeline.py`
- Test: `backend/tests/test_scoring_and_generation.py`
- Test: `backend/tests/test_api_pipeline.py`

- [ ] **Step 1: Write failing scoring tests**

Add tests that assert `score_candidate` returns requirement matches with dimension, JD text, status, contribution, and evidence.

- [ ] **Step 2: Run backend scoring tests and verify failure**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_scoring_and_generation.py -q`
Expected: failure because `requirement_matches` does not exist yet.

- [ ] **Step 3: Implement schema and scoring support**

Add requirement match and dimension explanation models, update `score_candidate` to accept extraction facts, compute 100-point dimension totals, and produce concise reasons.

- [ ] **Step 4: Run backend tests and verify pass**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_scoring_and_generation.py backend/tests/test_api_pipeline.py -q`
Expected: pass.

### Task 2: Frontend Explainability UI

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/App.test.tsx`

- [ ] **Step 1: Write failing UI test**

Extend the demo report and assert the page shows requirement-level scoring and evidence while risk deduction is secondary.

- [ ] **Step 2: Run App test and verify failure**

Run: `cd frontend && npm test -- --run App.test.tsx`
Expected: failure because the scoring matrix is not rendered yet.

- [ ] **Step 3: Implement UI rendering**

Render dimension summaries and requirement match rows with contribution, status, evidence, and small risk/gap treatment.

- [ ] **Step 4: Run frontend tests and build**

Run: `cd frontend && npm test -- --run App.test.tsx`
Run: `cd frontend && npm run build`
Expected: pass.

### Task 3: End-to-End Verification

**Files:**
- No new files.

- [ ] **Step 1: Run full backend tests**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q`
Expected: pass.

- [ ] **Step 2: Run frontend tests and build**

Run: `cd frontend && npm test`
Run: `cd frontend && npm run build`
Expected: pass.

- [ ] **Step 3: Inspect final diff**

Run: `find backend frontend docs -type f | sort`
Expected: only planned files changed or created.
