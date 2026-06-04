# [Coding Standards] Aiden's Tech Lead Guidelines

Aiden expects the codebase to follow these rules strictly. PRs failing these checks will be rejected.

---

## 1. Codebase & Language Conventions
- **Language**: TypeScript strictly on both Frontend (Next.js App Router) and Backend (Express TS).
- **Types**: No usage of `any`. Declare explicit interfaces for all API payloads and WebSocket messages.
- **Formatting**: ESLint and Prettier rules must pass cleanly.

---

## 2. Real-Time & Payment Resilience (Critical)

### 1) DB Connection Failures
- **Standard**: All database helper functions must include robust retries and graceful error catching.
- **Aiden's Rule**: *"Looks fine, but what happens when the DB connection drops?"* You must handle DB pool reconnects and prevent backend crashes.

### 2) Stripe Payment Safety
- **Standard**: Idempotency keys must be used for all Stripe charge creation endpoints to prevent double-charging users during network hiccups.

### 3) WebSocket Consistency
- **Standard**: If a user loses internet connection inside a pub (common in basement bars), the Socket.io client must automatically reconnect and reconcile the split payment status ledger gracefully.

---

## 3. Git Branching & Pull Requests
- **Branch Naming**: `feat/...` for features, `fix/...` for bugs, `chore/...` for dependencies.
- **PR Code Review**: Keep PRs small (< 300 lines of diff) so they can be reviewed quickly. Always reference the corresponding GitHub Issue in the commit message (e.g., `feat(auth): add login route [#12]`).
