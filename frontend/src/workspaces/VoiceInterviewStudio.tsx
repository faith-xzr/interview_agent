import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  Bot,
  FileText,
  Loader2,
  Send,
  Volume2
} from "lucide-react";

import {
  connectVoiceInterviewWebSocket,
  createVoiceInterviewSession,
  finalizeInterview,
  submitInterviewTurn,
  type VoiceInterviewWebSocket
} from "../api";
import AudioRecorder from "../components/AudioRecorder";
import { InterviewFinalReportCard } from "../components/InterviewFinalReportCard";
import type {
  CandidateReport,
  InterviewSession,
  InterviewTurnInputMetadata
} from "../types";

type VoiceMessage = {
  id: string;
  role: "interviewer" | "user";
  text: string;
  badge?: string;
  metadata?: string;
};

function base64ToInt16Array(base64: string): Int16Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Int16Array(bytes.buffer);
}

function pcmBase64ToAudioBuffer(audioContext: AudioContext, base64: string, sampleRate = 24000) {
  const samples = base64ToInt16Array(base64);
  const buffer = audioContext.createBuffer(1, samples.length, sampleRate);
  const channel = buffer.getChannelData(0);
  for (let index = 0; index < samples.length; index += 1) {
    channel[index] = samples[index] / 32768;
  }
  return buffer;
}

class PcmAudioPlaybackQueue {
  private nextPlayTime = 0;
  private sources = new Set<AudioBufferSourceNode>();
  private queue = Promise.resolve();
  private generation = 0;
  private finishTimer: number | null = null;

  constructor(private audioContext: AudioContext) {}

  enqueue(base64: string, sampleRate = 24000) {
    const generation = this.generation;
    this.queue = this.queue.then(() => this.schedule(base64, sampleRate, generation));
    return this.queue;
  }

  reset() {
    this.generation += 1;
    this.queue = Promise.resolve();
    this.clearFinishTimer();
    for (const source of this.sources) {
      try {
        const stoppable = source as AudioBufferSourceNode & { stop?: () => void };
        if (typeof stoppable.stop === "function") {
          stoppable.stop();
        }
      } catch {
        // The source may already have ended.
      }
    }
    this.sources.clear();
    this.nextPlayTime = this.audioContext.currentTime;
  }

  finish(onDone: () => void) {
    const generation = this.generation;
    this.queue = this.queue.then(() => {
      if (generation !== this.generation) {
        return;
      }
      this.clearFinishTimer();
      const delayMs = Math.max(0, this.nextPlayTime - this.audioContext.currentTime) * 1000;
      this.finishTimer = window.setTimeout(() => {
        if (generation === this.generation) {
          onDone();
        }
      }, delayMs + 30);
    });
  }

  async close() {
    this.reset();
    await this.audioContext.close();
  }

  private async schedule(base64: string, sampleRate: number, generation: number) {
    if (!base64 || generation !== this.generation) {
      return;
    }
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }
    if (generation !== this.generation) {
      return;
    }
    const buffer = pcmBase64ToAudioBuffer(this.audioContext, base64, sampleRate);
    const source = this.audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(this.audioContext.destination);
    source.onended = () => {
      this.sources.delete(source);
    };
    const startAt = Math.max(this.audioContext.currentTime, this.nextPlayTime);
    this.nextPlayTime = startAt + buffer.duration;
    this.sources.add(source);
    source.start(startAt);
  }

  private clearFinishTimer() {
    if (this.finishTimer !== null) {
      window.clearTimeout(this.finishTimer);
      this.finishTimer = null;
    }
  }
}

function createPcmAudioPlaybackQueue() {
  const AudioContextCtor = window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextCtor) {
    return null;
  }
  return new PcmAudioPlaybackQueue(new AudioContextCtor());
}

export default function VoiceInterviewStudio({
  candidate,
  session,
  onExit,
  onSessionChange
}: {
  candidate: CandidateReport;
  session: InterviewSession;
  onExit: () => void;
  onSessionChange: (session: InterviewSession) => void;
}) {
  const [candidateAnswer, setCandidateAnswer] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answerMetadata, setAnswerMetadata] = useState<InterviewTurnInputMetadata | null>(null);
  const [realtimeSubtitle, setRealtimeSubtitle] = useState("");

  const socketRef = useRef<VoiceInterviewWebSocket | null>(null);
  const audioPlaybackQueueRef = useRef<PcmAudioPlaybackQueue | null>(null);
  const onSessionChangeRef = useRef(onSessionChange);

  const currentQuestionText = session.current_question?.question ?? "";

  useEffect(() => {
    onSessionChangeRef.current = onSessionChange;
  }, [onSessionChange]);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    createVoiceInterviewSession(session.session_id)
      .then((created) => {
        if (cancelled) {
          return;
        }
        const socket = connectVoiceInterviewWebSocket(created.websocket_url, {
          onOpen: () => undefined,
          onClose: () => undefined,
          onError: (message) => {
            setIsSubmitting(false);
            setError(message);
          },
          onControl: (action, message) => {
            if (action === "ready") {
              setError(null);
            } else if (message && action === "error") {
              setError(message);
            }
          },
          onSubtitle: (text, isFinal) => {
            setRealtimeSubtitle(text);
            setCandidateAnswer(text);
            setAnswerMetadata({
              source: "speech",
              transcript: text,
              locale: "zh-CN",
              finalized: isFinal,
              raw_text: text
            });
          },
          onInterviewSession: (nextSession) => {
            setIsSubmitting(false);
            setCandidateAnswer("");
            setAnswerMetadata(null);
            setRealtimeSubtitle("");
            onSessionChangeRef.current(nextSession);
          },
          onAudioChunk: (data, index, isLast) => {
            if (isLast) {
              audioPlaybackQueueRef.current?.finish(() => setIsSpeaking(false));
              return;
            }
            try {
              if (!audioPlaybackQueueRef.current) {
                audioPlaybackQueueRef.current = createPcmAudioPlaybackQueue();
              }
              if (!audioPlaybackQueueRef.current) {
                return;
              }
              if (index === 0) {
                audioPlaybackQueueRef.current.reset();
              }
              setIsSpeaking(true);
              void audioPlaybackQueueRef.current.enqueue(data).catch(() => setIsSpeaking(false));
            } catch {
              setIsSpeaking(false);
            }
          }
        });
        socketRef.current = socket;
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "语音面试会话创建失败。");
        }
      });

    return () => {
      cancelled = true;
      socketRef.current?.disconnect();
      socketRef.current = null;
      if (audioPlaybackQueueRef.current) {
        void audioPlaybackQueueRef.current.close();
        audioPlaybackQueueRef.current = null;
      }
    };
  }, [session.session_id]);

  const buildAnswerMetadata = (): InterviewTurnInputMetadata => {
    const text = candidateAnswer.trim();
    return {
      source: answerMetadata?.source === "speech" ? "speech" : "text",
      transcript: text,
      confidence: answerMetadata?.confidence,
      locale: answerMetadata?.locale || "zh-CN",
      finalized: true,
      raw_text: text
    };
  };

  const handleAudioData = (audioData: string) => {
    const socket = socketRef.current;
    if (!socket?.sendAudio(audioData)) {
      setError("云端语音通道未连接，请稍后重试或直接输入文本。");
    }
  };

  const handleSubmit = async () => {
    const text = candidateAnswer.trim();
    if (!session.current_question || !text || isSubmitting || isFinalizing) {
      return;
    }
    setError(null);
    setIsSubmitting(true);
    if (socketRef.current?.isConnected()) {
      if (!socketRef.current.submitText(text)) {
        setIsSubmitting(false);
        setError("云端语音通道未连接，请稍后重试。");
      }
      return;
    }
    try {
      const nextSession = await submitInterviewTurn({
        sessionId: session.session_id,
        candidateAnswer: text,
        answerMetadata: buildAnswerMetadata()
      });
      setCandidateAnswer("");
      setAnswerMetadata(null);
      onSessionChangeRef.current(nextSession);
    } catch (err) {
      setError(err instanceof Error ? err.message : "回答提交失败，请稍后重试。");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFinalize = async () => {
    if (isFinalizing) return;
    if (!session.turns.length && !session.final_report) {
      setError("请先完成一轮回答后再生成报告。");
      return;
    }
    setIsFinalizing(true);
    setError(null);
    try {
      const nextSession = await finalizeInterview(session.session_id);
      onSessionChangeRef.current(nextSession);
    } catch (err) {
      setError(err instanceof Error ? err.message : "最终报告生成失败，请稍后重试。");
    } finally {
      setIsFinalizing(false);
    }
  };

  const handleReplayQuestion = () => {
    if (!currentQuestionText) {
      setError("当前没有可朗读的问题。");
      return;
    }
    if (!socketRef.current?.speakCurrentQuestion()) {
      setError("云端语音通道未连接，请稍后重试。");
    }
  };

  const canSubmit = candidateAnswer.trim().length > 0 && !isSubmitting && !isFinalizing;

  const messages: VoiceMessage[] = useMemo(() => {
    const items: VoiceMessage[] = [];
    for (const turn of session.turns) {
      items.push({
        id: `q-${turn.turn_index}`,
        role: "interviewer",
        badge: "面试官提问",
        text: turn.question.question
      });
      items.push({
        id: `a-${turn.turn_index}`,
        role: "user",
        badge: turn.answer_source === "text" ? "文本作答" : "语音作答",
        text: turn.answer
      });
      if (turn.diagnosis.followup_needed && turn.diagnosis.followup_question) {
        items.push({
          id: `f-${turn.turn_index}`,
          role: "interviewer",
          badge: "AI 追问",
          text: turn.diagnosis.followup_question,
          metadata: `clarity ${turn.diagnosis.clarity_score} · depth ${turn.diagnosis.depth_score} · ${turn.diagnosis.evidence_consistency}`
        });
      }
    }
    if (session.current_question) {
      items.push({
        id: "current-interview-question",
        role: "interviewer",
        badge: "当前问题",
        text: session.current_question.question
      });
    }
    if (candidateAnswer.trim()) {
      items.push({
        id: "draft-answer",
        role: "user",
        badge: answerMetadata?.source === "speech" ? "实时转写" : "候选人当前输入",
        text: candidateAnswer
      });
    }
    return items;
  }, [session.turns, session.current_question, candidateAnswer, answerMetadata?.source]);

  return (
    <section className="voice-studio card">
      <header className="voice-studio-header">
        <div className="voice-header-primary">
          <button className="voice-back-button secondary-button subtle" type="button" onClick={onExit}>
            <ArrowLeft size={16} aria-hidden="true" />
            <span>返回配置</span>
          </button>
          <div>
            <h2>语音模拟面试</h2>
          </div>
        </div>
      </header>

      <div className="voice-studio-content">
        <section className="voice-stage">
          <div className="voice-stage-stage-card">
            <div className="voice-stage-avatar" role="img" aria-label="interviewer-avatar">
              <Bot size={34} aria-hidden="true" />
            </div>
            <div className="voice-stage-question" aria-live="polite">
              {currentQuestionText ? currentQuestionText : "当前问题已结束，请生成最终报告。"}
            </div>
          </div>

          {realtimeSubtitle ? (
            <div className="voice-answer-hint" aria-live="polite">
              <strong>实时转写</strong>
              <span>{realtimeSubtitle}</span>
            </div>
          ) : null}

          <div className="voice-answer-block">
            <label htmlFor={`voice-answer-${session.session_id}`}>你的回答（可编辑）</label>
            <textarea
              className="voice-answer-textarea"
              id={`voice-answer-${session.session_id}`}
              value={candidateAnswer}
              onChange={(event) => {
                const value = event.target.value;
                setCandidateAnswer(value);
                setAnswerMetadata({
                  source: "text",
                  transcript: value,
                  finalized: true,
                  locale: "zh-CN",
                  raw_text: value
                });
              }}
              rows={6}
            />
          </div>

          <div className="voice-stage-actions">
            <AudioRecorder
              disabled={isSubmitting || isFinalizing || !session.current_question}
              isRecording={isRecording}
              onAudioData={handleAudioData}
              onError={setError}
              onRecordingChange={setIsRecording}
            />
            <button className="secondary-button subtle" type="button" onClick={handleReplayQuestion} disabled={isSubmitting || isFinalizing}>
              <Volume2 size={16} aria-hidden="true" />
              <span>重听问题</span>
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={handleSubmit}
              disabled={!canSubmit || isSubmitting || !session.current_question}
            >
              {isSubmitting ? <Loader2 size={16} aria-hidden="true" className="spin" /> : <Send size={16} aria-hidden="true" />}
              <span>{isSubmitting ? "提交中" : "提交回答"}</span>
            </button>
          </div>

          {session.current_question ? null : (
            <button className="secondary-button" type="button" onClick={handleFinalize} disabled={isFinalizing}>
              {isFinalizing ? <Loader2 size={16} aria-hidden="true" className="spin" /> : <FileText size={16} aria-hidden="true" />}
              <span>{isFinalizing ? "生成中" : "生成最终报告"}</span>
            </button>
          )}
        </section>

        <section className="voice-timeline-wrap">
          <h4>实时语音记录</h4>
          <div className="voice-timeline">
            {messages.length ? (
              messages.map((item) => (
                <article className={`voice-bubble ${item.role === "user" ? "voice-bubble-user" : "voice-bubble-ai"}`} key={item.id}>
                  <div className="voice-bubble-meta">
                    <span>{item.badge ?? "系统"}</span>
                    {item.metadata ? <small>{item.metadata}</small> : null}
                  </div>
                  <p>{item.text}</p>
                </article>
              ))
            ) : (
              <p className="voice-empty">还没有任何对话记录。</p>
            )}
          </div>
        </section>
      </div>

      {error ? (
        <div className="error-box" role="alert">
          <AlertCircle size={18} aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}

      {session.final_report ? <InterviewFinalReportCard report={session.final_report} /> : null}
    </section>
  );
}
