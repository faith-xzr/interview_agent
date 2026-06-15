import {
  AlertCircle,
  ArrowUpRight,
  Bot,
  FileText,
  HeartHandshake,
  Loader2,
  MessageCircle,
  Mic,
  MicOff,
  RefreshCw,
  ShieldAlert,
  Volume2,
  Sparkles,
  type LucideIcon
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState, type ReactNode } from "react";

import { finalizeInterview, getSkillRoute, startInterview, submitInterviewTurn } from "../api";
import { InterviewFinalReportCard } from "../components/InterviewFinalReportCard";
import { List } from "../components/List";
import { PageTitle } from "../components/PageTitle";
import { consistencyLabel, questionSourceLabel, sessionStatusLabel } from "../interviewDisplay";
import { hasQuestionMaterials } from "../matchReportDisplay";
import type { CandidateReport, InterviewSession, InterviewTurnInputMetadata, RunReport, SkillRouteResult } from "../types";
import VoiceInterviewStudio from "./VoiceInterviewStudio";

type InterviewMode = "text" | "voice";
type InterviewDifficulty = "campus" | "mid" | "senior";
type InterviewerStyle = "friendly_hr" | "strict_manager";

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onresult: ((event: any) => void) | null;
  onnomatch: (() => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

const DIFFICULTY_OPTIONS: Array<{ id: InterviewDifficulty; label: string; desc: string }> = [
  { id: "campus", label: "校招", desc: "0-1 年" },
  { id: "mid", label: "中级", desc: "1-3 年" },
  { id: "senior", label: "高级", desc: "3 年+" }
];

const INTERVIEWER_STYLES: Array<{ id: InterviewerStyle; label: string; desc: string; icon: LucideIcon }> = [
  { id: "friendly_hr", label: "亲切的 HR", desc: "更关注动机、表达与稳定性", icon: HeartHandshake },
  { id: "strict_manager", label: "严厉的面试主管", desc: "更关注证据、边界与抗压表现", icon: ShieldAlert }
];

export function MockInterviewWorkspace({
  report,
  selectedCandidate,
  onSelectCandidate,
  onSessionChange
}: {
  report: RunReport | null;
  selectedCandidate: CandidateReport | null;
  onSelectCandidate: (id: string) => void;
  onSessionChange: (session: InterviewSession) => void;
}) {
  const [mode, setMode] = useState<InterviewMode>("text");
  const [activeVoiceSession, setActiveVoiceSession] = useState<InterviewSession | null>(null);
  const [difficulty, setDifficulty] = useState<InterviewDifficulty>("mid");
  const [interviewerStyle, setInterviewerStyle] = useState<InterviewerStyle>("friendly_hr");
  const [skillRoute, setSkillRoute] = useState<SkillRouteResult | null>(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState<string | null>(null);
  const canStartInterview = selectedCandidate
    ? hasQuestionMaterials(selectedCandidate.match_report)
    : false;

  useEffect(() => {
    let cancelled = false;
    setSkillRoute(null);
    setRouteError(null);
    if (!report) {
      setRouteLoading(false);
      return;
    }
    setRouteLoading(true);
    getSkillRoute(report.run_id)
      .then((result) => {
        if (!cancelled) {
          setSkillRoute(result);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setRouteError(err instanceof Error ? err.message : "JD skill 路由失败。");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setRouteLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [report?.run_id]);

  useEffect(() => {
    if (!selectedCandidate) {
      setActiveVoiceSession(null);
      return;
    }
    if (activeVoiceSession && activeVoiceSession.candidate_id !== selectedCandidate.candidate_id) {
      setActiveVoiceSession(null);
    }
  }, [selectedCandidate?.candidate_id]);

  function syncVoiceSession(nextSession: InterviewSession) {
    setActiveVoiceSession((current) => (current?.session_id === nextSession.session_id ? nextSession : current));
    onSessionChange(nextSession);
  }

  return (
    <div className="workspace-stack">
      <PageTitle icon={Sparkles} title="模拟面试" />
      {activeVoiceSession && selectedCandidate ? (
        <VoiceInterviewStudio
          candidate={selectedCandidate}
          onExit={() => setActiveVoiceSession(null)}
          onSessionChange={syncVoiceSession}
          session={activeVoiceSession}
        />
      ) : (
        <>
          <section className="card interview-config-card">
            <ConfigSection title="面试模式">
              <div className="config-grid two">
                <OptionCard
                  active={mode === "text"}
                  description="推荐：更稳定，更适合系统化刷题与复盘"
                  icon={FileText}
                  label="文字面试"
                  onClick={() => setMode("text")}
                  badge="推荐"
                />
                <OptionCard
                  active={mode === "voice"}
                  description="实时语音对话，更偏临场模拟"
                  icon={MessageCircle}
                  label="语音面试"
                  onClick={() => setMode("voice")}
                />
              </div>
            </ConfigSection>

            <ConfigSection title="JD 自动路由调试">
              <SkillRouteDebugPanel
                jobTitle={report?.jd_profile.job_title ?? "暂无 JD 分组"}
                loading={routeLoading}
                route={skillRoute}
                error={routeError}
              />
            </ConfigSection>

            <ConfigSection title="难度">
              <div className="config-grid three">
                {DIFFICULTY_OPTIONS.map((item) => (
                  <button
                    className={difficulty === item.id ? "difficulty-card active" : "difficulty-card"}
                    key={item.id}
                    onClick={() => setDifficulty(item.id)}
                    type="button"
                  >
                    <strong>{item.label}</strong>
                    <span>{item.desc}</span>
                  </button>
                ))}
              </div>
            </ConfigSection>

            <ConfigSection title="面试官风格">
              <div className="config-grid two">
                {INTERVIEWER_STYLES.map((item) => (
                  <OptionCard
                    active={interviewerStyle === item.id}
                    description={item.desc}
                    icon={item.icon}
                    key={item.id}
                    label={item.label}
                    onClick={() => setInterviewerStyle(item.id)}
                  />
                ))}
              </div>
            </ConfigSection>

            {report && selectedCandidate ? (
              <div className="interview-candidate-strip">
                <label htmlFor="interview-candidate">面试候选人</label>
                <select
                  id="interview-candidate"
                  aria-label="面试候选人"
                  value={selectedCandidate.candidate_id}
                  onChange={(event) => onSelectCandidate(event.target.value)}
                >
                  {report.candidates.map((candidate) => (
                    <option key={candidate.candidate_id} value={candidate.candidate_id}>
                      {candidate.profile.name} · {candidate.match_report.total_score} 分
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
          </section>

          {report && selectedCandidate && canStartInterview ? (
            <section className="card interview-run-card">
              <InterviewRoom
                candidate={selectedCandidate}
                runId={report.run_id}
                config={{ mode, difficulty, interviewerStyle, skillRoute }}
                onSessionChange={syncVoiceSession}
                onStartVoiceSession={setActiveVoiceSession}
              />
            </section>
          ) : report && selectedCandidate ? (
            <div className="card empty-state compact-empty">
              <h2>暂不建议开始模拟面试</h2>
              <p>当前候选人未生成面试题，建议先完成岗位匹配审核后再开始 AI 面试。</p>
            </div>
          ) : (
            <div className="card empty-state compact-empty">
              <h2>暂无可面试候选人</h2>
              <p>请先在简历管理中完成一个 JD 分组的简历分析。</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ConfigSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="config-section">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function OptionCard({
  active,
  badge,
  compact,
  description,
  icon: Icon,
  label,
  onClick
}: {
  active: boolean;
  badge?: string;
  compact?: boolean;
  description?: string;
  icon: LucideIcon;
  label: string;
  onClick: () => void;
}) {
  return (
    <button className={`${compact ? "option-card compact" : "option-card"}${active ? " active" : ""}`} onClick={onClick} type="button">
      <span className="option-icon"><Icon size={compact ? 18 : 24} aria-hidden="true" /></span>
      <span>
        <strong>{label}</strong>
        {badge ? <em>{badge}</em> : null}
        {description ? <small>{description}</small> : null}
      </span>
    </button>
  );
}

function SkillRouteDebugPanel({
  error,
  jobTitle,
  loading,
  route
}: {
  error: string | null;
  jobTitle: string;
  loading: boolean;
  route: SkillRouteResult | null;
}) {
  return (
    <div className="skill-route-panel">
      <div className="skill-route-heading">
        <span className="option-icon"><Bot size={20} aria-hidden="true" /></span>
        <div>
          <strong>{route ? route.route_result : jobTitle}</strong>
          <small>{loading ? "正在根据 JD 自动匹配 skill..." : "基于简历管理中的 JD 分组自动路由"}</small>
        </div>
      </div>
      {route ? (
        <>
          <div className="route-debug-grid">
            <RouteDebugItem label="岗位名称" value={route.position_name} />
            <RouteDebugItem label="路由结果" value={route.route_result} />
            <RouteDebugItem label="Skill" value={`${route.skill_name} (${route.skill_id})`} />
            <RouteDebugItem label="置信度" value={`${Math.round(route.confidence * 100)}%`} />
            <RouteDebugItem label="来源" value={routeSourceLabel(route.source)} />
          </div>
          <p className="route-reason">{route.reason}</p>
        </>
      ) : error ? (
        <div className="route-warning">
          <AlertCircle size={16} aria-hidden="true" />
          <span>{error} 开始面试时将由后端按 JD 兜底。</span>
        </div>
      ) : (
        <div className="route-placeholder">
          {loading ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <Bot size={16} aria-hidden="true" />}
          <span>{loading ? "路由中" : "等待选择 JD 分组"}</span>
        </div>
      )}
    </div>
  );
}

function RouteDebugItem({ label, value }: { label: string; value: string }) {
  return (
    <span className="route-debug-item">
      <small>{label}</small>
      <strong>{value}</strong>
    </span>
  );
}

function routeSourceLabel(source: string) {
  if (source === "llm") return "模型路由";
  if (source === "keyword") return "关键词兜底";
  if (source === "fallback") return "通用兜底";
  return source || "未知";
}

function InterviewRoom({
  candidate,
  config,
  onSessionChange,
  onStartVoiceSession,
  runId
}: {
  candidate: CandidateReport;
  config: {
    mode: InterviewMode;
    difficulty: InterviewDifficulty;
    interviewerStyle: InterviewerStyle;
    skillRoute: SkillRouteResult | null;
  };
  onSessionChange?: (session: InterviewSession) => void;
  onStartVoiceSession?: (session: InterviewSession) => void;
  runId: string;
}) {
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [candidateAnswer, setCandidateAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speechSupported, setSpeechSupported] = useState<boolean>(false);
  const [answerSource, setAnswerSource] = useState<"text" | "speech">("text");
  const [answerMetadata, setAnswerMetadata] = useState<InterviewTurnInputMetadata | null>(null);
  const answerId = `interview-answer-${candidate.candidate_id}`;
  const recognitionRef = useRef<any>(null);
  const transcriptBufferRef = useRef("");
  const lastSpokenQuestionRef = useRef("");
  const isVoiceMode = config.mode === "voice";

  useEffect(() => {
    setSession(null);
    setCandidateAnswer("");
    setError(null);
    setAnswerSource("text");
    setAnswerMetadata(null);
    setIsListening(false);
    setIsSpeaking(false);
    lastSpokenQuestionRef.current = "";
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
    }
  }, [candidate.candidate_id, runId]);

  useEffect(() => {
    const speechRecognitionCtor = (
      window as Window & { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor }
    ).SpeechRecognition || (window as Window & { webkitSpeechRecognition?: SpeechRecognitionCtor }).webkitSpeechRecognition;
    setSpeechSupported(typeof speechRecognitionCtor === "function");
  }, []);

  useEffect(() => {
    const currentQuestion = session?.current_question?.question;
    if (!isVoiceMode || !currentQuestion) {
      return;
    }
    if (!window.speechSynthesis) {
      setError("当前浏览器不支持语音播报，将继续以文本方式显示问题。");
      return;
    }
    if (currentQuestion === lastSpokenQuestionRef.current) {
      return;
    }
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
    }
    const utterance = new SpeechSynthesisUtterance(currentQuestion);
    utterance.lang = "zh-CN";
    utterance.rate = 1;
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    lastSpokenQuestionRef.current = currentQuestion;
    window.speechSynthesis.speak(utterance);
  }, [session?.current_question?.question, isVoiceMode]);

  useEffect(() => {
    return () => {
      const recognition = recognitionRef.current;
      if (recognition) {
        try {
          recognition.stop();
        } catch {
          // ignore
        }
        recognitionRef.current = null;
      }
      if (window.speechSynthesis?.speaking) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  function getSpeechRecognition() {
    return (
      (window as Window & { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor }).SpeechRecognition
      || (window as Window & { webkitSpeechRecognition?: SpeechRecognitionCtor }).webkitSpeechRecognition
    );
  }

  function stopListening() {
    const recognition = recognitionRef.current;
    if (!recognition) {
      return;
    }
    try {
      recognition.stop();
    } catch {
      // ignore
    }
    recognitionRef.current = null;
    setIsListening(false);
  }

  function handleStartListening() {
    if (!speechSupported) {
      setError("当前浏览器不支持语音识别，请手动输入答案。");
      return;
    }
    if (isListening) {
      stopListening();
      setAnswerMetadata((previous) => previous ? { ...previous, finalized: true } : null);
      return;
    }
    const RecognitionCtor = getSpeechRecognition();
    if (typeof RecognitionCtor !== "function") {
      setError("当前浏览器不支持语音识别，请手动输入答案。");
      return;
    }

    try {
      const recognition = new RecognitionCtor();
      recognitionRef.current = recognition;
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "zh-CN";
      recognition.maxAlternatives = 1;
      transcriptBufferRef.current = candidateAnswer.trim();
      setAnswerSource("speech");
      setError(null);
      setIsListening(true);
      setAnswerMetadata({
        source: "speech",
        transcript: transcriptBufferRef.current,
        locale: recognition.lang,
        finalized: false
      });
      recognition.onresult = (event: any) => {
        let interimText = "";
        let confidence = 0;
        let confidenceCount = 0;
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index];
          if (!result || result.length === 0) {
            continue;
          }
          const item = result[0];
          const chunk = (item?.transcript || "").trim();
          if (!chunk) {
            continue;
          }
          if (result.isFinal) {
            transcriptBufferRef.current = `${transcriptBufferRef.current} ${chunk}`.trim();
          } else {
            interimText += ` ${chunk}`;
          }
          const score = item?.confidence;
          if (typeof score === "number" && Number.isFinite(score)) {
            confidence += score;
            confidenceCount += 1;
          }
        }
        const rawText = `${transcriptBufferRef.current} ${interimText}`.trim();
        setCandidateAnswer(rawText);
        setAnswerMetadata({
          source: "speech",
          transcript: transcriptBufferRef.current,
          confidence: confidenceCount ? confidence / confidenceCount : answerMetadata?.confidence,
          locale: recognition.lang,
          finalized: false,
          raw_text: rawText
        });
      };
      recognition.onerror = () => {
        setError("语音识别中断，请重试或手动输入。");
        stopListening();
      };
      recognition.onend = () => {
        setIsListening(false);
        setAnswerMetadata((previous) => previous ? { ...previous, finalized: true } : null);
      };
      recognition.onnomatch = () => {
        setError("未识别到有效语音，请重试。");
      };
      recognition.start();
    } catch (err) {
      stopListening();
      setError(err instanceof Error ? err.message : "语音识别启动失败，请手动输入。");
    }
  }

  function handleReplayQuestion() {
    const currentQuestion = session?.current_question?.question;
    if (!currentQuestion) {
      setError("当前没有可朗读的问题。");
      return;
    }
    if (!window.speechSynthesis) {
      setError("当前浏览器不支持语音播报。");
      return;
    }
    setIsSpeaking(false);
    const utterance = new SpeechSynthesisUtterance(currentQuestion);
    utterance.lang = "zh-CN";
    utterance.rate = 1;
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    window.speechSynthesis.speak(utterance);
  }

  function buildAnswerMetadata(): InterviewTurnInputMetadata | null {
    if (answerSource === "speech") {
      return {
        source: "speech",
        transcript: (answerMetadata?.transcript || candidateAnswer).trim(),
        confidence: answerMetadata?.confidence,
        locale: answerMetadata?.locale || "zh-CN",
        finalized: true,
        raw_text: candidateAnswer
      };
    }
    return {
      source: "text",
      transcript: candidateAnswer,
      finalized: true
    };
  }

  function handleAnswerChange(value: string) {
    setCandidateAnswer(value);
    setAnswerSource("text");
    setAnswerMetadata({
      source: "text",
      transcript: value,
      finalized: true
    });
  }

  function handleClearAnswer() {
    setCandidateAnswer("");
    setAnswerSource("text");
    setAnswerMetadata(null);
    transcriptBufferRef.current = "";
    if (isListening) {
      stopListening();
    }
  }

  async function handleStart() {
    setLoading(true);
    setError(null);
    try {
      const nextSession = await startInterview({
        runId,
        candidateId: candidate.candidate_id,
        mode: `${config.mode}:${config.skillRoute?.skill_name ?? ""}:${config.difficulty}:${config.interviewerStyle}`,
        skillId: config.skillRoute?.skill_id
      });
      if (isVoiceMode) {
        onStartVoiceSession?.(nextSession);
      } else {
        setSession(nextSession);
      }
      onSessionChange?.(nextSession);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 面试会话创建失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmitTurn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;
    if (!candidateAnswer.trim()) {
      setError("候选人回答不能为空。");
      return;
    }
    setSubmitting(true);
    setError(null);
    if (isListening) {
      stopListening();
    }
    try {
      const nextSession = await submitInterviewTurn({
        sessionId: session.session_id,
        candidateAnswer,
        answerMetadata: buildAnswerMetadata() ?? undefined
      });
      setSession(nextSession);
      onSessionChange?.(nextSession);
      setCandidateAnswer("");
      setAnswerSource("text");
      setAnswerMetadata(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "回答提交失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleFinalize() {
    if (!session) return;
    setFinalizing(true);
    setError(null);
    try {
      const nextSession = await finalizeInterview(session.session_id);
      setSession(nextSession);
      onSessionChange?.(nextSession);
    } catch (err) {
      setError(err instanceof Error ? err.message : "最终报告生成失败，请稍后重试。");
    } finally {
      setFinalizing(false);
    }
  }

  return (
    <div className="interview-panel">
      <div className="interview-console">
        <header className="interview-console-header">
          <div>
            <span className="fact-type">Structured interview</span>
            <strong>{session ? sessionStatusLabel(session.status) : "准备开始"}</strong>
          </div>
          <div className="score-pills">
            <span>{session ? `${session.turns.length} 轮` : "0 轮"}</span>
            <span>{config.skillRoute?.route_result ?? "JD 自动路由"}</span>
            <span>{difficultyLabel(config.difficulty)}</span>
            <span>{interviewerStyleLabel(config.interviewerStyle)}</span>
            <span>{candidate.profile.name}</span>
          </div>
        </header>

        {!session ? (
          <div className="interview-start">
            <p className="empty-facts">准备开始结构化面试。</p>
            <button className="secondary-button" type="button" onClick={handleStart} disabled={loading}>
              {loading ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <ArrowUpRight size={16} aria-hidden="true" />}
              <span>
                {loading
                  ? "创建中"
                  : isVoiceMode
                    ? "开始语音面试"
                    : "开始 AI 面试"}
              </span>
            </button>
          </div>
        ) : (
          <>
            {session.current_question ? (
              <div className="selected-question interview-current">
                <span>{questionSourceLabel(session.current_question.source)}</span>
                <strong>{session.current_question.question}</strong>
                {session.current_question.scoring_criteria ? <p>{session.current_question.scoring_criteria}</p> : null}
              </div>
            ) : session.final_report ? null : (
              <p className="empty-facts">当前轮次已完成，可以生成最终报告。</p>
            )}

            {session.current_question ? (
              <form className="followup-form interview-answer-form" onSubmit={handleSubmitTurn}>
                <div className="followup-control">
                  <label htmlFor={answerId}>候选人回答</label>
                  <textarea
                    aria-label="候选人回答"
                    id={answerId}
                    value={candidateAnswer}
                    onChange={(event) => handleAnswerChange(event.target.value)}
                    placeholder="输入候选人当前回答"
                    rows={5}
                  />
                </div>
                {isVoiceMode ? (
                  <>
                    <div className="voice-control-row">
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={handleStartListening}
                        disabled={submitting || finalizing || (!speechSupported && !isListening)}
                      >
                        {isListening ? <MicOff size={16} aria-hidden="true" /> : <Mic size={16} aria-hidden="true" />}
                        <span>{isListening ? "停止识别" : "开始识别"}</span>
                      </button>
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={handleReplayQuestion}
                        disabled={submitting || finalizing}
                      >
                        {isSpeaking ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <Volume2 size={16} aria-hidden="true" />}
                        <span>重听问题</span>
                      </button>
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={handleClearAnswer}
                        disabled={submitting || finalizing}
                      >
                        <RefreshCw size={16} aria-hidden="true" />
                        <span>清空回答</span>
                      </button>
                    </div>
                    <div className="voice-hint">
                      <span>{isListening ? "语音识别中，请直接说话..." : "点击“开始识别”后可进行语音输入。"} </span>
                      <strong>答案来源：{answerSource === "speech" ? "语音" : "文本"}</strong>
                      {answerMetadata?.confidence ? <small>{`识别置信度 ${(answerMetadata.confidence * 100).toFixed(0)}%`}</small> : null}
                    </div>
                  </>
                ) : null}
                <button className="secondary-button" type="submit" disabled={submitting}>
                  {submitting ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <ArrowUpRight size={16} aria-hidden="true" />}
                  <span>{submitting ? "发送中" : "发送回答"}</span>
                </button>
              </form>
            ) : null}

            {session.turns.length && !session.final_report ? (
              <button className="secondary-button" type="button" onClick={handleFinalize} disabled={finalizing}>
                {finalizing ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <FileText size={16} aria-hidden="true" />}
                <span>{finalizing ? "生成中" : "生成最终报告"}</span>
              </button>
            ) : null}
          </>
        )}

        {error ? (
          <div className="error-box" role="alert">
            <AlertCircle size={18} aria-hidden="true" />
            <span>{error}</span>
          </div>
        ) : null}
      </div>

      {session?.turns.length ? <InterviewHistory session={session} /> : null}
      {session?.final_report ? <InterviewFinalReportCard report={session.final_report} /> : null}
    </div>
  );
}

function InterviewHistory({ session }: { session: InterviewSession }) {
  return (
    <section className="interview-history followup-result">
      <h4>面试记录</h4>
      <div className="interview-turn-list">
        {session.turns.map((turn) => (
          <article className="interview-turn" key={turn.turn_index}>
            <span className="fact-type">第 {turn.turn_index} 轮</span>
            <strong>{turn.question.question}</strong>
            <p className="interview-answer">{turn.answer}</p>
            {turn.answer_source ? <small>答案来源：{turn.answer_source === "speech" ? "语音" : "文本"}</small> : null}
            <div className="score-pills">
              <span>清晰度 {turn.diagnosis.clarity_score}</span>
              <span>深度 {turn.diagnosis.depth_score}</span>
              <span>{consistencyLabel(turn.diagnosis.evidence_consistency)}</span>
            </div>
            <p>{turn.diagnosis.answer_summary}</p>
            {turn.diagnosis.issues.length ? <List items={turn.diagnosis.issues} /> : null}
            {turn.diagnosis.followup_needed ? (
              <div className="followup-question-card">
                <span>动态追问</span>
                <strong>{turn.diagnosis.followup_question}</strong>
                <p>{turn.diagnosis.reason}</p>
                <small>{turn.diagnosis.expected_signal}</small>
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function difficultyLabel(value: InterviewDifficulty) {
  return DIFFICULTY_OPTIONS.find((item) => item.id === value)?.label ?? "中级";
}

function interviewerStyleLabel(value: InterviewerStyle) {
  return INTERVIEWER_STYLES.find((item) => item.id === value)?.label ?? "亲切的 HR";
}
