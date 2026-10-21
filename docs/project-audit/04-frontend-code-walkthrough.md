# 04 — Frontend code walkthrough

The frontend is a React 19 single-page application in `frontend/`, written in strict TypeScript (6.0) and built
with Vite 8.

| Concern | Libraries |
|---|---|
| Styling | Tailwind CSS 4 |
| Server state | TanStack Query 5 |
| Routing | React Router 7 |
| Accessible primitives | Radix UI |
| Forms and validation | React Hook Form + Zod |
| Charts | Recharts |
| 3D | React Three Fiber + drei + three.js |
| Animation | Motion |
| Toasts | Sonner |

Exact versions are in `frontend/package.json`.

## 1. Entry point and providers

`frontend/index.html` loads `src/main.tsx` (L1–29), which renders:

```
<StrictMode>
  <QueryClientProvider client={queryClient}>      // shared cache, lib/queries.ts L24–35
    <MotionConfig reducedMotion="user">           // honours the OS "reduce motion" setting
      <Tooltip.Provider>                          // Radix tooltips
        <RouterProvider router={router} />        // src/router.tsx
        <Toaster theme="dark" />                  // sonner notifications
```

`src/styles/index.css` defines the Tailwind 4 design tokens (colours such as `aurora` and `iris`; fonts Space
Grotesk, Inter, JetBrains Mono, self-hosted through Fontsource).

## 2. Routing and protected routes

`src/router.tsx` builds the route table with `createBrowserRouter`. Every page is **lazy-loaded** by `lazyPage`
(L9–22) inside `<Suspense>` with a loading skeleton, so the initial bundle doesn't include 3D or chart code.

| Path | Page | Guard |
|---|---|---|
| `/` | LandingPage | none |
| `/login`, `/register`, `/forgot-password` | AuthPages | `RedirectIfAuthed` (signed-in users go to `/app`) |
| `/reset-password`, `/verify-email` | AuthPages | none (token comes in the URL fragment) |
| `/app/onboarding` | OnboardingPage (outside the app shell) | `RequireAuth` |
| `/app` and children: dashboard, profile, progress, readiness, readiness/model, roles, gaps, simulator, graph, roadmap, mentor, documents, settings | inside `AppShell` | `RequireAuth` |
| `/app/staff` | StaffPage | `RequireAuth roles={["mentor","admin"]}` |
| `/app/admin` | AdminPage | `RequireAuth roles={["admin"]}` |
| `/app/forbidden`, `*` | error pages | — |

`RequireAuth` (`src/components/layout/guards.tsx` L16–27) reads `useMe()` (`GET /auth/me`):

* while loading → splash skeleton;
* not signed in → `/login?next=<current path>`;
* wrong role → `/app/forbidden`;
* a student who hasn't finished onboarding is sent to `/app/onboarding`;
* anyone who has finished, and staff, are sent away from onboarding.

The login page accepts `next` only when it starts with `/app` (`AuthPages.tsx` L63–64), which prevents open
redirects. These guards only improve the user experience; **authorisation is always enforced by the backend**.

## 3. API integration

### `src/lib/api.ts` — the typed client

* `api<T>(path, opts)` (L101–128) calls `fetch` with `credentials: "same-origin"`, so the HttpOnly session cookie is
  sent automatically. JavaScript never sees the session token.
* `headersFor` (L86–95) adds `X-Requested-With: twinpath` and `X-CSRF-Token` (read from the readable CSRF cookie,
  preferring `__Host-tp_csrf`; L47–49) to every non-GET request.
* Errors are normalised from the backend envelope into `ApiError {status, code, message, details, requestId}`
  (L71–84). `fieldErrors` maps validation details onto form fields.
* If the server answers `csrf_invalid`, the client calls `GET /auth/csrf` once and retries (L119–122).
* A network failure becomes `ApiError(0, "network_error", "You appear to be offline…")` (L113–116).
* `download()` (L130–143) fetches a file with the cookie and saves it through a temporary object URL.

### `src/lib/sse.ts` — streaming

`EventSource` can't send a POST body or custom headers, so `postSse` (L11–60) uses `fetch` with a streamed body. It
splits the stream on blank lines (`\n\n`), parses `event:` and `data:` lines, and calls `onEvent(event, json)` for
each frame.

### `src/lib/queries.ts` — server state

* One shared `QueryClient` (L24–35): `staleTime` 30 s, no refetch on window focus, and **no retries for 4xx
  errors** (400/401/403/404/409/422), at most 2 retries otherwise.
* Central query keys `qk` (L37–62) and hooks such as `useMe`, `useProfile`, `useSkills`, `useMatches`,
  `useRoleGaps`, `useRoadmap`, `useMentorStatus`.
* `invalidateTwin()` (L64–74) refreshes everything that depends on the twin (`twin/*`, profile, gaps, roadmap,
  latest readiness, timeline, graph) after any profile change. This is how a skill edit shows up on the dashboard
  without a page reload.

**State management:** there is no global client store (no Redux or Zustand). Server data lives in the TanStack Query
cache; transient UI state lives in component `useState`; the only persisted preference is the 3D on/off choice in
`localStorage` (`src/lib/visuals.ts` L8). Nothing sensitive is stored in the browser.

## 4. Layout and shared components

| Component | File | What it does |
|---|---|---|
| `AppShell` | `components/layout/AppShell.tsx` L139 | Sidebar navigation grouped by area, filtered by role; mentor online/offline indicator; **Send feedback** button; user block with settings and sign-out; mobile drawer (Radix Dialog); skip-to-content link; `<Outlet/>` for pages |
| `PageHeader` | same file L240 | Icon, eyebrow, title, description, actions for every page |
| `Brand` | `components/layout/Brand.tsx` | Logo mark + "AI Career Guidance App" wordmark (kept on one line to fit the 260 px sidebar) |
| UI kit | `components/ui/*.tsx` | `Button` (variants, loading), form controls with label/hint/error wiring (`Field`), `Dialog`, `ConfirmButton` (type-to-confirm for destructive actions), `Tabs`, cards, badges, meters, loading/empty/error states (`ErrorState` shows the request id) |
| `SafeMarkdown` | `components/SafeMarkdown.tsx` L44 | Renders mentor output as React text nodes: paragraphs, lists, bold, code, `[S1]` citation buttons, and **only `https://` links**. No HTML is ever interpreted (ESLint also bans `dangerouslySetInnerHTML`) |
| `FeedbackButton` | `components/FeedbackButton.tsx` L97 | Dialog with area (pre-selected from the current page), 1–5 rating (required), optional comment; `POST /feedback` |
| `PasswordChecklist` | `components/PasswordChecklist.tsx` | Live password rules shared with the Zod schema |

### 3D and its 2D fallbacks

`useCan3D` (`src/lib/visuals.ts` L67) turns 3D off when:

* the user switched it off;
* WebGL is unavailable;
* the OS asks for reduced motion;
* the device reports little memory.

| 3D view (React Three Fiber) | Used on | 2D fallback |
|---|---|---|
| `TwinCore` (`components/three/TwinCore.tsx`) | Dashboard "Your twin" | `CategoryRadar` (Recharts radar) via `TwinVisual.tsx` |
| `SkillConstellation` | Dashboard skill profile | `ConstellationFallback` |
| `Graph3D` (positions computed by the server with NetworkX `spring_layout`, dim=3) | Knowledge graph page | `Graph2D` (keyboard-navigable list/graph, inferred edges dashed) |

## 5. Pages

Each row: what the user sees and does → endpoints → failure behaviour. Endpoints were extracted from the source.

| Page (file) | What the user sees / can do | Endpoints | On failure |
|---|---|---|---|
| Landing (`pages/landing/LandingPage.tsx`, 276 lines) | Product explanation, evidence trust levels, feature cards (incl. the Personalized Mentor), "what the app will never claim", live model info | `GET /readiness/model` | Static content still renders |
| Auth (`pages/auth/AuthPages.tsx`, 319) | Login (+ 6-digit MFA step), registration with consent and live password checklist, forgot/reset password, e-mail verification | `/auth/register`, `/auth/login`, `/auth/login/mfa`, `/auth/password/forgot`, `/auth/password/reset`, `/auth/email/verify` | Field errors from Zod and the server; neutral messages that don't reveal account existence |
| Onboarding (`pages/onboarding/OnboardingPage.tsx`, 335) | 4 steps: academics, goals and target role, quick skill self-assessment (0–4 or skip; skipped = unknown), weekly hours and learning preferences | `PATCH /profile`, `PUT /profile/roles`, `PUT /twin/skills`, `POST /profile/onboarding/complete` | Toast with the server message; stays on the step |
| Dashboard (`pages/dashboard/DashboardPage.tsx`, 222) | Twin visual (3D/2D), completeness ring with hints, readiness card, highest-priority gaps, learning plan, mentor status, recent history, next actions | `useMe`, `useCompleteness`, `useFeatures`, `useLatestReadiness`, `useRoleGaps`, `useRoadmap`, `useMentorStatus`; `POST /readiness/analyse`, `GET /twin/snapshots` | Each card has its own loading/empty/error state |
| Twin profile (`pages/twin/ProfilePage.tsx` + `sections/*`) | Academic form; skills list with estimate source; projects, experience and certifications with skill-evidence links and "request verification"; assessment results and self-reported results; version history with diffs | `/profile`, `/twin/skills/{id}`, `/twin/projects…`, `/twin/experiences…`, `/twin/certifications…`, `/twin/assessments…`, `/twin/verification-requests`, `/twin/snapshots`, `/twin/diff` | Validation errors shown per field; `ConfirmButton` before deletes |
| Progress (`pages/progress/ProgressPage.tsx`) | Readiness over time, skill trajectory by twin version, roadmap activity | `GET /progress/timeline` | "Not enough history yet" empty state |
| Readiness (`pages/readiness/ReadinessPage.tsx`, 207) | Band and rounded probability (only when calibration is validated), warnings (synthetic model, low information, out-of-distribution), SHAP chart, all inputs with contributions, history | `POST /readiness/analyse`, `GET /readiness/history`, `useLatestReadiness` | "Model unavailable" notice; never invents a score |
| Model card (`pages/readiness/ModelCardPage.tsx`) | Target, selection, held-out metrics, calibration, confusion matrix, global attribution, subgroups, leakage checks, limitations, all from the manifest | `GET /readiness/model` | "No active model" state |
| Roles (`pages/roles/RolesPage.tsx`) | Roles ranked against the twin, framework provenance, Monte-Carlo ranking sensitivity; choose target/preferred roles | `useMatches`, `PUT /profile/roles`, `GET /skill-gaps/sensitivity` | Error state with retry |
| Skill gaps (`pages/gaps/SkillGapsPage.tsx`) | Per-role match bounds, priority ranking, sliders for the formula constants (optional weight, unlock/blocking bonus, unknown-gap assumption), filters, skill-by-skill breakdown with prerequisites and actions | `GET /skill-gaps/roles/{id}?…` via `useRoleGaps` | Empty state when filters match nothing |
| Simulator (`pages/simulator/SimulatorPage.tsx`, 320) | Hypothetical inputs (skill levels, projects, internship months, certifications, hackathons, assessments, CGPA, semester), baseline vs hypothetical readiness and role match, changed model inputs, plausibility notes, save/delete scenarios | `POST /simulations/run`, `GET/POST /simulations/scenarios`, `DELETE /simulations/scenarios/{id}` | 422 messages shown (e.g. "earlier semester") |
| Knowledge graph (`pages/graph/GraphPage.tsx`) | 3D or 2D graph filtered by role and node types, provenance legend, insights (blocking prerequisites, resources for top gaps, alternative roles, multi-role unlocks) | `GET /knowledge-graph`, `GET /knowledge-graph/insights` | "Nothing to show" state |
| Roadmap (`pages/roadmap/RoadmapPage.tsx`, 236) | Ordered items with reason, effort range, resource, exercise, completion criteria, weeks; status updates; reordering with up/down buttons; regeneration; staleness banner; plan history and diff; item ratings | `POST /roadmaps/generate`, `GET /roadmaps`, `PATCH /roadmaps/items/{id}`, `PUT /roadmaps/{id}/order`, `GET /roadmaps/{id}/compare/{other}`, `POST /feedback` | Warning when a reorder breaks prerequisites |
| Personalized Mentor (`pages/mentor/MentorPage.tsx`, 235) | Conversation list, suggested questions, streamed answer, sources panel, "check these numbers" notice, removed-link notice, thumbs up/down | `POST /mentor/ask` (SSE), `GET/DELETE /mentor/conversations…`, `POST /feedback`, `useMentorStatus` | "The Personalized Mentor is offline" notice; SSE `error` shown inline; request can be cancelled |
| Documents (`pages/documents/DocumentsPage.tsx`, 219) | Upload a resume (PDF/DOCX/TXT), paste a JD, see extracted skills and suggestions, confirm skills, compare resume with a JD, download, delete | `/documents`, `/documents/job-description`, `/documents/{id}`, `/documents/{id}/download`, `/documents/{id}/confirm-skills`, `/documents/compare` | Server rejection reasons shown (e.g. "Macro-enabled documents are not accepted") |
| Settings (`pages/settings/SettingsPage.tsx`, 223) | Account, e-mail verification, password change, MFA setup by manual secret entry (the secret is shown as grouped text; no QR code is rendered even though the API returns an `otpauth://` URI), sessions with revoke, consents, policy, data export, account deletion (type to confirm), 3D preference | `/auth/*`, `/privacy/*` | Errors as toasts / field errors |
| Mentor tools (`pages/staff/StaffPage.tsx`) | Student picker (linked + consented only), overview with known skills and top gaps, record a verified assessment, verify pending items, assessor readiness label, pending queue | `/staff/*` | 404 if the student isn't accessible |
| Admin (`pages/admin/AdminPage.tsx`, 405) | Tabs: System, Feedback, Users, Mentor links, Roles, Resources, Models, Knowledge base, Audit log | `/admin/*` | Error states; confirmation dialogs for retention, model activation, deletions |

## 6. A user action traced end to end: "Run analysis" on the Readiness page

1. **Click**: `ReadinessPage.tsx` L92–101 defines `run = useMutation({ mutationFn: () => api("/readiness/analyse",
   { method: "POST" }) })`.
2. **Client**: `api()` adds `X-Requested-With: twinpath` and `X-CSRF-Token`; the browser attaches the HttpOnly
   session cookie (`lib/api.ts` L86–112).
3. **Dev proxy or nginx**: in development Vite forwards `/api` to `127.0.0.1:8010` (`vite.config.ts`); in containers
   nginx forwards to `api:8000` (`frontend/nginx.conf`).
4. **Middleware**: Origin and header checks, request id (`backend/app/middleware.py` L74–83).
5. **Dependency**: session lookup by token digest, CSRF digest comparison, RLS subject set
   (`backend/app/deps.py` L79–87).
6. **Handler** `run_readiness` (`backend/app/api/v1/career.py` L144–159):
   * rate limit;
   * `ensure_snapshot` loads the twin, hashes it and inserts a `twin_snapshots` row if it changed, with the 19
     features;
   * `predict(snap.features)` runs the calibrated model and SHAP **in memory**;
   * `store_prediction` inserts into `predictions` (model version id, snapshot id, explanation, warnings, features);
   * commit.
7. **Database**: rows written to `twin_snapshots` (maybe) and `predictions`. The RLS policy `predictions_owner`
   checks `user_id = current_setting('app.user_id')`.
8. **Response**: JSON with `band`, `band_label`, `probability` (rounded to 5%, only if calibration is validated),
   `explanation`, `summary`, `warnings`, `limitations`, `prediction_id`, `snapshot_version`.
9. **UI update**: `onSuccess` stores the result, warns if the model is unavailable, invalidates `["readiness"]` and
   the twin queries, so the history list and dashboard refresh. `ShapChart` renders contributions; warnings render
   as `Notice`s; `SyntheticModelNotice` is always shown for the synthetic model.
10. **Failure**: any `ApiError` becomes a toast with the server's message (L100). A 503 from a database outage shows
    "The database is temporarily unavailable."

## 7. Forms and validation

* React Hook Form + Zod on the auth pages (password schema shared with `PasswordChecklist`) and the main forms.
  Client validation runs first; the server always re-validates (Pydantic `StrictModel`).
* Field errors from the server (`details[].field`) are mapped back to inputs through `ApiError.fieldErrors`.
* Destructive actions use `ConfirmButton` (`components/ui/overlay.tsx` L57). Account deletion additionally requires
  the password and typing `DELETE MY ACCOUNT`.

## 8. Accessibility and responsive design

| Measure | Evidence |
|---|---|
| Skip-to-content link is the first focusable element | `AppShell.tsx`; e2e test `keyboard: skip link…` (desktop **and** mobile) |
| Labelled controls (`Field` wires `htmlFor`, `aria-describedby`, `aria-invalid`) | `components/ui/form.tsx` L37–74 |
| Radix primitives for focus trapping and ARIA in dialogs, tabs, tooltips | `components/ui/overlay.tsx` |
| Rating buttons with descriptive `aria-label`s (e.g. "4 – Useful") | `FeedbackButton.tsx`, `OnboardingPage.tsx` |
| Automated axe checks (colour contrast excluded in jsdom) | `src/test/utils.tsx` `axeViolations`; used in `auth.test.tsx`, `FeedbackButton.test.tsx` |
| Reduced motion respected | `MotionConfig reducedMotion="user"` (`main.tsx`), `useCan3D` |
| 2D alternatives for every 3D scene; keyboard-operable graph | §4, `components.test.tsx` "lets keyboard users select nodes…" |
| Mobile layout without horizontal overflow | e2e mobile project (Pixel 7) asserts overflow ≤ 1 px |

**Not verified:** a full manual screen-reader audit, and colour-contrast measurement in a real browser (jsdom can't
compute contrast).

## 9. Frontend tests

| File | Tests | What they check |
|---|---|---|
| `src/lib/api.test.ts` | 5 | CSRF headers only on unsafe methods, error envelope, single CSRF retry, offline errors, `__Host-` cookie preference |
| `src/lib/visuals.test.tsx` | 2 | 2D fallback without WebGL; user preference |
| `src/components/components.test.tsx` | 9 | SafeMarkdown never interprets HTML and renders only https links; unknown ≠ 0 in the level meter; states; password checklist; Graph2D keyboard selection and dashed inferred edges |
| `src/components/layout/guards.test.tsx` | 3 | Onboarding redirects for students and staff |
| `src/components/FeedbackButton.test.tsx` | 1 | Required rating, page-derived area, request body, accessible dialog |
| `src/pages/auth/auth.test.tsx` | 6 | Client validation before any request, neutral messages, server errors, MFA step, axe on login and register |
| `e2e/student-journey.spec.ts` (Playwright) | 5 scenarios / 6 runs | Real browser against a running stack: registration → onboarding → dashboard; twin evidence, gaps, readiness, simulation, roadmap; CSRF rejection; keyboard skip link on desktop and mobile; account deletion |

**Audit run (2026-10-21):** Vitest 26/26 passed; Playwright 6/6 against the dev servers and 6/6 against the
containers; ESLint and `tsc` clean.
