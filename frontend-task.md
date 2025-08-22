# LLM Implementation Prompt — **Frontend** (Monorepo, Docker, Monochrome UI)

**Context:** Build a simple, clean, **monochrome** Frontend for the SMS API Gateway per the system design (v1.5). The UI is a standalone web app beside **Server B** (DMZ), talking to Server B’s APIs. Keep everything in a **single repository** with `server-a/`, `server-b/`, and `frontend/`.
**Admin user:** There is a **built-in admin** whose username/password are provided **via `docker-compose` env vars**, **not** persisted in DB, and **cannot be disabled**. The frontend must support login for both this built-in admin and (later) DB-backed users exposed by Server B.

> If a more suitable web stack than React exists for this scope (e.g., **React+Vite** default; optionally **Next.js** or **SvelteKit** if you can justify benefits: routing, DX, build), you may use it. Otherwise use **React + Vite + TypeScript**. In all cases: ship Docker support and tests.

---

## Output Mode

* If you **cannot** access a CLI or filesystem, **print all files** using this exact format:

  ```
  # FILE: path/to/file.ext
  <file content>
  ```

  Include every file required (Dockerfile, vite config, tsconfig, test setup, etc.).
* If you **do** have CLI/filesystem access, create files directly. (Optional: `git` commits are welcome but **not required** in this prompt.)

> **Important:** For anything you add, **also include tests**.

---

## Monorepo Structure

Create/ensure this tree (implement **frontend** fully):

```
repo-root/
  server-a/                     # existing (leave as-is)
  server-b/                     # existing (leave as-is)
  frontend/
    src/
      main.tsx
      app.tsx
      router.tsx
      api/
        client.ts
        auth.ts
        messages.ts
        users.ts
      components/
        layout/
          AppShell.tsx
          Sidebar.tsx
          Topbar.tsx
        ui/
          Button.tsx
          Input.tsx
          Table.tsx
          Badge.tsx
          Card.tsx
          Modal.tsx
        charts/                 # optional (placeholder)
      pages/
        Login.tsx
        Dashboard.tsx
        MessagesList.tsx
        MessageDetail.tsx
        UsersAdmin.tsx
        NotFound.tsx
      hooks/
        useAuth.ts
        useFetch.ts
      styles/
        index.css
        theme.css
      lib/
        rbac.ts
        format.ts
      test/
        setup.ts
        __mocks__/serverB.ts
        pages/
          login.test.tsx
          messages.test.tsx
          users-admin.test.tsx
          rbac.test.ts
    index.html
    tsconfig.json
    vite.config.ts
    package.json
    Dockerfile
    README.md
  docker-compose.yml             # extend with frontend service + env
  .env.example                   # add frontend envs
  README.md                      # repo overview (update if necessary)
```

---

## Tech Choices

* **Default:** React 18 + Vite + TypeScript.
* **Styling:** **Tailwind CSS** *or* vanilla CSS with CSS variables. Use a **monochrome** palette (grayscale only, one neutral accent if necessary).
* **State/Query:** Lightweight—no Redux. Use simple hooks and fetch wrappers.
* **Testing:** **Vitest** + **@testing-library/react** for unit/integration tests.
* **Icons:** Optional (`lucide-react`) but keep monochrome.
* **Routing:** `react-router-dom`.

---

## Environment Variables (frontend)

Add to root `.env.example` and pass via `docker-compose`:

```
# Frontend
VITE_APP_NAME=SMS Gateway UI
VITE_API_BASE_URL=http://server-b:9000
VITE_DEFAULT_THEME=mono

# Built-in admin (for login request payload only; NOT stored in DB)
# These envs are passed to Server B too; frontend just shows a login form.
# Do not hardcode these in the bundle; users type them on the login form.
```

> Frontend **does not** embed admin credentials. It presents a **login form** and calls Server B’s `/api/auth/login`. Server B must accept:
>
> * built-in admin from **env** (e.g., `SERVER_B_ADMIN_USERNAME`, `SERVER_B_ADMIN_PASSWORD`)
> * DB users (future) if configured
>   The built-in admin path **cannot be disabled** server-side.

---

## Pages & Access Control

* **Login** (public): POST to `POST /api/auth/login` (Server B) → returns an access token (e.g., JWT) with claims `{ sub, role }` where `role ∈ { "admin", "user" }`. Store token **in memory** + **localStorage**; attach to API calls via `Authorization: Bearer`.
* **Dashboard** (authenticated): quick stats (count by status over last 24h), recent messages list summary, quota usage per client (if available), and provider availability (if Server B exposes a summary).
* **Messages** (authenticated for **any user**):

  * **List** with filters: `tracking_id`, phone, status (QUEUED/PROCESSING/SENT/DELIVERED/FAILED), time range; pagination or infinite scroll.
  * **Detail**: show full message + **event timeline** (PROCESSING → SENT → DELIVERED/FAILED) with timestamps and provider handoffs.
* **Users (Admin only)**:

  * CRUD for DB-backed `ui_users` and their **client associations**.
  * Note: the **built-in admin** is **not** in DB; label it “Built-in Admin (env) — always enabled” in UI but not editable.
* **(Optional) Clients & API Keys (Admin)**:

  * List/CRUD clients (`clients` table): name, api\_key, daily\_quota, is\_active.
* **(Optional) Providers (Admin)**:

  * Read-only view of providers’ operational status (if Server B exposes it) and config fingerprints comparison.

**RBAC:**

* Route guards: `role === 'admin'` can access Users/Clients pages; otherwise redirect.
* Navbar/Sidebar should show/hide links by role.

---

## API Contracts (expected from Server B)

If not available yet, implement a **mock adapter** in `src/test/__mocks__/serverB.ts` and a **dev mock mode** toggle:

* **Auth:** `POST /api/auth/login` → `{ access_token, role, expires_in }`.
* **Messages:**

  * `GET /api/messages?status=&q=&from=&to=&page=&page_size=` → paginated list
  * `GET /api/status/{tracking_id}` → details + events (as specified in the design doc)
* **Users (Admin):**

  * `GET /api/ui-users`
  * `POST /api/ui-users`
  * `PUT /api/ui-users/{id}`
  * `DELETE /api/ui-users/{id}`
  * `GET /api/client-user-associations?ui_user_id=...` | `POST /api/client-user-associations` | `DELETE ...`
* **Clients (Admin, optional):**

  * `GET /api/clients` | `POST /api/clients` | `PUT /api/clients/{id}` | `DELETE /api/clients/{id}`

> If an endpoint is missing server-side, your **API client** must transparently fall back to **mock mode** (driven by `import.meta.env.VITE_MOCK_API === 'true'`) so the UI still runs.

---

## Design & UX (Monochrome)

* **Palette:** grayscale only (e.g., `#000`/`#111`/`#333`/`#777`/`#eee`/`#fff`).
* **Typography:** system fonts; clear hierarchy; comfortable line heights.
* **Components:** minimalist: Button, Input, Table, Badge, Card, Modal—all monochrome.
* **Layout:** Sidebar + Topbar in an `AppShell`. Responsive.
* **Accessibility:** semantic HTML, keyboard focus states, sufficient contrast.
* **Empty states:** clear messages, “no results found” variants.
* **Loading & errors:** skeletons/spinners; inline error banners.
* **No brand colors**—strictly monochrome.

---

## Frontend Logic

* **Auth flow:**

  * On login success, store `{ token, role, expires_at }`.
  * Add Axios/fetch interceptor to inject `Authorization: Bearer`.
  * Route guards read `role`.
* **RBAC:**

  * Utilities in `lib/rbac.ts`: `canManageUsers(role)` etc.
  * Hide admin-only nav items for non-admins.
* **API layer:**

  * `api/client.ts` centralizes `fetch`/retry/minimal error handling & mock toggle.
  * `api/messages.ts`, `api/users.ts`, `api/auth.ts` call concrete endpoints or mocks.
* **Hooks:**

  * `useAuth` provides login/logout, role, token, guard helpers.
  * `useFetch` wraps `fetch` with loading/error states and cancellation.
* **Performance:** simple pagination/infinite scroll; debounce filters.

---

## Docker & Compose

* `frontend/Dockerfile`:

  * Multi-stage: build with Node (Vite), then serve static files from **nginx\:alpine** or a minimal node http server.
* Extend root `docker-compose.yml`:

  * Add `frontend` service, expose port (e.g., `5173` dev or `8080` prod).
  * Set `VITE_API_BASE_URL=http://server-b:9000`.
  * Ensure startup order is fine but **frontend** should not block if Server B isn’t fully ready (mock mode switch helps).

---

## Tests (required for everything you add)

Use **Vitest** + **@testing-library/react**:

* `pages/login.test.tsx`: form validation, success path stores token/role; failure shows error.
* `pages/messages.test.tsx`: filter → API call performed; list renders; empty-state; detail navigation.
* `pages/users-admin.test.tsx`: route guard blocks non-admin; CRUD actions call API; built-in admin is displayed as non-editable info.
* `rbac.test.ts`: role checks; links hidden/shown correctly.

> Every UI component or utility you add should have **unit tests** or **page-level integration tests** that cover its core behaviors.

---

## Acceptance Criteria

* **Monochrome** look & feel throughout.
* **Login** screen integrates with `POST /api/auth/login`; supports built-in admin (server env) and later DB users.
* **Dashboard** shows recent metrics/message counts (if available) or placeholders.
* **Messages** list + detail with filters, pagination, and event timeline.
* **Users (Admin)** page functions for DB users/associations; **built-in admin** appears as read-only info and is **not** stored in DB.
* **RBAC** route guards enforce access.
* **API mock mode** works when server endpoints are missing.
* **Docker** image builds and serves the app.
* **Tests** exist and pass for pages/components you created.

---

## Step-by-Step Tasks

### Task 0 — Bootstrap app

* Create Vite + React + TS app; set up routing, Tailwind (or CSS variables), Vitest + RTL, and basic monochrome theme.
* Add `AppShell` with Sidebar & Topbar; wire routes.

### Task 1 — Auth

* Build `Login` page; `useAuth` hook; token storage; route guards.
* Expect `POST /api/auth/login` returns `{ access_token, role }`. If unreachable and mock mode enabled, return a mock token + role.
* Add tests.

### Task 2 — Messages

* Build `MessagesList` with filters (status, q, date), pagination.
* Build `MessageDetail` with event timeline.
* API: `GET /api/messages`, `GET /api/status/{tracking_id}` (or mock).
* Add tests.

### Task 3 — Users (Admin)

* Build `UsersAdmin` page: list/create/update/delete DB users and manage client associations.
* Show **Built-in Admin (env)** as read-only badge; not editable.
* Add tests (including route guard).

### Task 4 — Dashboard

* Simple KPIs: counts by status in last 24h; recent messages; provider/config fingerprint status if available; otherwise placeholders.
* Add tests.

### Task 5 — Polish & Docker

* Loading states, error banners, empty states; accessibility checks.
* Implement `frontend/Dockerfile` (multi-stage) and extend `docker-compose.yml`.
* Add README with run instructions and envs.
* Ensure tests run (Vitest) and CI-ready scripts in `package.json`.

---

## Deliverables (print these files if no CLI)

1. `frontend/package.json`
2. `frontend/tsconfig.json`
3. `frontend/vite.config.ts`
4. `frontend/index.html`
5. `frontend/src/main.tsx`
6. `frontend/src/app.tsx`
7. `frontend/src/router.tsx`
8. `frontend/src/styles/index.css`
9. `frontend/src/styles/theme.css`
10. `frontend/src/components/layout/AppShell.tsx`
11. `frontend/src/components/layout/Sidebar.tsx`
12. `frontend/src/components/layout/Topbar.tsx`
13. `frontend/src/components/ui/Button.tsx`
14. `frontend/src/components/ui/Input.tsx`
15. `frontend/src/components/ui/Table.tsx`
16. `frontend/src/components/ui/Badge.tsx`
17. `frontend/src/components/ui/Card.tsx`
18. `frontend/src/components/ui/Modal.tsx`
19. `frontend/src/hooks/useAuth.ts`
20. `frontend/src/hooks/useFetch.ts`
21. `frontend/src/lib/rbac.ts`
22. `frontend/src/lib/format.ts`
23. `frontend/src/api/client.ts`
24. `frontend/src/api/auth.ts`
25. `frontend/src/api/messages.ts`
26. `frontend/src/api/users.ts`
27. `frontend/src/pages/Login.tsx`
28. `frontend/src/pages/Dashboard.tsx`
29. `frontend/src/pages/MessagesList.tsx`
30. `frontend/src/pages/MessageDetail.tsx`
31. `frontend/src/pages/UsersAdmin.tsx`
32. `frontend/src/pages/NotFound.tsx`
33. `frontend/src/test/setup.ts`
34. `frontend/src/test/__mocks__/serverB.ts`
35. `frontend/src/test/pages/login.test.tsx`
36. `frontend/src/test/pages/messages.test.tsx`
37. `frontend/src/test/pages/users-admin.test.tsx`
38. `frontend/src/test/pages/rbac.test.ts`
39. `frontend/Dockerfile`
40. `frontend/README.md`
41. Root `docker-compose.yml` (updated with `frontend` service)
42. Root `.env.example` (add frontend envs)
43. Root `README.md` (updated overview)

--- 

# Must-Have Files (in addition to previous list)

Add/extend modules for Auth & RBAC and new APIs:
server-b/app/auth.py (JWT create/verify, role deps, bcrypt utilities)
server-b/app/routers/auth.py (login, builtin admin info)
server-b/app/routers/messages.py (list/detail)
server-b/app/routers/users.py (users CRUD + associations)
server-b/app/routers/admin.py (providers summary, dashboard summary)
Update server-b/app/main.py to include CORS and mount routers with tags.
Update server-b/app/schemas.py with DTOs for:
Auth: LoginRequest, LoginResponse
Messages: MessageOut, MessageListResponse, filters
Users: UserIn, UserOut, AssociationIn
Providers: ProviderInfo, ProvidersResponse
Summary: SummaryResponse
Update server-b/app/repositories.py with queries supporting filters/pagination.
Update migrations to ensure indexes for message queries.
Tests (Vitest not applicable; use pytest):
tests/test_auth.py (builtin + db user, guards)
tests/test_messages_api.py (filters, paging)
tests/test_users_admin_api.py
tests/test_admin_providers_summary.py
Keep earlier tests (policy engine, consumer, webhooks, status)
Dependencies (additions)
PyJWT, passlib[bcrypt]

## Env & Contracts
Same env and endpoint contracts as the CLI prompt above.


## Acceptance
Same as above; endpoints compile and tests cover all additions.

---

## Notes

* Keep the UI strictly **monochrome**; no brand colors.
* The **built-in admin** lives only in **Server B env** (compose); frontend displays it as read-only info in the Users page; not persisted.
* If you choose a different stack than React+Vite, ensure equivalent structure, tests, and Dockerization.
* For every component/page/hook/utility you add, **write tests**.

