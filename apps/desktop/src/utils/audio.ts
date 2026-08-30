class SoundController {
  private ctx: AudioContext | null = null;
  private humOsc: OscillatorNode | null = null;
  private humGain: GainNode | null = null;
  private isHumPlaying = false;

  private initCtx() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.ctx = new AudioCtx();
    }
    if (this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  playBeep(freq = 880, type: OscillatorType = 'sine', duration = 0.08, gainVal = 0.05) {
    try {
      this.initCtx();
      if (!this.ctx) return;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);

      gain.gain.setValueAtTime(gainVal, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, this.ctx.currentTime + duration);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch {
      // Audio permission or unsupported context
    }
  }

  playClick() {
    this.playBeep(1200, 'sine', 0.04, 0.04);
  }

  playScanPing() {
    try {
      this.initCtx();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(1400, now);
      osc.frequency.exponentialRampToValueAtTime(400, now + 0.15);

      gain.gain.setValueAtTime(0.08, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start(now);
      osc.stop(now + 0.15);
    } catch {
      // Ignore
    }
  }

  playTargetLock() {
    try {
      this.initCtx();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      
      // Two quick high tones
      [0, 0.07, 0.14].forEach((delay, idx) => {
        const osc = this.ctx!.createOscillator();
        const gain = this.ctx!.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(900 + idx * 300, now + delay);
        gain.gain.setValueAtTime(0.08, now + delay);
        gain.gain.exponentialRampToValueAtTime(0.001, now + delay + 0.06);

        osc.connect(gain);
        gain.connect(this.ctx!.destination);
        osc.start(now + delay);
        osc.stop(now + delay + 0.06);
      });
    } catch {
      // Ignore
    }
  }

  toggleAmbientHum(enable: boolean) {
    try {
      this.initCtx();
      if (!this.ctx) return;

      if (enable && !this.isHumPlaying) {
        this.humOsc = this.ctx.createOscillator();
        this.humGain = this.ctx.createGain();

        this.humOsc.type = 'sine';
        this.humOsc.frequency.setValueAtTime(55, this.ctx.currentTime); // Low 55Hz drone

        this.humGain.gain.setValueAtTime(0.015, this.ctx.currentTime);

        this.humOsc.connect(this.humGain);
        this.humGain.connect(this.ctx.destination);

        this.humOsc.start();
        this.isHumPlaying = true;
      } else if (!enable && this.isHumPlaying) {
        if (this.humGain) {
          this.humGain.gain.linearRampToValueAtTime(0.0001, this.ctx.currentTime + 0.3);
          setTimeout(() => {
            this.humOsc?.stop();
            this.humOsc?.disconnect();
            this.isHumPlaying = false;
          }, 350);
        }
      }
    } catch {
      // Ignore
    }
  }
}

export const soundFx = new SoundController();
