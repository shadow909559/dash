# TODO

- [ ] Step 1: Implement rich backend websocket chat/voice/agent protocol (replace echo scaffold, unify routes, add protocol models + streaming)
- [ ] Step 2: Update backend websocket tests to validate authentication handshake and chat streaming/done
- [ ] Step 3: Run backend tests (pytest) and fix any failures
- [ ] Step 4: Wire mobile WebSocketService + ChatProvider to the new protocol (auth + structured events)
- [ ] Step 5: Implement provider/Ollama integration in backend and wire to websocket handlers
- [ ] Step 6: Cleanup/remove unused websocket scaffolds and ensure protocol naming consistency
- [ ] Step 7: Compile/test verification (backend pytest + mobile flutter analyze/build if available)

