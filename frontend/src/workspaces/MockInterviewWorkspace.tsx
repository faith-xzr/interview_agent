import {
  AlertCircle,
  ArrowUpRight,
  Bot,
  Cpu,
  FileText,
  Gauge,
  HeartHandshake,
  Loader2,
  MessageCircle,
  ShieldAlert,
  Sparkles,
  type LucideIcon
} from "lucide-react";
import { FormEvent, useEffect, useState, type ReactNode } from "react";

import { finalizeInterview, startInterview, submitInterviewTurn } from "../api";
import { InterviewFinalReportCard } from "../components/InterviewFinalReportCard";
import { List } from "../components/List";
import { PageTitle } from "../components/PageTitle";
import { consistencyLabel, questionSourceLabel, sessionStatusLabel } from "../interviewDisplay";
import { hasQuestionMaterials } from "../matchReportDisplay";
import type { CandidateReport, InterviewSession, RunReport } from "../types";

type InterviewMode = "text" | "voice";
type InterviewDifficulty = "campus" | "mid" | "senior";
type InterviewerStyle = "friendly_hr" | "strict_manager";

const INTERVIEW_DIRECTIONS = [
  "AI Agent 开发",
  "算法与数据结构",
  "前端工程",
  "Java 后端开发",
  "Python 后端开发",
  "系统设计",
  "自定义 JD"
];

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
  const [direction, setDirection] = useState("Java 后端开发");
  const [difficulty, setDifficulty] = useState<InterviewDifficulty>("mid");
  const [interviewerStyle, setInterviewerStyle] = useState<InterviewerStyle>("friendly_hr");
  const canStartInterview = selectedCandidate
    ? hasQuestionMaterials(selectedCandidate.match_report)
    : false;

  return (
    <div className="workspace-stack">
      <PageTitle icon={Sparkles} title="模拟面试" subtitle="选择面试模式、方向、难度和面试官风格" />
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

        <ConfigSection title="面试方向">
          <div className="config-grid directions">
            {INTERVIEW_DIRECTIONS.map((item) => (
              <OptionCard
                active={direction === item}
                compact
                icon={directionIcon(item)}
                key={item}
                label={item}
                onClick={() => setDirection(item)}
              />
            ))}
          </div>
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
            config={{ mode, direction, difficulty, interviewerStyle }}
            onSessionChange={onSessionChange}
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

function directionIcon(direction: string) {
  if (direction.includes("算法")) return Gauge;
  if (direction.includes("系统")) return Cpu;
  if (direction.includes("自定义")) return Sparkles;
  return Bot;
}

function InterviewRoom({
  candidate,
  config,
  onSessionChange,
  runId
}: {
  candidate: CandidateReport;
  config: {
    mode: InterviewMode;
    direction: string;
    difficulty: InterviewDifficulty;
    interviewerStyle: InterviewerStyle;
  };
  onSessionChange?: (session: InterviewSession) => void;
  runId: string;
}) {
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [candidateAnswer, setCandidateAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const answerId = `interview-answer-${candidate.candidate_id}`;

  useEffect(() => {
    setSession(null);
    setCandidateAnswer("");
    setError(null);
  }, [candidate.candidate_id, runId]);

  async function handleStart() {
    setLoading(true);
    setError(null);
    try {
      const nextSession = await startInterview({
        runId,
        candidateId: candidate.candidate_id,
        mode: `${config.mode}:${config.direction}:${config.difficulty}:${config.interviewerStyle}`
      });
      setSession(nextSession);
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
    try {
      const nextSession = await submitInterviewTurn({
        sessionId: session.session_id,
        candidateAnswer
      });
      setSession(nextSession);
      onSessionChange?.(nextSession);
      setCandidateAnswer("");
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
            <span>{config.direction}</span>
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
              <span>{loading ? "创建中" : "开始 AI 面试"}</span>
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
                    onChange={(event) => setCandidateAnswer(event.target.value)}
                    placeholder="输入候选人当前回答"
                    rows={5}
                  />
                </div>
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
