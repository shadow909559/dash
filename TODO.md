# Bug Fix TODO

## CRITICAL
- [ ] 1. Add missing projects/notifications/automation_rules route includes to api/router.py
- [ ] 2. Fix memory API param mismatch (page/perPage -> limit/offset) in Memory.tsx
- [ ] 3. Fix login double-call in Login.tsx (register now returns tokens)
- [ ] 4. Fix chat conversation persistence on reload
- [ ] 5. Fix automation route conflict (frontend calls /automation/rules)

## VERIFY
- [ ] 6. Run build to confirm zero TypeScript errors
- [ ] 7. Verify all pages work end-to-end
