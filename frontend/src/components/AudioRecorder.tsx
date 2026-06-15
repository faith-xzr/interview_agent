import { useEffect, useRef, useState } from "react";
import { Mic, MicOff } from "lucide-react";

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    const chunk = bytes.subarray(index, index + 0x8000);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

export default function AudioRecorder({
  isRecording,
  disabled = false,
  onRecordingChange,
  onAudioData,
  onError
}: {
  isRecording: boolean;
  disabled?: boolean;
  onRecordingChange: (value: boolean) => void;
  onAudioData: (audioData: string) => void;
  onError?: (message: string) => void;
}) {
  const [level, setLevel] = useState(0);
  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const intervalRef = useRef<number | null>(null);

  function cleanup() {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (workletRef.current) {
      workletRef.current.port.onmessage = null;
      workletRef.current.disconnect();
      workletRef.current = null;
    }
    if (analyserRef.current) {
      analyserRef.current.disconnect();
      analyserRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (contextRef.current) {
      contextRef.current.close();
      contextRef.current = null;
    }
    setLevel(0);
  }

  async function startRecording() {
    try {
      const AudioContextCtor = window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!navigator.mediaDevices?.getUserMedia || !AudioContextCtor) {
        throw new Error("当前浏览器不支持云端语音录音，请使用文本输入。");
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000
        }
      });
      const audioContext = new AudioContextCtor({ sampleRate: 16000 });
      if (!audioContext.audioWorklet) {
        throw new Error("当前浏览器不支持 AudioWorklet，请使用新版 Chrome 或 Edge。");
      }
      await audioContext.audioWorklet.addModule("/audio-worklet/pcm-processor.js");
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      const workletNode = new AudioWorkletNode(audioContext, "pcm-processor");
      const mutedGain = audioContext.createGain();
      mutedGain.gain.value = 0;
      source.connect(workletNode);
      workletNode.connect(mutedGain);
      mutedGain.connect(audioContext.destination);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      intervalRef.current = window.setInterval(() => {
        analyser.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((sum, item) => sum + item, 0) / dataArray.length;
        setLevel(average);
      }, 120);

      workletNode.port.onmessage = (event) => onAudioData(arrayBufferToBase64(event.data));
      streamRef.current = stream;
      contextRef.current = audioContext;
      workletRef.current = workletNode;
      analyserRef.current = analyser;
      onRecordingChange(true);
    } catch (error) {
      cleanup();
      onRecordingChange(false);
      onError?.(error instanceof Error ? error.message : "录音启动失败。");
    }
  }

  function stopRecording() {
    cleanup();
    onRecordingChange(false);
  }

  useEffect(() => () => cleanup(), []);

  useEffect(() => {
    if (!isRecording) {
      cleanup();
    }
  }, [isRecording]);

  return (
    <button
      className={isRecording ? "secondary-button danger" : "secondary-button"}
      type="button"
      onClick={() => (isRecording ? stopRecording() : startRecording())}
      disabled={disabled && !isRecording}
      title={isRecording ? `音量 ${Math.round(level)}` : "开始录音"}
    >
      {isRecording ? <MicOff size={16} aria-hidden="true" /> : <Mic size={16} aria-hidden="true" />}
      <span>{isRecording ? "停止录音" : "开始录音"}</span>
    </button>
  );
}
