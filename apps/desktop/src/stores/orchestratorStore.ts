/**
 * Orchestrator Store — tracks multi-agent task execution.
 *
 * Listens for orchestrator.* events from the WebSocket and maintains
 * the current run state, steps, and progress.
 */
import { create } from "zustand";

interface OrchestratorStep {
  id: string;
  index: number;
  description: string;
  type: string;
  status: string;
  result: string;
  error: string;
  agent: string;
  duration_ms: number;
}

interface OrchestratorState {
  /** Current or last run ID */
  runId: string | null;
  /** Overall status: idle | planning | running | complete | error */
  status: string;
  /** Status message shown to user */
  message: string;
  /** Steps from the plan */
  steps: OrchestratorStep[];
  /** Index of the currently running step */
  currentStep: number;
  /** Summary after completion */
  summary: string;
  /** Error message if failed */
  error: string;

  // Actions
  startRun: (task: string) => void;
  handleEvent: (type: string, data: Record<string, unknown>) => void;
  reset: () => void;
}

const INITIAL_STATE = {
  runId: null,
  status: "idle" as string,
  message: "",
  steps: [] as OrchestratorStep[],
  currentStep: -1,
  summary: "",
  error: "",
};

export const useOrchestratorStore = create<OrchestratorState>((set, get) => ({
  ...INITIAL_STATE,

  startRun: (_task: string) => {
    set({
      ...INITIAL_STATE,
      status: "planning",
      message: "Breaking down your task...",
    });
  },

  handleEvent: (type: string, data: Record<string, unknown>) => {
    const event = type.replace("orchestrator.", "");

    switch (event) {
      case "status":
        set({
          status: (data.status as string) || "running",
          message: (data.message as string) || "",
        });
        break;

      case "plan":
        set({
          runId: (data.run_id as string) || get().runId,
          steps: (data.steps as OrchestratorStep[]) || [],
          status: "running",
          message: `Executing ${data.total} steps...`,
          currentStep: 0,
        });
        break;

      case "step_start": {
        const step = data.step as OrchestratorStep;
        set((state) => {
          const steps = [...state.steps];
          if (step && steps[step.index]) {
            steps[step.index] = { ...steps[step.index], ...step };
          }
          return { steps, currentStep: step?.index ?? state.currentStep };
        });
        break;
      }

      case "step_done": {
        const step = data.step as OrchestratorStep;
        set((state) => {
          const steps = [...state.steps];
          if (step && steps[step.index]) {
            steps[step.index] = { ...steps[step.index], ...step };
          }
          const completed = steps.filter((s) => s.status === "completed").length;
          return {
            steps,
            message: `Step ${completed}/${steps.length} complete`,
          };
        });
        break;
      }

      case "step_error": {
        const step = data.step as OrchestratorStep;
        set((state) => {
          const steps = [...state.steps];
          if (step && steps[step.index]) {
            steps[step.index] = { ...steps[step.index], ...step };
          }
          return { steps };
        });
        break;
      }

      case "complete":
        set({
          status: "complete",
          summary: (data.summary as string) || "",
          message: `Done! ${data.completed}/${data.total} steps succeeded.`,
          steps: (data.steps as OrchestratorStep[]) || get().steps,
        });
        break;

      case "error":
        set({
          status: "error",
          error: (data.error as string) || "Unknown error",
          message: "Orchestration failed",
        });
        break;

      case "cancelled":
        set({
          status: "idle",
          message: "Cancelled",
        });
        break;
    }
  },

  reset: () => set(INITIAL_STATE),
}));
