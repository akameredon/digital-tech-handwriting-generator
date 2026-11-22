# Teacher UI — Experience and Visual Design Specification

**Product:** Ink Flow Handwriting Studio
**Audience:** Nigerian secondary-school teachers (SS1–SS3)  
**Primary goal:** Let a teacher select a curriculum lesson, understand what is available, prepare the note and download a standard printable PDF. The interface must clearly disclose that handwriting conversion is not currently available.

## 1. Product experience principles

- One obvious next action on every screen.
- Use everyday teacher language, not developer terminology.
- Mobile-first, fast on ordinary mobile connections and comfortable on desktop.
- Progressive disclosure: essential choices first; advanced options only when needed.
- Show the selected class, term, week and curriculum topic before the teacher proceeds.
- Distinguish prepared lesson notes from curriculum-only outlines. Never imply that a generated lesson exists when only a prompt or outline is available.
- Make errors recoverable. Preserve the teacher's selections when an API request fails.
- Avoid clutter, dashboards full of numbers, decorative gradients, excessive animation and competing calls to action.
- Accessible by keyboard and assistive technology; target WCAG 2.2 AA.

## 2. Information architecture

Keep the primary navigation intentionally small:

1. **Create lesson** — the main teacher workflow.
2. **Curriculum** — browse SS1, SS2 and SS3 topics by term and week.
3. **Handwriting** — explain that handwriting-to-font export is paused until real recognition and glyph alignment are available.
4. **Help** — short teacher instructions and troubleshooting.

On narrow screens, collapse navigation into a simple menu. Do not introduce a complex admin dashboard or account system unless a real requirement appears.

## 3. Core teacher journey

### Step 1 — Choose a lesson

The home screen opens with the heading **"Prepare your next lesson"**, one short explanation and one primary action.

The selection panel contains:
- Class: SS1, SS2 or SS3.
- Term: First, Second or Third Term.
- Week: the weeks available in the selected curriculum term.
- A curriculum topic preview loaded from the existing `GET /topics` data.

After the class/term/week selection, show the topic title and official content summary. Disable continuation until the selection is valid. Clearly label exam, break, revision and closing weeks.

### Step 2 — Review lesson content

Call the existing `GET /lesson/{class_level}/{term}/{week}` route.

Display:
- Class, term, week and topic.
- Official curriculum content.
- Lesson note in readable sections.
- A visible content-availability status.

Use two honest statuses:
- **Prepared lesson note** — when the response is based on an existing sample note.
- **Curriculum outline** — when the system has only the official topic/content and the fallback outline.

If the teacher needs a fuller note and only an outline is available, offer **"Copy AI prompt"** using the existing `GET /prompt/{class_level}/{term}/{week}` route. Explain that the prompt can be used in an AI tool; do not claim the application itself has called an AI model.

### Step 3 — Printable PDF and handwriting status

The standard browser journey downloads a ruled PDF from `POST /export/lesson-pdf`. The separate experimental worksheet path may return a handwriting-style PDF only after the teacher confirms the worksheet labels. Show a clear loading state, report success only after a PDF response is received, and identify which PDF workflow completed.

Natural-page handwriting-to-font export is unavailable. The interface may offer the experimental, optional generated-worksheet path, but it must state that cell positions label only that sheet and require the teacher to confirm the written character matches each printed label. This confirmation is a self-check, not software verification; do not imply that ordinary notebook pages are recognized. A regular printable PDF must remain available without a worksheet. Enabling natural-page conversion requires a genuine recognizer, verified text-to-image alignment, and real-sample acceptance tests.

### Step 4 — Completion

Show a calm success state with:
- Selected lesson details.
- Download action for the PDF workflow that actually completed: standard ruled output or optional worksheet-based handwriting-style output.
- Start another lesson action.
- A short note explaining where the downloaded file is stored by the browser.

Never show success before the server confirms the operation.

## 4. Wireframe descriptions

### Desktop

- Slim left navigation with product mark and four destinations.
- Main content column with a clear page title and a restrained max-width.
- A small three-step progress indicator for Choose → Review → Export.
- One main white surface/card for the active task.
- Curriculum topic preview adjacent to or directly below the selection controls.
- A persistent, unobtrusive help link.

### Mobile

- Compact top bar with product name and menu.
- Single-column layout with full-width controls and buttons.
- Large touch targets and labels above controls.
- Keep the active step and selected class/term/week visible.
- No horizontal scrolling, tiny text or hover-only interactions.
- Preview and content sections stack vertically.

## 5. Visual design system

Aim for quiet, precise, premium educational software rather than a flashy AI landing page.

- **Typography:** Geist Sans or an equivalent highly legible sans-serif; use a restrained type scale and generous line height.
- **Canvas:** very light neutral background.
- **Surfaces:** white cards, subtle neutral borders, minimal shadows.
- **Primary text:** deep ink/navy for strong readability.
- **Accent:** one confident blue/indigo for primary actions and selected states.
- **Status colors:** use green only for confirmed success, amber for warnings/partial content, red for actionable errors.
- **Spacing:** consistent 4/8-point spacing rhythm; comfortable whitespace.
- **Corners:** moderate, consistent radii; avoid pill-shaped everything.
- **Icons:** consistent Lucide icon set, paired with visible labels for important actions.
- **Motion:** brief and purposeful; respect `prefers-reduced-motion`. Motion must never delay a teacher's task.

## 6. Component inventory

- App shell and responsive navigation.
- Page heading and contextual help.
- Three-step progress indicator.
- Class/term/week selection controls.
- Curriculum topic preview.
- Week type/status badge.
- Lesson content renderer.
- Prepared-note vs curriculum-outline status panel.
- Copy prompt action with copy confirmation.
- Optional worksheet download/upload flow with explicit character-label confirmation and partial-coverage feedback; natural-page recognition remains unavailable.
- Printable-PDF progress and error/retry panel.
- PDF download completion panel.
- Empty, loading, offline and not-found states.

Components must be reusable and typed. Keep API response parsing in a dedicated API client rather than embedding fetch logic in visual components.

## 7. Recommended implementation architecture

- React 19.3 + TypeScript for the interface.
- Vite as the frontend build tool for a focused client-side application.
- Tailwind CSS for design tokens and responsive layout.
- Accessible, composable primitives (Radix/shadcn-style) where they improve consistency.
- Lucide icons.
- CSS transitions for small interactions; no animation framework unless a real interaction requires it.
- Frontend source in `frontend/`; production assets built to a known static output directory.
- FastAPI remains the system of record and serves its existing routes. New API routes are additive adapters around the existing Python pipeline.
- Keep API base configuration environment-driven. Do not hardcode production secrets or expose model keys to the browser.

React's official documentation recommends starting new React apps with a framework for many use cases, while also documenting build-tool approaches for applications with specific constraints. This project already has a Python/FastAPI server and needs a small teacher-facing client, so Vite is a deliberate fit only if the repository's deployment and static-serving audit confirms it. Do not migrate the backend to Next.js.

## 8. Acceptance criteria for Gate 2

- [ ] The teacher's primary journey is documented from start to successful download.
- [ ] All pages and navigation destinations are defined.
- [ ] Desktop and mobile wireframe descriptions are complete.
- [ ] Every primary control has a defined state and outcome.
- [ ] Prepared lesson note and curriculum outline are visibly distinguished.
- [ ] No unavailable AI or PDF functionality is represented as working.
- [ ] Visual tokens and reusable component inventory are documented.
- [ ] Accessibility and responsive acceptance criteria are explicit.
- [ ] Backend integration is additive and existing Python modules remain the source of truth.

## 9. Out of scope for this frontend phase

- Replacing or expanding the curriculum.
- Changing lesson content or the prompt engine.
- Adding a new LLM provider or automatic AI lesson generation.
- Replacing the handwriting or font algorithms.
- User accounts, payments, subscriptions or analytics dashboards.
- Replacing the Python backend with a JavaScript backend.

These can be considered separately only after the core teacher journey is working and verified.
