# Mobile Account Deactivation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add mobile-only account deactivation applications with a 60-day reversible waiting period and permanent lockout at expiry.

**Architecture:** Keep HTTP endpoints in the existing user router and centralize lifecycle predicates/mutations in a focused core module shared by login and token authentication. Persist the four already-started user columns, expose them through profile serialization, and verify behavior through API-level pytest tests.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, pytest/TestClient

---

### Task 1: Request validation and application API

**Files:**
- Create: `app/core/account_deactivation.py`
- Modify: `app/schemas/user.py`
- Modify: `app/api/users.py`
- Test: `tests/test_account_deactivation.py`

- [ ] **Step 1: Write failing tests for mobile restriction, trimmed 10–500 character validation, successful application, and duplicate rejection**

Create API tests that issue mobile and non-mobile development tokens, call `POST /api/user/deactivation`, and assert status codes, response data, and persisted model fields. Parameterize the allowed client types as `android`, `ios`, `harmonyos`, `miniprogram`, and `h5`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.venv/bin/pytest tests/test_account_deactivation.py -q`

Expected: FAIL because `/api/user/deactivation` does not exist and trimmed validation is not implemented.

- [ ] **Step 3: Add the shared lifecycle primitives and normalized request schema**

Implement these interfaces in `app/core/account_deactivation.py`:

```python
DEACTIVATION_WAIT_DAYS = 60
MOBILE_CLIENT_TYPES = {"android", "ios", "harmonyos", "miniprogram", "h5"}

def is_mobile_account(user: User) -> bool: ...
def deactivation_is_due(user: User, now: datetime | None = None) -> bool: ...
def mark_deactivated(user: User) -> None: ...
def expire_deactivation_if_due(user: User, now: datetime | None = None) -> bool: ...
```

Use a Pydantic `field_validator(..., mode="before")` to strip the reason before `min_length=10` and `max_length=500` are evaluated.

- [ ] **Step 4: Implement the application endpoint**

Add `POST /api/user/deactivation` to `app/api/users.py`. Reject non-mobile and duplicate applications with 400; otherwise set status, normalized reason, UTC apply time, and `apply_time + timedelta(days=60)`, commit, refresh, and return the lifecycle fields.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `.venv/bin/pytest tests/test_account_deactivation.py -q`

Expected: all application tests PASS.

### Task 2: Cancellation, profile output, and expiry enforcement

**Files:**
- Modify: `app/api/users.py`
- Modify: `app/api/serializers.py`
- Modify: `app/api/deps.py`
- Modify: `app/api/auth.py`
- Test: `tests/test_account_deactivation.py`

- [ ] **Step 1: Write failing tests for cancellation, profile output, and expired access/login**

Test that pending accounts can still authenticate and cancel; cancellation clears all four fields; profile exposes pending values; expired pending accounts receive 401 on authenticated access and 403 on login; and expiry is persisted as `deactivated` plus `is_active=False`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.venv/bin/pytest tests/test_account_deactivation.py -q`

Expected: FAIL because cancellation is missing, serializer omits lifecycle values, and login expiry changes are not reliably persisted.

- [ ] **Step 3: Implement cancellation and profile serialization**

Add `POST /api/user/deactivation/cancel`. Require a mobile account with a non-expired `pending` state, then clear status, reason, apply time, and end time. Populate the four `deactivation*` fields in `user_profile()`.

- [ ] **Step 4: Share and persist expiry behavior across authentication paths**

Use `expire_deactivation_if_due()` in `app/api/deps.py`; commit before rejecting an expired bearer token. Change `ensure_user_can_login` to accept the session, persist an expired transition before raising 403, and update all four login call sites.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `.venv/bin/pytest tests/test_account_deactivation.py -q`

Expected: all deactivation tests PASS.

### Task 3: Migration and regression verification

**Files:**
- Verify: `alembic/versions/0045_user_deactivation.py`
- Verify: all files modified above

- [ ] **Step 1: Verify migration ancestry and syntax**

Run: `.venv/bin/alembic heads`

Expected: a single head at `0045_user_deactivation`.

- [ ] **Step 2: Run the full test suite**

Run: `.venv/bin/pytest -q`

Expected: all tests PASS with zero failures.

- [ ] **Step 3: Run static and whitespace checks**

Run: `.venv/bin/python -m compileall -q app tests`

Expected: exit code 0.

Run: `git diff --check`

Expected: exit code 0 and no output.

- [ ] **Step 4: Review final scope**

Run: `git status --short` and `git diff --stat HEAD~1`

Expected: only the account-deactivation implementation, tests, migration, schema/model changes, and plan/spec documentation are present.
