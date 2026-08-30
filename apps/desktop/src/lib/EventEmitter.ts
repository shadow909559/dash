/**
 * Browser-safe EventEmitter shim.
 *
 * The renderer process runs with `nodeIntegration: false` and `sandbox: true`,
 * so Node.js built-ins like `events` are NOT available. This minimal, spec-like
 * implementation provides the subset of the Node EventEmitter API used across
 * the DASH renderer so no Node-only module is ever bundled into the UI.
 */

type Listener = (...args: any[]) => void;

export class EventEmitter {
  private _events: Map<string, Listener[]> = new Map();

  on(event: string, listener: Listener): this {
    if (typeof listener !== "function") {
      throw new TypeError("The listener must be a function");
    }
    const listeners = this._events.get(event);
    if (listeners) {
      listeners.push(listener);
    } else {
      this._events.set(event, [listener]);
    }
    return this;
  }

  once(event: string, listener: Listener): this {
    const wrapper: Listener = (...args: any[]) => {
      this.removeListener(event, wrapper);
      listener(...args);
    };
    // Carry the original so `removeListener` can find it.
    (wrapper as any).listener = listener;
    return this.on(event, wrapper);
  }

  addListener(event: string, listener: Listener): this {
    return this.on(event, listener);
  }

  removeListener(event: string, listener: Listener): this {
    const listeners = this._events.get(event);
    if (!listeners) return this;
    const idx = listeners.findIndex(
      (l) => l === listener || (l as any).listener === listener,
    );
    if (idx !== -1) {
      listeners.splice(idx, 1);
      if (listeners.length === 0) {
        this._events.delete(event);
      }
    }
    return this;
  }

  off(event: string, listener: Listener): this {
    return this.removeListener(event, listener);
  }

  removeAllListeners(event?: string): this {
    if (event) {
      this._events.delete(event);
    } else {
      this._events.clear();
    }
    return this;
  }

  emit(event: string, ...args: any[]): boolean {
    const listeners = this._events.get(event);
    if (!listeners || listeners.length === 0) return false;
    // Copy so listeners added/removed during emit don't affect this pass.
    for (const listener of [...listeners]) {
      listener(...args);
    }
    return true;
  }

  listeners(event: string): Listener[] {
    return [...(this._events.get(event) || [])];
  }

  listenerCount(event: string): number {
    return this._events.get(event)?.length || 0;
  }

  eventNames(): string[] {
    return [...this._events.keys()];
  }
}
