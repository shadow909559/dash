# Tool Calling - Backend Integration TODO

- [ ] Add tool-aware LLM call path in `apps/backend/dash_backend/llm/service.py`
- [ ] Integrate `ToolManager` into `apps/backend/dash_backend/api/websocket/handlers.py` `handle_chat_send`
- [ ] Extend websocket protocol with inbound confirmation/rejection messages (client -> server)
- [ ] Update `apps/backend/dash_backend/api/routes/websocket.py` to handle confirmation/rejection and resume/deny tool execution
- [ ] Add WS tool lifecycle events mapping to protocol message models
- [ ] Flutter updates

