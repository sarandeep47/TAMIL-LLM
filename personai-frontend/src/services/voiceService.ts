export class VoiceService {
  private mediaStream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private scriptProcessor: ScriptProcessorNode | null = null;
  private recordedBuffers: Float32Array[] = [];
  private isRecording = false;

  async startRecording(): Promise<void> {
    try {
      this.recordedBuffers = [];
      
      // Get microphone access
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });

      // Create audio context
      this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 16000,
      });

      const source = this.audioContext.createMediaStreamSource(this.mediaStream);

      // Create script processor for direct audio capture
      this.scriptProcessor = this.audioContext.createScriptProcessor(4096, 1, 1);

      this.scriptProcessor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        this.recordedBuffers.push(new Float32Array(inputData));
      };

      source.connect(this.scriptProcessor);
      this.scriptProcessor.connect(this.audioContext.destination);

      this.isRecording = true;
    } catch (error) {
      console.error('Microphone access error:', error);
      throw new Error('Failed to access microphone. Please check permissions.');
    }
  }

  async stopRecording(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      try {
        if (!this.audioContext || !this.scriptProcessor) {
          reject(new Error('Recording not started'));
          return;
        }

        // Disconnect and close recording
        this.scriptProcessor.disconnect();
        if (this.mediaStream) {
          this.mediaStream.getTracks().forEach(track => track.stop());
        }
        if (this.audioContext && this.audioContext.state !== 'closed') {
          this.audioContext.close();
        }

        this.isRecording = false;

        // Merge recorded buffers
        const totalLength = this.recordedBuffers.reduce((acc, curr) => acc + curr.length, 0);
        const mergedSamples = new Float32Array(totalLength);
        let offset = 0;
        for (const buf of this.recordedBuffers) {
          mergedSamples.set(buf, offset);
          offset += buf.length;
        }

        // Create WAV blob
        const wavBlob = this.encodeWAV(mergedSamples, 16000);
        resolve(wavBlob);
      } catch (error) {
        reject(error);
      }
    });
  }

  private encodeWAV(samples: Float32Array, sampleRate: number): Blob {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    // WAV header
    const writeString = (offset: number, string: string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    };

    writeString(0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(36, 'data');
    view.setUint32(40, samples.length * 2, true);

    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }

    return new Blob([view], { type: 'audio/wav' });
  }

  playText(text: string, rate: number = 0.7): Promise<void> {
    return new Promise((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'ta-IN';
      utterance.rate = rate;
      utterance.pitch = 1;
      utterance.volume = 1;

      const voices = window.speechSynthesis.getVoices();
      const tamilVoice = voices.find(v => v.lang.includes('ta'));
      if (tamilVoice) {
        utterance.voice = tamilVoice;
      }

      utterance.onend = () => resolve();
      window.speechSynthesis.speak(utterance);
    });
  }

  stopPlayback(): void {
    window.speechSynthesis.cancel();
  }

  isCurrentlyRecording(): boolean {
    return this.isRecording;
  }
}

export const voiceService = new VoiceService();
