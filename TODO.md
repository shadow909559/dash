# TODO

## OpenAI native tool message ordering fix (handlers.py)
- [ ] Inspect current tool loop in apps/backend/dash_backend/api/websocket/handlers.py
- [ ] Implement required OpenAI_NATIVE ordering:
  1) capture native assistant tool_calls
  2) append assistant tool_calls message to history
  3) parse tool calls via ToolManager.parse_tool_calls()
  4) execute tools using existing ToolExecutor via ToolManager.execute_tool_stream()
  5) append ToolManager.format_result_for_llm() output to history
  6) loop until assistant returns no tool_calls
- [ ] Ensure CUSTOM_JSON behavior unchanged
- [ ] Run `python -m py_compile apps/backend/dash_backend/api/websocket/handlers.py`
- [ ] Sanity-check code paths so no role="tool" is appended without preceding assistant tool_calls message

