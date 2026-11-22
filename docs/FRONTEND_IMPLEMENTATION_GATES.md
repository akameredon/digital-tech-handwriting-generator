# Frontend Design and Release Gates

## Mission

Deliver a calm, exceptionally clear, mobile-first teacher experience for Ink Flow Handwriting Studio. Improve access and usability without replacing or weakening the curriculum, lesson-generation, handwriting-processing, PDF-export, CLI, or FastAPI capabilities already in this repository.

This document is a guarded implementation plan. It does not authorize destructive backend changes.

## Non-negotiable preservation rules

1. Treat the current `main` branch as the protected production baseline.
2. Do not rewrite, rename, delete, migrate, or replace existing curriculum files, lesson content, generation logic, validators, handwriting preprocessing, font compilation, PDF export, CLI commands, API routes, or deployment configuration as part of a UI-only task.
3. Do not introduce a second source of truth for curriculum or lesson content.
4. Do not change API request/response contracts without documenting the need, adding compatibility tests, and obtaining explicit approval.
5. Build on a separate feature branch. Keep changes additive and narrowly scoped. Never force-push or commit directly to `main`.
6. Before implementation, inventory the full repository, existing routes, schemas, tests, dependencies, deployment target, and current behavior. The README alone is not a complete architecture map.
7. If an existing frontend or web interface is discovered, improve it in place rather than creating a competing application.
8. Keep secrets server-side. Never expose API keys or service credentials in browser code.

## Recommended frontend direction

Choose the stack only after the repository audit and deployment constraints are known.

- TypeScript with React; use the existing framework if one is already present.
- If no frontend exists, prefer a stable, currently supported React framework compatible with the hosting setup. Do not adopt a framework merely because it is fashionable.
- Tailwind CSS for a consistent responsive design system.
- Accessible, composable UI primitives (for example, shadcn/ui or an equivalent) rather than a large opaque component framework.
- Lightweight motion only where it clarifies state transitions; respect reduced-motion preferences.
- Use generative AI as a development aid for exploration, copy, and component scaffolding—not as an uncontrolled runtime dependency and not as a reason to change the lesson-generation engine.
- Connect to the existing FastAPI service through a typed API adapter. Preserve existing endpoints and payloads.

## Experience principles

- The teacher should understand the next action immediately.
- Use plain language and familiar labels; avoid technical jargon in the public interface.
- Make the primary journey obvious: choose class → choose term → choose week/topic → review lesson → generate/export.
- Keep advanced options secondary and progressively disclosed.
- Show clear loading, success, empty, validation, and error states.
- Make curriculum coverage and selected lesson details visible before generation.
- Keep generated content readable and editable where the existing backend supports it.
- Explain PDF/handwriting output options before export.
- Design mobile-first, then tablet and desktop. Support keyboard navigation, screen readers, visible focus, sufficient contrast, and WCAG 2.2 AA as the target.
- Never imply that a lesson is officially approved or curriculum-verified unless the existing source data and validation support that claim.

## The five mandatory release gates

A gate is PASS only when its evidence is recorded. A failed or unverified gate blocks progression. "Looks good" is not evidence.

### Gate 1 — Baseline and preservation audit

**Purpose:** Prove that we understand what exists before changing anything.

Checklist:
- [ ] Record the exact base commit and working branch.
- [ ] Inventory the repository tree, runtime, framework, dependencies, entry points, API routes, schemas, data files, tests, CI, and deployment configuration.
- [ ] Identify all protected backend and curriculum paths.
- [ ] Run the existing test suite and record baseline results.
- [ ] Exercise representative existing CLI, API, lesson-generation, validation, and PDF-export flows where runnable.
- [ ] Capture current API contracts and representative request/response fixtures.
- [ ] Identify any existing UI and its current behavior.
- [ ] Document risks and the smallest safe frontend integration point.

**Pass evidence:** An architecture/baseline report, test log, protected-path list, and API contract snapshot. No production files changed.

### Gate 2 — User journey, information architecture, and visual system

**Purpose:** Agree on what teachers see and how they move through it before coding screens.

Checklist:
- [ ] Map the teacher journey from landing page to successful PDF download.
- [ ] Define the minimum navigation and page hierarchy.
- [ ] Produce low-fidelity wireframes for mobile and desktop.
- [ ] Define design tokens: typography, spacing, color, surfaces, borders, radii, elevation, and focus states.
- [ ] Specify reusable components and interaction states.
- [ ] Validate labels and instructions with realistic teacher tasks.
- [ ] Keep optional/advanced controls out of the primary path.
- [ ] Review responsive behavior and accessibility requirements.

**Pass evidence:** Approved journey map, wireframes, component inventory, design tokens, and acceptance criteria for each screen.

### Gate 3 — Isolated frontend implementation and API compatibility

**Purpose:** Build the interface without disturbing the proven core.

Checklist:
- [ ] Implement only the approved frontend scope on the feature branch.
- [ ] Reuse the existing frontend if one exists; otherwise add the smallest compatible frontend surface.
- [ ] Add a typed API client/adapter around existing FastAPI endpoints.
- [ ] Keep curriculum and lesson data owned by the existing backend.
- [ ] Add no duplicate generation logic in the browser.
- [ ] Preserve API payloads and response semantics.
- [ ] Add robust loading, empty, validation, retry, and error states.
- [ ] Keep configuration and secrets out of client bundles.
- [ ] Keep changes additive; document every touched protected boundary.

**Pass evidence:** Reviewable UI implementation, API compatibility tests, dependency diff, and a path-by-path change report.

### Gate 4 — Quality, accessibility, and regression verification

**Purpose:** Prove that the new experience works and the old system still works.

Checklist:
- [ ] Run formatting, linting, type checks, and production build.
- [ ] Run all existing backend tests and all new frontend/API tests.
- [ ] Verify no baseline test regressed.
- [ ] Test the complete teacher journey on narrow mobile, tablet, and desktop viewports.
- [ ] Test keyboard-only navigation, focus order, labels, contrast, screen-reader semantics, and reduced motion.
- [ ] Test slow network, API unavailable, invalid input, empty results, and recoverable errors.
- [ ] Verify generated lesson content and exported PDFs against pre-change fixtures.
- [ ] Check browser console, network failures, bundle size, and security-sensitive configuration.
- [ ] Confirm no curriculum, generated content, or user data was lost or silently transformed.

**Pass evidence:** Green test/build logs, accessibility report, responsive test matrix, before/after regression results, and zero unresolved critical/high-severity defects.

### Gate 5 — Release readiness, rollback, and controlled launch

**Purpose:** Make release reversible and observable.

Checklist:
- [ ] Review the complete diff against the recorded base commit.
- [ ] Confirm only intended files changed.
- [ ] Confirm backend/API compatibility and deployment configuration.
- [ ] Document environment variables without publishing secret values.
- [ ] Verify production build and deployment preview.
- [ ] Run smoke tests against the preview using safe test data.
- [ ] Confirm rollback steps and the known-good baseline commit.
- [ ] Prepare concise teacher-facing usage guidance.
- [ ] Obtain explicit release approval before merging or deploying to production.
- [ ] After release, monitor errors and teacher task completion; keep rollback available.

**Pass evidence:** Signed-off diff review, preview smoke-test report, rollback instructions, deployment record, and explicit release approval.

## Definition of done

The frontend is ready only when all five gates pass. The interface must make the core teacher task obvious, work well on mobile and desktop, remain accessible, and preserve all existing backend behavior. A successful frontend build alone is not a release.

## Suggested initial screen structure

1. **Home:** concise promise, one primary "Create lesson note" action, and a short explanation of the workflow.
2. **Lesson setup:** guided class, term, week/topic selection with visible curriculum context.
3. **Lesson preview:** structured lesson note preview with clear sections and validation feedback.
4. **Handwriting and export:** explain available output choices, preview where supported, then generate/download.
5. **Help:** short teacher guide, troubleshooting, and contact/support information if configured.

Do not implement screens until Gate 1 confirms the real API and repository structure.
