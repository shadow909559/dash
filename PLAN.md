# Fix Plan - All Test Errors

## Summary of Errors Found

After running all tests, the following errors were identified across the test suite:

### Issues in `tests/test_integration.py`:

1. **test_jwt_token_creation_and_validation**: `create_access_token(data={"sub": user_id})` - API signature mismatch. Should be `create_access_token(subject=user_id)`.

2. **test_jwt_rejects_expired_token**: `create_access_token(data=..., expires_delta=...)` - API signature mismatch. Must use `_encode_jwt` directly.

3. **test_full_auth_flow**: Uses `hashed_password` kwarg but User model has `password_hash`. Also uses `found_user.hashed_password`.

4. **test_create_and_query_user**: Same `hashed_password` -> `password_hash` issue.

5. **test_rag_search**: `retrieve_context` returns empty because embeddings are None with no provider configured, but the fallback search also fails.

6. **test_skill_registry**: Calls `SkillRegistry.list_skills()` which doesn't exist.

7. **test_input_sanitization**: Expects `sanitize_user_input("x"*10000)` to truncate to <=5000, but default MAX_USER_MESSAGE_LENGTH is 10000.

8. **test_rate_limiter**: Uses `RateLimiter(max_requests=5, window_seconds=60)` but signature is `RateLimiter(capacity=..., refill_period_seconds=...)`.

9. **test_path_traversal_prevention**: Imports `resolve_path_within_sandbox` from wrong module.

10. **test_websocket_message_parsing**: `ChatSendMessage` requires `message_id` field but test data doesn't include it.

11. **test_full_auth_to_conversation_flow**: Same `hashed_password` -> `password_hash` issue.

12. **test_goal_to_execution_pipeline**: Will fail because `create_goal` expects `uuid.UUID` not `str`.

## Files to Edit:

### 1. `apps/backend/tests/test_integration.py`
- Fix all test methods with the issues listed above

### 2. `apps/backend/dash_backend/skills/registry.py`
- Add `list_skills()` class method to SkillRegistry

### 3. No source code changes needed - all errors are in tests or can be fixed by updating tests to match current API signatures.

