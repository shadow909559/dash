# TODO (Dash AI OS)

## Phase 1 — Flutter application audit & stability polish

- [ ] STEP 1: Fix ChatPage rebuild/auto-scroll loop

  - [ ] Remove scheduling scrolling from build()
  - [ ] Auto-scroll only when new messages arrive / streaming updates
  - [ ] Only scroll if user is near bottom


- [ ] STEP 2: Improve WebSocketService reliability

  - [ ] Add reconnect state (connected/connecting/reconnecting/disconnected)
  - [ ] Ensure single in-flight connect and single reconnect timer
  - [ ] Exponential backoff with cap
  - [ ] Heartbeat lifecycle cleanup on reconnect/disconnect
  - [ ] Outgoing queue ONLY for chat.send
  - [ ] Preserve message_id, conversation_id, timestamp
  - [ ] FIFO flush after reconnect
  - [ ] Duplicate-send protection

- [ ] STEP 3: Update ChatProvider to use queue + disable sends while reconnecting
  - [ ] Disable send if websocket disconnected/reconnecting
  - [ ] Ensure queued messages are not re-sent by ChatProvider

- [ ] STEP 4: Add UI indicators for reconnecting
  - [ ] ChatPage: banner above input
  - [ ] Dashboard: compact status indicator
  - [ ] Settings: full connection status

- [ ] STEP 5: Testing after each step
  - [ ] Run: flutter analyze
  - [ ] Run: flutter test

- [ ] Final verification checklist
  - [ ] Chat streams correctly
  - [ ] Auto-scroll works without rebuild loops
  - [ ] WebSocket reconnects automatically
  - [ ] Queue flushes correctly
  - [ ] No duplicate messages
  - [ ] No memory leaks
  - [ ] No API contract changes
  - [ ] App launches successfully

