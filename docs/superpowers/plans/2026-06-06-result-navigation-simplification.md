# Result Navigation Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the upload result page show only candidate decision and match score, while moving the four core feature details into separate result views.

**Architecture:** Keep the current single React app and API contract. Add a lightweight result-view state in `frontend/src/App.tsx` with tabs for overview, structured extraction, matching score, interview questions, and follow-up simulation. Remove JSON export buttons from the UI.

**Tech Stack:** React, TypeScript, Vite, Vitest.

---

### Task 1: Test The New Result Information Architecture

**Files:**
- Modify: `frontend/src/App.test.tsx`

- [ ] **Step 1: Write the failing test**

Assert that after submission the default result view shows candidate score and decision only, does not show export JSON, and exposes four detail tabs.

- [ ] **Step 2: Verify red**

Run: `cd frontend && npm test -- --run App.test.tsx`
Expected: fail because the current UI still renders all details and export buttons on the result page.

### Task 2: Implement Result Views

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Remove JSON export buttons**

Delete topbar and detail export links.

- [ ] **Step 2: Add result navigation**

Add `activeView` state with `overview`, `extraction`, `matching`, `questions`, and `followups`.

- [ ] **Step 3: Split detail content**

Render candidate score/decision summary in overview, and move extraction, matching, questions, followups into separate views.

- [ ] **Step 4: Verify green**

Run: `cd frontend && npm test -- --run App.test.tsx`
Expected: pass.

### Task 3: Verify

**Files:**
- No new runtime files.

- [ ] **Step 1: Run frontend tests and build**

Run: `cd frontend && npm test`
Run: `cd frontend && npm run build`
Expected: pass.

- [ ] **Step 2: Browser smoke test**

Open `http://127.0.0.1:5173`, submit text JD/resume, verify the default result is concise and detail views switch correctly.
