class PcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    this.pending = [];
    this.pendingLength = 0;
    this.samplesPerChunk = 3200;
  }

  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input || input.length === 0) {
      return true;
    }
    const resampled = this.resample(input, sampleRate, this.targetSampleRate);
    const pcm = this.float32ToInt16(resampled);
    this.enqueue(pcm);
    this.flushChunks();
    return true;
  }

  resample(input, sourceRate, targetRate) {
    if (sourceRate === targetRate) {
      return input;
    }
    const ratio = sourceRate / targetRate;
    const outputLength = Math.max(1, Math.round(input.length / ratio));
    const output = new Float32Array(outputLength);
    for (let i = 0; i < outputLength; i += 1) {
      const sourceIndex = i * ratio;
      const lower = Math.floor(sourceIndex);
      const upper = Math.min(lower + 1, input.length - 1);
      const weight = sourceIndex - lower;
      output[i] = input[lower] * (1 - weight) + input[upper] * weight;
    }
    return output;
  }

  float32ToInt16(input) {
    const output = new Int16Array(input.length);
    for (let i = 0; i < input.length; i += 1) {
      const sample = Math.max(-1, Math.min(1, input[i]));
      output[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }
    return output;
  }

  enqueue(pcm) {
    this.pending.push(pcm);
    this.pendingLength += pcm.length;
  }

  flushChunks() {
    while (this.pendingLength >= this.samplesPerChunk && this.pending.length > 0) {
      const chunk = new Int16Array(this.samplesPerChunk);
      let offset = 0;
      while (offset < this.samplesPerChunk && this.pending.length > 0) {
        const head = this.pending[0];
        const take = Math.min(head.length, this.samplesPerChunk - offset);
        chunk.set(head.subarray(0, take), offset);
        if (take === head.length) {
          this.pending.shift();
        } else {
          this.pending[0] = head.subarray(take);
        }
        offset += take;
        this.pendingLength -= take;
      }
      this.port.postMessage(chunk.buffer);
    }
    if (this.pending.length === 0) {
      this.pendingLength = 0;
    }
  }
}

registerProcessor("pcm-processor", PcmProcessor);
