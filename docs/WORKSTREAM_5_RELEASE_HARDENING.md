# Workstream 5 — release and frontend hardening

## Scope

Workstream 5 strengthens the existing teacher-facing application without changing API contracts or adding a paid service. It covers two low-risk release improvements:

1. **Browser security defaults:** every HTTP response receives `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, a strict cross-origin referrer policy, and a restrictive permissions policy. Existing application headers are preserved rather than overwritten.
2. **Accessibility semantics:** shared navigation buttons explicitly declare their button type, and the lesson progress indicator exposes a labelled list/list-item structure with the active step.

## Verification

- The complete backend test suite covers the header middleware and existing behavior.
- The frontend type-check and production build remain required after every UI change.
- These changes do not configure an HTR provider, download a model, expose credentials, or alter curriculum/API behavior.

## Boundaries

This workstream does not claim WCAG conformance or complete real-device accessibility acceptance. Keyboard-only, screen-reader, contrast, mobile viewport, and browser testing still require execution in representative browsers and devices. Deployment preview, rollback, security review, and explicit production approval also remain release gates.
