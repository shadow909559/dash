# Migration issue: missing `conversations.is_archived`

## Symptom
`GET /api/v1/conversations` fails with:
`UndefinedColumnError: column conversations.is_archived does not exist`

## What was found
- SQLAlchemy model `Conversation` and query logic expect `conversations.is_archived`.
- Alembic upgrade fails due to a broken revision graph:
  `KeyError: '20260715_0002_add_server_defaults'`

## What was added
- New migration (idempotent column add):
  `20260716_0004_add_is_archived_to_conversations`
  at `apps/backend/alembic/versions/20260716_0004_add_is_archived_to_conversations.py`

## Why upgrade still fails
Even when targeting the new migration, Alembic cannot resolve the chain because:
`20260715_0002_add_server_defaults` is referenced but cannot be resolved in the revision map.

## Next required action
Fix Alembic revision resolution so the migration graph is valid. Then run:

1) `cd apps/backend`
2) `python -m alembic upgrade head`
3) Verify:
   - `SELECT is_archived FROM conversations LIMIT 1;`
   - `GET /api/v1/conversations` returns HTTP 200 (or `[]` if empty).

