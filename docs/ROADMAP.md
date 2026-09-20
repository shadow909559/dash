# DASH — Honest Capability Roadmap

What DASH is becoming, what is real today, what is buildable, and what will
never be claimed. This roadmap holds the project to the standard DASH himself
is being built to hold: no imaginary features, no impractical promises, no
fake status. Every phase names its real dependencies and its real limits.

---

## Phase 0 — Candor Core (the personality layer) — ✅ DONE (decisions.md #54)

**Goal:** DASH tells the truth, always, including about himself.

**What exists already:** the brain (`autonomous/brain.py`) orchestrates
alerts/idle/chat; chat flows through `api/websocket/handlers.py` and
`autonomous/brain.py`, both assembling system prompts; memory injection and
RAG grounding exist; `HallucinationDetector`/`SourceVerifier` services exist
for knowledge-graph claims.

**Being built:**
- `autonomous/candor.py` — the honesty engine: a candor system-prompt block
  wired into BOTH chat paths, plus a deterministic idea-assessment pass
  (pre-LLM reality checks: vagueness, capability claims vs. real tools,
  forbidden fake-data patterns) whose findings are injected into the reply
  context.
- Persona contract: disagree plainly when an idea is bad; say "I don't know";
  cite only real system/memory state; never invent tool results.

**Real limits:** the local TinyLlama models are small — candor rules improve
behavior but cannot make a 3B model a genius. Cloud providers follow the
rules better. Honest output also depends on honest inputs: grounding blocks
must be real data, never placeholder text.

## Phase 1 — Eyes (vision) — CORE SHIPPED, LIVE-VERIFIED, AUTONOMOUS (decisions.md #58, #61, #62)

**Goal:** offline object identification + face recognition from the camera.

**Dependencies (real):** `vision/camera_vision.py` already captures frames
(OpenCV, graceful fallback). Needed: an ONNX object detector (YOLO-class,
downloaded once, runs on CPU), and a face stack — `opencv` DNN face detector
+ embeddings (e.g. ONNX ArcFace-class model) with per-person enrollment
stored locally. `models/vision/` exists and is currently empty.

**Honest limits:** CPU-only inference is seconds-per-frame, not real-time,
on modest hardware; recognition accuracy drops in bad light; this runs
locally for privacy, so no cloud accuracy. Camera permission is explicit.

**Autonomous watch (shipped, #62):** a 30s VisionWatcher polls the camera,
recognizes enrolled persons, and reports honestly through the agent's
working memory, `vision.*` bus events, and the audit log — with per-key
cooldowns, failure backoff, and no identity ever guessed.

## Phase 2 — Self-reliance — CORE SHIPPED

**Goal:** DASH notices when things break and fixes them; improves his own
code without destroying himself.

**Shipped (decisions.md #59):** the closed self-healing loop
(`self_heal.py` — detect → diagnose → repair → VERIFY by re-running the
failing check → report; lifespan-wired, audit-logged, visible in
/status) and the test-gated self-code-edit tool
(`tools/self_code_edit_tool.py`, registered as `self_code_edit` — git
checkpoint of the target file first, exact-match edit, real pytest gate,
auto-rollback on red, protected paths so the gate cannot disable itself,
every attempt audited).

**Remaining in this phase:** periodic self-training (interaction log →
LoRA fine-tune → offline eval → swap-in only if eval beats the current
model). Hardware-bound; unbuilt — no claim is made that it exists.

**What existed already:** `monitoring/repair.py`, health monitors, the
outbox dead-letter recovery, alembic boot-retry (decisions.md #49),
`autonomous/self_improve.py` (prompt adaptation), `dash_training/` LoRA
pipeline + TinyLlama GGUF.

**Honest limits:** self-edits are gated by the test suite, not by wisdom —
coverage gaps are the real risk. Training runs are hardware-bound (hours on
a consumer GPU) and evaluated offline first; a worse model is never swapped
in. No unbounded self-modification: the gates are code, not vibes.

## Phase 3 — Builder skills — PLANNED

**Goal:** create websites, deploy, edit, debug — as real agent-core tools
with real verification, not "here's a sketch" answers.

**What exists already:** agent core + tool protocol, coding tools,
orchestrator DAG, executive queue.

**Being built:** scaffold → run dev server → screenshot/DOM-verify → iterate
→ deploy (static hosts / Vercel-class) → post-deploy probe. Debugging tools
read real logs and real stack traces.

**Honest limits:** deploys need the user's accounts/keys; complex sites are
iterated, not conjured in one shot.

## Phase 4 — Guardian (defensive security) — SHIPPED (decisions.md #60)

**Shipped:** `security/guardian.py` — listening-port baseline diffing,
suspicious-process patterns, failed-login burst detection (per-IP +
global, live feed + audit sweep), rate-limited notify + workflow-event
response, GUARDIAN_INCIDENT audit trail, /security/guardian* routes,
status observability. Process termination is manual-only by design.

**Goal:** defend the machine autonomously. Not offense.

**Explicitly out of scope, permanently:** creating viruses/malware,
attacking third parties. That request is refused on real grounds — it
endangers the user (criminal exposure, blacklisting, retaliation) and
contradicts the honesty principle. Defensive work is the real version of
"defend against hackers": port/process monitoring, failed-login and
anomaly detection, firewall control, quarantine actions, automatic response
runs + an honest incident log.

## Phase 5 — The DASH OS layer — PLANNED

**Goal:** using the PC feels like using DASH.

**Reality check:** replacing the Windows kernel is not a serious project for
one machine; becoming the AI operating layer over it is. Launcher + voice +
window management + workflows + vision + autonomy, always running, always
honest about what he did and why.

---

**Standing rule for every phase:** if a feature can only be demoed by
faking data, it does not ship. DASH says "I can't do that yet" more often
than most assistants — by design.
