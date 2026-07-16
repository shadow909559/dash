# TODO - Dash AI Assistant Tool Calling Integration

- [ ] Inspect current LLM streaming/token pipeline and identify how to add tool-calling loop without breaking existing streaming.
- [ ] Update WebSocket protocol with missing inbound tool confirmation/rejection message types (client -> server).
- [ ] Update WebSocket route handler to route these confirmation/rejection messages to ToolManager.
- [ ] Integrate ToolManager into `handle_chat_send` tool-aware execution loop.
- [ ] Implement tool-aware LLM call in `llm/service.py` for Ollama (parse tool calls / function-call outputs).
- [ ] Emit required WS lifecycle events: tool.started/tool.progress/tool.finished/tool.error (+ confirmation_required/confirmed/rejected).
- [ ] Finish Flutter: render tool running/progress/output/error + confirmation prompt UX.
- [ ] Add/adjust tests for tool calling and websocket message flow.
- [ ] Run backend tests + smoke test calculator/current_time.

