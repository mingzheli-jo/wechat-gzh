# Spec: Draft Rewrite Cap (max 5 regenerations)

**Date:** 2026-05-11
**Status:** Draft — pending user review
**Origin:** User reported that the「重新改写」flow felt "one-shot" and asked to extend the limit to 5. After clarification, the agreed behavior is a simple per-draft regeneration counter, not version history.

## Goal

Allow each `Draft` row to be re-rewritten up to **5 times** via `POST /drafts/{id}/rewrite`. After the 5th re-rewrite, the button is disabled in the UI and the backend returns `409 已达 5 次改写上限`. Each re-rewrite continues to overwrite the previous title, content, review report, and images (current behavior — no version history kept).

The initial generation (`POST /drafts/rewrite`, which creates a new Draft row from a library item) does **not** count toward the cap. So per draft the LLM is invoked at most `1 + 5 = 6` times by the rewrite pipeline.

## Non-Goals

- **No version history.** Old title/content/reviews are still discarded on each regeneration. The 5-cap is a cost guardrail, not a "save 5 alternative versions" feature.
- **No counter reset path.** v1 has no admin endpoint to reset the counter. If the user needs more attempts, they delete the draft and re-create it from the library item, which resets to a fresh budget of 5.
- **No retroactive limit on Draft.title / content edits via PATCH `/drafts/{id}`.** Manual edits do not consume the budget.
- **No change to the open content-mixup bug** (memory note 2026-05-08). The cap doesn't fix or address it — independent issue.

## Naming choice

The Library schema already exposes `rewrite_count: int` on `LibraryItemOut`, meaning "number of Draft rows produced from this library item" (per-item, used by the Library list UI to show `已改写 ×N`). To avoid collision and reader confusion, the new column on the `drafts` table is named **`regenerate_count`**, semantically "number of times the regenerate/「重新改写」action has been invoked on this specific draft."

| Field | Table | Meaning |
|-------|-------|---------|
| `library_items.rewrite_count` *(virtual, computed via subquery)* | LibraryItem list response | How many drafts have been created from this article |
| `drafts.regenerate_count` *(new, persisted)* | Draft row | How many times this draft has been re-rewritten |

## Backend changes

### 1. Model (`backend/app/drafts/models.py`)

Add column:

```python
regenerate_count: Mapped[int] = mapped_column(
    Integer, nullable=False, default=0, server_default="0"
)
```

No class constant for the limit — it lives in `Settings` so it can be tuned per environment.

### 2. Config (`backend/app/config.py`)

Add field:

```python
draft_max_regenerations: int = Field(default=5, ge=1, le=50)
```

Reads from env var `DRAFT_MAX_REGENERATIONS` if set.

### 3. Migration (Alembic)

New revision file. Depends on `b3a7f1c2e8d9` (current head).

```python
def upgrade() -> None:
    op.add_column(
        "drafts",
        sa.Column(
            "regenerate_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

def downgrade() -> None:
    op.drop_column("drafts", "regenerate_count")
```

`server_default="0"` ensures existing rows are backfilled to 0 — every existing draft gets a fresh budget of 5.

### 4. Service (`backend/app/drafts/service.py`)

Modify `reset_for_rewrite` so the existing `UPDATE drafts ...` statement also includes `regenerate_count=Draft.regenerate_count + 1`. This keeps the increment atomic with the reset (one UPDATE, no race).

```python
.values(
    title=None,
    content_html=None,
    cover_image_id=None,
    error_msg=None,
    wechat_media_id=None,
    wechat_pushed_at=None,
    status=DraftStatus.draft,
    regenerate_count=Draft.regenerate_count + 1,
)
```

### 5. Route (`backend/app/drafts/routes.py`, `rewrite_again`)

Insert one check before calling `reset_for_rewrite`:

```python
settings = get_settings()
if obj.regenerate_count >= settings.draft_max_regenerations:
    raise HTTPException(409, "已达 5 次改写上限")
```

Order of checks (top to bottom): 404 → in-progress 409 → published 409 → **new cap 409** → reset + enqueue.

### 6. Schemas (`backend/app/drafts/schemas.py`)

Add `regenerate_count: int` to `DraftOut` (so the Library/Drafts list and the detail page both see it). Add `max_regenerations: int` to `DraftDetail` only (single-place rendering of the cap, sourced from settings on the route handler before validating the response). Implementation: build the dict, inject `max_regenerations`, then `DraftDetail.model_validate(...)`.

Alternative considered: add `max_regenerations` to a separate `/api/config` endpoint. Rejected — one extra request per page load for a static value is wasteful.

## Frontend changes

### `frontend/src/pages/DraftDetail.tsx`

Two small edits, both around the「重新改写」button (around line 760):

1. **Label** shows counter:
   ```tsx
   {rewriteAgain.isPending
     ? "重写中…"
     : `重新改写 (${detail.data.regenerate_count}/${detail.data.max_regenerations})`}
   ```

2. **Disabled** condition gets one more clause:
   ```tsx
   disabled={
     rewriteAgain.isPending ||
     detail.data.status === "draft" ||
     detail.data.status === "reviewing" ||
     detail.data.status === "published_to_wechat" ||
     detail.data.regenerate_count >= detail.data.max_regenerations
   }
   ```

3. **Hint text** (optional, only shown when at cap) below the button:
   ```tsx
   {detail.data.regenerate_count >= detail.data.max_regenerations && (
     <p style={{ fontSize: 12, color: "var(--color-failed)", marginTop: 6 }}>
       已达 {detail.data.max_regenerations} 次改写上限
     </p>
   )}
   ```

### TypeScript type (`frontend/src/types/draft.ts` or wherever `DraftDetail` is declared)

Add `regenerate_count: number;` and `max_regenerations: number;`.

## Edge cases

| Case | Behavior |
|------|----------|
| Re-rewrite that fails (LLM error → `status=failed`) | **Counts.** The LLM call already burned tokens. The counter is incremented in `reset_for_rewrite`, which runs before `run_pipeline.delay(...)` enqueues the work, so the count reflects "attempts started", not "successful completions". |
| Manual edit via PATCH `/drafts/{id}` | Does NOT count. Editing in place is free. |
| Publish to WeChat | Does NOT count. Publishing doesn't reset the counter either — the cap persists across publishes. |
| Existing drafts after migration | `regenerate_count = 0` (server_default), so they all get the full budget of 5. |
| Initial creation via POST `/drafts/rewrite` | Does NOT count. Counter stays at 0 after creation. Only `POST /drafts/{id}/rewrite` increments. |
| Concurrent click (user double-clicks button before first request returns) | Idempotent at the DB level — both UPDATE statements increment by 1, so two simultaneous clicks may consume 2 from the budget. Acceptable for v1 (single-user tool, low concurrency). Frontend `disabled` while `isPending` prevents this in practice. |
| Counter reset | No reset path. Workaround: delete + re-create the draft. |
| Draft.status is `failed` and `regenerate_count` is already 5 | 409 returned. User must delete + re-create. (Acceptable; failed drafts are rare and the user can use the library re-rewrite flow to start fresh.) |

## Tests

No dedicated `test_drafts_service.py` / `test_drafts_routes.py` exists yet. v1 adds tests in two locations to stay consistent with current layout:

### Unit (`tests/unit/test_drafts_service.py` — new file)

- `test_reset_for_rewrite_increments_regenerate_count`: create draft with count=2, call `reset_for_rewrite`, assert count=3.
- `test_reset_for_rewrite_clears_generated_fields`: smoke-cover the existing behavior so the increment edit doesn't accidentally break it.

### Integration (`tests/integration/test_drafts_routes.py` — new file)

Mirrors the pattern of `tests/integration/test_library_routes.py` (auth fixture + `httpx.AsyncClient`).

- `test_rewrite_again_increments_counter`: POST `/drafts/{id}/rewrite` (with Celery patched to no-op via `monkeypatch.setattr("app.tasks.rewrite.run_pipeline.delay", ...)`), GET `/drafts/{id}`, assert `regenerate_count == 1`.
- `test_rewrite_again_blocked_at_cap`: pre-seed draft with `regenerate_count=5`, POST `/drafts/{id}/rewrite` returns 409 with body matching `已达 5 次改写上限`. Verify count stays at 5 (no increment on rejection).
- `test_draft_detail_exposes_max_regenerations`: GET `/drafts/{id}`, assert `max_regenerations == 5`.

### Migration

- Run `uv run alembic upgrade head` against a database holding existing draft rows; verify all have `regenerate_count = 0`.

### Frontend

- No new test file required (the existing pattern is for behavior-heavy components; this is a label + a boolean clause). A quick `pnpm build` (tsc + vite) confirms types compile.

## Rollout

1. Backend changes + migration → commit.
2. Frontend changes → commit.
3. `docker compose up -d --build api worker web` on the user's server.
4. Manual smoke: open an existing draft, click「重新改写」5 times waiting for each to complete, verify 6th click is disabled and shows `(5/5)`.

## Risks / open questions

- **Open content-mixup bug (memory 2026-05-08):** if regenerations are returning wrong content body, this cap will make the bug LESS recoverable (only 5 retries before requiring delete-and-recreate). The cap should not be implemented before that bug is diagnosed — OR the cap should be raised temporarily. Suggested coordination: implement the cap, but if the content-mixup bug repros, set `DRAFT_MAX_REGENERATIONS=20` in `.env` until the bug is fixed, then drop back to 5.
- **Cost protection level:** 5 regenerations × ~6k tokens/pass × DeepSeek pricing ≈ negligible per draft. The cap is more about UX (preventing the user from hammering the button) than cost.
