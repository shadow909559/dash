- [ ] Inspect backend for any existing llama3.2:3b or llama3.2 references and update them to llama3.2:1b
- [x] Update settings default ollama_model to "llama3.2:1b"
- [x] Optimize Ollama request payload / settings for low-memory (smaller context / keep streaming)
- [x] Keep the WebSocket streaming path intact end-to-end


- [ ] Add or adjust backend tests for Ollama streaming/model selection (if present)
- [ ] Run backend tests
- [ ] Run Flutter analyze
- [ ] Run Flutter tests
- [x] Actually test the Ollama connection via a small backend-level call (or curl) and verify streaming



