/**
 * A simple wrapper around the MediaRecorder API to handle audio recording.
 */
class AudioRecorder {
  private mediaRecorder: MediaRecorder | null = null;
  private audioChunks: Blob[] = [];

  /**
   * Check if recording is currently active.
   */
  isRecording(): boolean {
    return this.mediaRecorder?.state === "recording";
  }

  /**
   * Start recording audio from the user's microphone.
   * @returns {Promise<void>} A promise that resolves when recording has started.
   */
  async start(): Promise<void> {
    if (this.isRecording()) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.mediaRecorder = new MediaRecorder(stream);
      this.audioChunks = [];

      this.mediaRecorder.ondataavailable = (event) => {
        this.audioChunks.push(event.data);
      };

      this.mediaRecorder.start();
    } catch (err) {
      console.error("Error starting audio recording:", err);
      throw new Error("Microphone access was denied or an error occurred.");
    }
  }

  /**
   * Stop recording audio.
   * @returns {Promise<string>} A promise that resolves with the Base64-encoded audio data.
   */
  async stop(): Promise<string> {
    if (!this.isRecording() || !this.mediaRecorder) {
      throw new Error("Recording is not active.");
    }

    return new Promise((resolve) => {
      const recorder = this.mediaRecorder;
      if (!recorder) {
        throw new Error("Recording is not active.");
      }

      recorder.onstop = () => {
        const audioBlob = new Blob(this.audioChunks, { type: "audio/webm" });
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64String = (reader.result as string).split(",")[1];
          resolve(base64String);
        };
        reader.readAsDataURL(audioBlob);

        // Clean up stream
        recorder.stream.getTracks().forEach(track => track.stop());
        this.mediaRecorder = null;
      };

      recorder.stop();
    });
  }
}

const mediaRecorder = new AudioRecorder();
export default mediaRecorder;