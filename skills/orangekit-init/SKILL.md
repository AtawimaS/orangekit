---
name: orangekit-init
description: Sets up ORANGEKIT Devkit in a project for the first time — a tech-stack interview (frontend, backend, DB), creation of orangekit.config.json and CLAUDE.md, and installation of the stack rule cards. Use when setting up a new project for the first time or when choosing the stack configuration again. Manual invocation only.
disable-model-invocation: true
---

# /orangekit-init — ORANGEKIT project initial setup

## Purpose
Creates `orangekit.config.json` and `CLAUDE.md` at the project root and initializes the `dev/` structure. An existing `CLAUDE.md` is overwritten only after Step 1 confirms whether to back it up.

## Procedure

### Step 0: Measure the repo once (before asking — to cut down what you ask)

**Read before you ask** — asking about things you could have found out is where most of the interview
time goes. Pre-fill the defaults for Steps 2, 4, 4.5 and 4.7:

```bash
ls -a                                   # existing code · toolchain traces
cat package.json 2>/dev/null            # framework · packageManager · scripts · deps
cat pyproject.toml requirements.txt 2>/dev/null
ls pnpm-lock.yaml yarn.lock package-lock.json bun.lockb uv.lock poetry.lock 2>/dev/null
ls src app packages services apps 2>/dev/null   # sourceDir · repoTopology
ls app.json pubspec.yaml ios android Cargo.toml 2>/dev/null   # app axis (Expo · Flutter · native) · Rust backend
cat tsconfig.json 2>/dev/null | head -20        # importAlias · strict
git remote get-url origin 2>/dev/null           # vcsPlatform — github.com / gitlab.com
```

What measurement settles: name · framework · language · package manager · build/test/lint commands · source directory · importAlias · repo topology · backend axis (inferred from deps) · code hosting.

If the remote URL contains `github.com`, **settle on** `github`; if `gitlab.com`, `gitlab`
— do not ask. Only ask in the third call when it is self-hosted or there is no remote to decide from.
**A new empty project has nothing to measure, so the preset defaults take that place.**

### Step 0.5: Environment check — `jq`

**Read `assets/preflight-jq.md` at this step and follow it exactly.** If `jq` is present, move on to Step 1 without saying anything; if missing, ask whether to install it, but a refusal or failure does not block initialization.

### Step 1: Check for existing configuration

Check whether these files exist at the project root:
- `orangekit.config.json` — if present, confirm: "Already configured. Reconfigure?"
- `CLAUDE.md` — if present, confirm whether to back up and overwrite

### Interview protocol — only pull forward answers that change a later question's list

Steps 2, 4, 4.5 and 4.7 originally had 3 mandatory waits plus 5 conditional ones. The Step 0 measurement fills
most of them, so **ask only about what is left, in batches.** Asking one at a time is what spends the most of a person's time.

The batching rule is **dependency, not count**. `AskUserQuestion` collects the answers of one call
**simultaneously**, so an earlier answer that **changes a later question's option list cannot go in
the same call.** The tool's limits are **4 questions · 4 options** (the tool attaches the free-input field separately).

| Call | Questions batched | Why this order |
| --- | --- | --- |
| **1st — what are you building** | ① product form ② backend type ③ response language ④ experience level | ① splits the screen questions, ② splits the backend detail |
| **2nd — which approach** | ⑤ web framework (① = web) or app approach (① = mobile app) ⑥ backend detail (filtered by ②) ⑦ PWA or not (only when ① = web) ⑧ repo topology | can only be asked once the lists are settled |
| **3rd — built with what** (conditional) | ⑨ the per-approach app question (for hybrid, two: web screens + app shell) ⑩ TypeScript server framework (⑥ = TypeScript) ⑪ deployment target (for a self-hosted server) | ⑨ depends on ⑤, ⑩⑪ depend on ⑥. ⑪ is discarded if ⑩ is `aws-container` — what branches is **whether the question exists**, not a list, so it rides in the same call and its answer is ignored |
| **4th — what is left** (conditional) | auth method (Step 4.5) · empty dimensions of a custom axis (DB · ORM · commands) · code hosting (when Step 0 failed to decide — `github` · `gitlab`) · whatever measurement missed (name · app directories) | you only know what is empty once the earlier answers are in |

- **When a measured value exists, put it first as the default option** — most of the time the user just confirms and moves on
- **Do not make the 3rd or 4th call if there is nothing to fill.** Web + BaaS takes 2 calls; hybrid + a self-hosted server takes 3–4
- If one call would exceed 4 questions, load **the questions that change a list first** and push the rest to the next call
- **Language (TypeScript/JavaScript) is not asked separately** — it stays at the preset default and is changed in the Step 4.9 confirmation summary
- Ask only questions whose answers branch. Implementation details like "should we use the pre-built one or generate?" are not asked
- Ask the first question **in product terms** ("what are you building", not "pick a frontend")

### Rules shared by every option list — custom · not sure

**Read `assets/interview-choices.md` at this point** — the pack normalization of custom input, the handling of "Not sure", and the table of deciding questions are there. "Not sure" adds one more question, "Get a recommendation" / "Decide later", to the next call; "Decide later" is recorded as `undecided` in `presets.<axis>`, and custom input that matches no pack is recorded as `custom`. If ① is "Mobile app", `clientKind` is settled as `app`.

### Step 2: Preset selection (interactive)

A stack is made of **three axes** — web screens (`frontend`) · app (`app`) · backend (`backend`) — with
**dimensions** that are not axes layered on top (product form · app shell · language · deployment target). Axes pick the pack;
dimensions turn that pack's **conditional slots** on and off.

```
① What are you building — this choice sets the lists for the later questions:
  1. Web         — reached through a browser. No install
  2. Mobile app  — an app installed from a store (including hybrid, which puts web screens inside an app)
  3. API only    — no user-facing screens
  4. Not sure
```

① splits not just the screen list but, through `deliveryModel` and its derived value `clientKind`, **the slots of the backend and infrastructure guides** too — it is information that is unreachable unless you ask (slot table below).

```
⑤ What do you build the screens with:   ← ① splits the question itself

  ▸ If ① is "Web" — web framework:
    1. nextjs      — Next.js App Router + React + Tailwind v4 + shadcn/ui + Zustand
    2. react-vite  — React + Vite SPA (no SSR) + Tailwind + React Router + TanStack Query + Zustand
    3. vue         — Vue 3 Composition API + Vite SPA (no SSR) + Tailwind + Vue Router + Pinia
    4. Not sure
    (vanilla — standard DOM + ES modules — and any other framework go through custom. A matching name is recognized as its pack)
    + ⑦ Also ship it as a PWA (installable web) — service worker · offline cache · install prompt

  ▸ If ① is "Mobile app" — how do you build the app:
    1. Hybrid          — most screens are built for the web and put inside an app shell. A web version can ship too
    2. Cross-platform  — one codebase draws native iOS and Android screens
    3. Fully native    — iOS (Swift) and Android (Kotlin) are each built separately
    4. Not sure

  ▸ If ① is "API only" — do not ask. Every screen axis is `none`

⑨ (3rd call) one more per app approach:

  ▸ Hybrid — load both questions into the same call (neither changes the other's list):
    Web screens:  1. react-vite (recommended)  2. vue  3. nextjs (static-export constraint — see the conflict warning below)  4. Not sure
    App shell:
      1. Capacitor                — almost no shell code. Native features are called through plugins
      2. RN webview shell         — React Native wraps a webview. RN handles only the bridge · push · permissions
      3. RN shell + native screens — some screens, like maps and camera, are drawn directly in RN
      4. Not sure

  ▸ Cross-platform:  1. react-native (Expo)  2. flutter  3. Not sure
                     (Kotlin Multiplatform · .NET MAUI and the like go through custom)

  ▸ Fully native:  1. iOS + Android (native-dual)  2. iOS only (ios-swift)  3. Android only (android-kotlin)  4. Not sure
                   The default UI toolkits are SwiftUI · Jetpack Compose — for UIKit or the View system, change it in the confirmation summary
```

**How a choice reaches the config** — this table is canonical. After "Hybrid" is picked, do not ask again "web or
native?": hybrid is the form that uses **the web screen axis and the app axis together**, and the app
shell question settles whether the app axis exists.

| Choice | `deliveryModel` | `appShell` | `presets.frontend` | `presets.app` |
| --- | --- | --- | --- | --- |
| Web | `web` | — | web framework | `none` |
| Hybrid + Capacitor | `hybrid` | `capacitor` | web screens | `none` (the frontend-guide shell slot covers it) |
| Hybrid + RN webview shell | `hybrid` | `rn-webview` | web screens | `react-native` |
| Hybrid + RN shell + native screens | `hybrid` | `rn-native-screens` | web screens | `react-native` |
| Cross-platform | `cross-platform` | — | `none` | `react-native` · `flutter` |
| Fully native | `native` | — | `none` | `ios-swift` · `android-kotlin` · `native-dual` |
| API only | `api-only` | — | `none` | `none` |
| Mobile app + approach left undecided | (not written) — **`clientKind` is `app`** | — | `undecided` | `undecided` |
| Hybrid + shell left undecided | `hybrid` | `""` | web screens | `undecided` |
| Hybrid + custom shell (Ionic · an in-house WebView, etc.) | `hybrid` | `custom` | web screens | `custom` if the shell has code, otherwise `none` |
| Cross-platform · native + custom (KMP · .NET MAUI, etc.) | `cross-platform` · `native` | — | `none` | `custom` |
| Cross-platform · native + left undecided | `cross-platform` · `native` | — | `none` | `undecided` |

- When `presets.app` is not `none`, write a **human-readable summary** into `techStack.nativeStack`
  (e.g. "Expo React Native — WebView shell + native screens (maps · camera)")
- If a cross-platform or native product **also has a separate web (an admin screen, etc.)**, fill `presets.frontend` in the
  confirmation summary — it surfaces when Step 4.7 takes the monorepo's app list

```
② Pick a backend type — **these are not three interchangeable names but three different shapes**:
  1. BaaS            — the vendor supplies DB, auth and storage together. There is a policy engine in the data layer
  2. Serverless assembly — you compose managed services yourself. **There may be no row-level policy engine**,
                     so the application layer carries more of the checking
  3. Self-hosted server  — you run a resident server. The application layer is the only boundary
  4. None · undecided

⑥ (2nd call) detail:
  ↳ BaaS — which vendor:
      1. supabase  — PostgreSQL + RLS + Auth + Storage + Realtime
      2. firebase  — Firestore + Auth + Storage + Cloud Functions
      3. Not sure

  ↳ Serverless assembly — the cloud is the runtime model:
      1. aws-serverless  — Lambda + API Gateway + DynamoDB + Cognito
      2. gcp-serverless  — Cloud Run/Functions + Firestore + Identity Platform
      3. Not sure

  ↳ Self-hosted server — **pick the language first** (it is where the toolchain splits):
      1. TypeScript  — the framework is picked in the 3rd call
      2. Python      — fastapi: FastAPI + SQLAlchemy + Pydantic + Alembic
      3. Rust        — rust-axum: Axum + Tokio + SQLx + PostgreSQL
      4. Not sure
      (Java · Go · C# and the like go through custom)

  ↳ None · undecided:
      1. No backend — a static site, or it only consumes an external REST API → `none`
      2. Get a recommendation
      3. Decide later → `undecided`

⑩ (3rd call) Self-hosted server · TypeScript — framework:
      1. fastify        — Fastify + PostgreSQL + Drizzle + Zod
      2. node-nest      — NestJS + PostgreSQL + TypeORM + class-validator
                          (modules, DI and decorators set the structure — it is not a variant of Express)
      3. node-api       — Express + PostgreSQL + Prisma
      4. aws-container  — Hono + Drizzle · ECS/Fargate + RDS PostgreSQL + Cognito
                          (a finished product including the AWS infrastructure. AWS coupling stays in the infrastructure layer only)
      (the options are full — someone who knows only "TypeScript" writes "recommend" in the custom field)

⑪ (3rd call) Deployment target — for a self-hosted server that is not `aws-container`:
      1. Undecided / cloud-agnostic (default) — the same guide wherever you deploy
      2. AWS                          — ECS/Fargate · EC2, etc.
      3. Custom                       — GCP · Azure · Vercel · on-premises
```

`fastapi` (Python) and `rust-axum` (Rust) split the toolchain from the web screen axis, so take per-axis commands separately (Step 4). `rust-axum` has no pre-built pack and takes the generation path — it is on the list because it is a common choice.

**Record the product form in `techStack.deliveryModel`** (`web` · `hybrid` · `cross-platform` · `native` · `api-only`).
For "Web" also fill `techStack.pwa`; for "Hybrid" fill `techStack.appShell`.
And **write the derived value into the config alongside it**:

> `clientKind = (deliveryModel === 'web') ? 'browser' : 'app'`

If each pack re-derives it on its own the descriptions diverge, so **decide it in one place and let
the packs read only this value.** Hybrid, cross-platform and native are all "an app talking to an API" from the backend's point of view.

| Slot | `browser` | `app` |
| --- | --- | --- |
| Client auth transport | cookie session · CORS · CSRF defense | **Bearer + secure storage** (not cookies) |
| Idempotent ingest | empty | **alive** — offline batch sync is assumed |
| Push delivery | empty | alive (FCM/APNs) |
| API version negotiation | empty | alive — old app versions keep running |

An empty slot is the normal path — a web project's backend guide having no push section is not a defect.

> **Conflict warning — "Hybrid" × `nextjs`**: an app shell carries static assets, so
> `output: 'export'` is forced and **Server Actions and Route Handlers cannot be used.** When this
> combination comes up, tell the user and offer the choice of ⓐ switching to `react-vite` or
> ⓑ using Next.js as a static export while moving the server features to the backend axis. **Without
> asking for the product form there is no way to detect this conflict.**

**Record the deployment target in `techStack.backend.cloudProvider`** — not a new field but a
dimension already in the schema (`null` when "undecided"). When this value is empty a cloud-agnostic
guide ships; when it is filled, Step 4.5 and Step 9.5 treat that cloud's infrastructure guidance as a requirement.

> **Why ask for the type first** — `aws-container` (Hono) and `aws-serverless` (Lambda) share only the cloud;
> the frameworks differ. Treating the cloud as a freely combinable axis makes combinations explode (`docs/presets.md`),
> so **infrastructure is an independent dimension only in the resident-server family** — for serverless and BaaS the cloud is the architecture.

Language and product form are dimensions, not presets — a pack must hold for any combination of dimensions, and specialization happens at generation time.

> **Why several axes**: guide content is a function of the combination — the same Supabase centers on Route Handlers
> and Server Actions with Next.js, and on Edge Functions with React+Vite. The app axis is separate from the web screen axis
> because in a hybrid the two live in one product. The only app axis pack is `react-native` (something is pre-built
> only when it can be registered as an audit target); the other app values take the generation path.

`frontend: none` is the result of choosing "API only" in ① or of building only a cross-platform or native app —
it is a consequence of the product form, not an option on the web screen axis, so it is not asked in ⑤. A combination
where the screen axes and the backend are all `none` corresponds to the former `blank` preset.

### Step 3: Load preset defaults (merge)

Read four files and merge them in this order (later overrides earlier). **If an axis value is `none` · `custom` · `undecided`,
that axis has no file** — skip it without reading:

1. `${CLAUDE_PLUGIN_ROOT}/presets/base.json` — shared domains · security patterns
2. `${CLAUDE_PLUGIN_ROOT}/presets/frontend/<choice>.json`
3. `${CLAUDE_PLUGIN_ROOT}/presets/app/<choice>.json` — fills `techStack.app`
4. `${CLAUDE_PLUGIN_ROOT}/presets/backend/<choice>.json`

Merge rules:

- `additionalStack` is **accumulated**, not overwritten
- `native-dual` has two codebases — the preset `sourceDir` is `ios`, and `android` is taken alongside it in Step 4.7
  and **both** go into the Step 7.5 card `paths:`
- `domains.sourceDir` takes the first value present in the order web screen axis → app axis → backend axis.
  If two or more exist and the values differ, confirm with the user — in a monorepo the Step 4.7 app directories are the answer
- If the app preset's `fits` does not include the chosen app approach (e.g. `flutter` for a hybrid shell), point out that
  combination and have the user pick again — for a shell, only the RN family uses an app-axis pack
- Each preset's `notes` is not written into the config — in Step 9.5 it is **passed to the guide
  generation agent as combination context** (the basis for making a guide that accounts for both axes)

### Step 4: Collect project information (interactive)

Ask the user for the following (show the preset default where one exists):

1. **Project name** (required)
2. **Response language** — 4 options + "Other" (the free input `AskUserQuestion` provides automatically)

   | Display | `language` | `languageLabel` |
   | --- | --- | --- |
   | 한국어 | `ko` | `한국어` |
   | English | `en` | `English` |
   | Bahasa Indonesia | `id` | `Bahasa Indonesia` |
   | Tiếng Việt | `vi` | `Tiếng Việt` |
   | Other (free input) | the BCP-47 tag for the input | that language's **endonym** (its own name for itself) |

   A value that arrives through "Other" is normalized by the model — "Thai" · "ภาษาไทย" → `th` / `ภาษาไทย`.
   If the tag cannot be settled, leave `language` empty and fill only `languageLabel`.
   **Write both values into the config.** `session-brief.sh` reads them to substitute
   `{{RESPONSE_LANGUAGE}}` in the T0 operating rules — if they are not written here the language choice never arrives.

   All this choice settles is the **final output language**. Analysis and reasoning are always in
   English, and technical terms that are standard in English across the industry (`Bottom Sheet` ·
   `GNB` · `middleware`) stay in English whichever language is chosen — the canonical source for this norm is T0.
3. **Experience level** — senior / mid / junior (default: senior)
4. **Framework, language and package manager per axis** (confirm the merged preset defaults)
5. **Build/test/lint commands** (confirm the preset defaults)
6. **Source directory** (confirm the result of the Step 3 merge rules)
7. **Shared package path** (required for `monorepo` and `msa` — see Step 4.7. Skipped for `single`)

**With two or more axes, take commands per axis** — even with the same toolchain (TypeScript web + TypeScript API),
different directories mean different commands. Combinations whose toolchains split (react-vite + fastapi, + rust-axum,
+ flutter, etc.) all the more so. Then confirm the **project-level commands** (`techStack.commands`)
on their own — build-gate and health-check read those values, so they must be filled.
In a monorepo the project-level command is often a root script that runs every axis together. If the project-level command
runs only one axis, **build-gate never verifies the other axes even once** — note that fact in the confirmation summary.

### Step 4.5: Fill the backend's undecided dimensions

The backend **type** was already settled in Step 2 — do not ask again here. Fill only the dimensions
the chosen backend preset left empty:

| Backend axis | Already settled | What to ask here |
| --- | --- | --- |
| `supabase` | backendType · database · dataAccess · auth, all of them | nothing — show and confirm |
| `fastapi` | backendType · database · dataAccess | **auth method** (self-issued JWT · OAuth provider · session) · hosting (optional) |
| `node-api` | backendType · database · framework (Express) · ORM (Prisma) | **auth method**. The framework and ORM are nailed down by the pack — anything else is `node-nest` or the generation path |
| `node-nest` | backendType · database · framework (NestJS) · ORM (TypeORM) · validation (class-validator) | **auth method**. Whether the guard reads a session cookie or a bearer token is a function of the frontend axis |
| `aws-container` | defaults for every dimension | nothing — show and confirm. Changing the defaults (RDS PostgreSQL · Drizzle · Cognito) leaves the pre-built set and takes the generation path |
| `aws-serverless` · `gcp-serverless` | defaults for every dimension | any dimension where a different service is used (e.g. DynamoDB→RDS) |
| `fastify` | backendType · database · framework (Fastify) · ORM (Drizzle) | **auth method**. The pack pins the framework and ORM — a different ORM such as Prisma takes the generation path |
| `rust-axum` | backendType · database · framework (Axum) · data access (SQLx) | **auth method**. There is no pre-built pack — generation path |
| `firebase` | every dimension | nothing — show and confirm |
| `custom` | the entered framework name | **DB · data access (ORM) · auth method · commands · language** — the preset fills nothing in |
| `undecided` | — | nothing. Note in the confirmation summary that it is undecided |
| `none` | — | if an external API is used, its auth method (where the token is kept is the security point) |

If a request comes up to switch to a combination outside the presets (MongoDB · Prisma · Cognito, etc.), take
the dimensions on the spot and record them in `techStack.backend` — a preset is a starting point, not a ceiling.
In that case the combination leaves the pre-built set, so Step 9.5 takes the generation path.

### Step 4.7: Confirm the repo structure (interactive)

If there is existing code, first show the value inferred from measurement (`ls` + a look at the main directories) as the default and merely take a confirmation:

```
Confirming the repo structure:

1. monorepo — root app + shared packages (packages/)                (default)
   ↳ When code is used in two or more places. Web+admin, app+landing, shared UI · types · utils
   ↳ packages/ is classified Costly, so edits pick up one more review step

2. single   — one app
   ↳ When there is nothing to share yet. Prototypes · single services
   ↳ If packages/ shows up later, you move up to monorepo then (easy to reverse)

3. msa      — several services (services/ · apps/)
   ↳ When there are several deployment units. API and event contracts between services are managed separately

If it is hard to choose — is there code right now that two or more places use?
  Yes → 1   ·   No → 2   ·   Deployed separately → 3
```

- **Measurement beats the default.** If an existing repository has no `packages/` or `services/`,
  offer `single` as the default. The `monorepo` default applies **only to new projects and when measurement is undecidable**
- The shared package path (Step 4 item 7) is **skipped only when `single` is chosen** — `monorepo` and `msa` require it.
  Without that path Step 7.5 cannot fill the structure card's `paths:`, and an empty `paths:`
  means that card is never loaded over shared code again
- The result is used for `domains.repoTopology` in Step 5 and for the structure card in Step 7.5
- **For a `monorepo` or `msa` with two or more axes, take a directory per axis** — web (`apps/web`) · app (`apps/mobile`) ·
  API (`apps/api`), say. Each becomes that axis's `sourceDir`, and **all** of them go into the Step 7.5 card `paths:`.
  Take only one and the structure card never loads over the other axes' code

> **Why the options carry explanations** — a default with no basis for judgement just gets pressed, and a
> one-app project starts out carrying an empty `packages/`. The deciding question is not scale but the single
> question **"is there code right now that two or more places use?"** — ask by scale and you get "it will
> probably grow", which is not a basis. Structure protects only up to the review requirement; what tells you
> B broke is B's tests.

### Step 4.9: Confirmation summary — show it once before writing any file

When the interview ends, **show the values to be recorded in a single table and get confirmation.** Files are written after that.
Without this step, values produced by measurement, inference or normalization become the config without ever passing the user's eyes.

```
Confirmation summary — recording this as-is:
  Product form   hybrid (app shell: RN shell + native screens)      clientKind = app
  Web screens    react-vite   · TypeScript · npm · apps/web
  App            react-native · TypeScript · npm · apps/mobile      → stack rule file installed (detailed guide optional in Step 9.5)
  Backend        fastify      · PostgreSQL · Drizzle · Auth0 (custom) · AWS · apps/api
  Project cmds   build: npm run build -ws   test: npm test -ws   lint: npm run lint -ws
  Repo           monorepo · shared packages/
  Source         ✎ user choice  ⓜ measured  ⓟ preset default  ⓡ recommended — marked on every row
```

- **Mark the source on every row** — only when it is visible where values the user did not pick (measured · preset · recommended)
  came from can a wrong one be spotted. In particular, **a value inferred from reading a design document is marked as inferred, not ⓜ**
- **Changes to defaults such as language (TypeScript/JavaScript) and UI toolkit are taken here** — they are not asked separately
- Say so for a `custom` or `undecided` axis — it means there is no prebuilt rule file. For `custom`, Step 9.5 asks you to choose among a rule file (backed by the official docs) · rule file + detailed guide · create nothing

**Right after showing the table, ask with `AskUserQuestion` — do not ask in text and end the turn**
(the user is left waiting without knowing what to type). This confirmation does not count toward the interview call budget (calls 1–4):

```
Question: Create the files with this configuration?
  1. Create (recommended) — write orangekit.config.json · CLAUDE.md · rule cards as shown above
  2. Edit                 — pick what to change
```

- **On "Create", go straight to Step 5.** Do not confirm again
- **On "Edit", ask once more with the same tool** — take the items to change as a multi-select:
  `Product form · screens · app` / `Backend (type · framework · DB · auth · deploy)` /
  `Commands · directories · repo structure` / free input (any other value). Re-ask only the questions
  for the chosen items (never restart the interview), fix the values, then **show the table again and
  return to the confirmation question above**
- If the free input already carries the change (e.g. "backend auth should be Auth0"), fix just that value and return to the table

### Step 5–6: Create orangekit.config.json · CLAUDE.md

**Read `assets/config-and-claude-md.md` and follow it exactly.**

### Step 7: Install the T1 rule cards (required — do not skip)

Install the plugin's rule cards into the project's `.claude/rules/`:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/install-rules.sh"
```

Cards installed:

| File | Load condition |
| --- | --- |
| `workflow-routing.md` | **every session, unconditionally** (no `paths`) — task routing P0–P6 + reference freshness |
| `code-change.md` | editing `src/**` `app/**` `packages/**` `lib/**` `apps/**` `services/**` `ios/**` `android/**` |
| `security.md` | editing `src/**` `app/**` `packages/**` `lib/**` `apps/**` `services/**` `ios/**` `android/**` |
| `reversibility.md` | editing source · migrations · workspace |
| `harness-change.md` | editing `.claude/**` `scripts/**` `hooks/**` |
| `lessons.md` | editing source · `.claude/**` · `scripts/**` · `dev/docs/**` |
| `doc-dependency.md` | editing `dev/docs/{prd,database,design,architecture,api}/**` |
| `data-modeling.md` | editing DB paths such as `supabase/**` `**/migrations/**` `**/migration/**` `**/db/**` `prisma/**` `alembic/**` `**/*.sql`. It holds only §1–8; the eleven patterns are moved down to `.claude/references/data-modeling/` so **only what is needed** is read |
| `ui-design.md` | editing `**/components/**` `**/*.{css,scss}` `**/app/**/page.{tsx,jsx}` `**/app/**/layout.{tsx,jsx}` |

> This table must reflect the real frontmatter in `rules/`. When a card is added or changed, fix this too
> — `doctor --fast` detects a card-count mismatch.

Verify after installing:

```bash
ls .claude/rules/
```

Zero files means the install failed — report to the user and stop.

> Skipping it is recovered in the next session — the `session-brief` hook runs `install-rules.sh --missing-only` —
> but the hook installs **only what is missing**, does not refresh outdated versions, and does not wait for work that needs the rules in this session.
> The always-on norms (T0) are not a file; the `session-brief` hook prints them every session (plugin-owned).

### Step 7.5: Create project-specific rule cards (project-owned)

**Read "Step 7.5" in `assets/project-cards-and-report.md` and follow it exactly.** Build the two cards `project-structure.md` and `code-conventions.md` from measurement, and check that `paths:` covers the source and topology paths.

### Step 8–9.5: dev/ · .gitignore · stack rule files (the detailed guide is opt-in)

**Read `assets/scaffold-and-guide.md` and follow it exactly.**

### Step 10: Completion report

**Read "Step 10" in `assets/project-cards-and-report.md` and report in that format.**

## Cautions

- Secret blocking is **built into** the `security-check.sh` hook — it is not a project configuration item
