import {
  AlertCircle,
  ArrowUpRight,
  Bot,
  Briefcase,
  CheckCircle2,
  ChevronRight,
  Cpu,
  FileStack,
  FileText,
  Gauge,
  HeartHandshake,
  KeyRound,
  Loader2,
  MessageCircle,
  Paperclip,
  Search,
  Settings,
  ShieldAlert,
  Sparkles,
  Trash2,
  Upload,
  Users,
  type LucideIcon
} from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

import {
  createRun,
  deleteInterviewSession,
  finalizeInterview,
  getModelProviders,
  listInterviewSessions,
  listRuns,
  startInterview,
  submitInterviewTurn,
  updateDefaultModelProvider,
  updateModelProviderApiKey
} from "./api";
import type {
  CandidateReport,
  CandidateProfile,
  DimensionExplanation,
  ExtractedFact,
  InterviewFinalReport,
  InterviewSession,
  MatchReport,
  ModelProvider,
  RequirementMatch,
  RunReport
} from "./types";
import "./styles.css";

type WorkspaceView = "resumes" | "interview" | "records" | "settings";
type ResultView = "overview" | "extraction" | "matching" | "questions";
type InputMode = "file" | "text";
type InterviewMode = "text" | "voice";
type InterviewDifficulty = "campus" | "mid" | "senior";
type InterviewerStyle = "friendly_hr" | "strict_manager";

const WORKSPACE_GROUPS: Array<{
  title: string;
  items: Array<{
    id: WorkspaceView;
    label: string;
    description: string;
    icon: LucideIcon;
  }>;
}> = [
  {
    title: "面试准备",
    items: [
      { id: "resumes", label: "简历管理", description: "按 JD 分组分析", icon: FileStack },
      { id: "interview", label: "模拟面试", description: "配置面试练习", icon: Sparkles },
      { id: "records", label: "面试记录", description: "管理面试历史", icon: Users }
    ]
  },
  {
    title: "系统",
    items: [
      { id: "settings", label: "设置", description: "管理模型服务", icon: Settings }
    ]
  }
];

const DETAIL_VIEWS: Array<{ id: ResultView; label: string }> = [
  { id: "overview", label: "总览" },
  { id: "extraction", label: "结构化提取" },
  { id: "matching", label: "智能匹配打分" },
  { id: "questions", label: "试题生成" }
];
const QUESTION_MATERIAL_MIN_SCORE = 40;
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

const FALLBACK_MODEL_PROVIDERS: ModelProvider[] = [
  {
    id: "dashscope",
    name: "通义千问（DashScope）",
    model: "qwen3.5-flash",
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key_configured: false,
    is_default: false
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    model: "deepseek-v4-flash",
    base_url: "https://api.deepseek.com/v1",
    api_key_configured: false,
    is_default: false
  },
  {
    id: "kimi",
    name: "Kimi",
    model: "kimi-latest",
    base_url: "https://api.moonshot.cn/v1",
    api_key_configured: false,
    is_default: false
  },
  {
    id: "glm",
    name: "智谱 GLM",
    model: "glm-5",
    base_url: "https://open.bigmodel.cn/api/coding/paas/v4",
    api_key_configured: false,
    is_default: false
  },
  {
    id: "openai-compatible",
    name: "OpenAI Compatible",
    model: "gpt-4o-mini",
    base_url: "https://api.openai.com/v1",
    api_key_configured: false,
    is_default: true
  }
];

export default function App() {
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceView>("resumes");
  const [jdText, setJdText] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [resumeFiles, setResumeFiles] = useState<File[]>([]);
  const [jdInputMode, setJdInputMode] = useState<InputMode>("file");
  const [resumeInputMode, setResumeInputMode] = useState<InputMode>("file");
  const [runs, setRuns] = useState<RunReport[]>([]);
  const [report, setReport] = useState<RunReport | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<ResultView>("overview");
  const [interviewSessions, setInterviewSessions] = useState<InterviewSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recordsError, setRecordsError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadWorkspaceState() {
      try {
        const [savedRuns, savedSessions] = await Promise.all([listRuns(), listInterviewSessions()]);
        if (cancelled) return;
        setRuns(savedRuns);
        setInterviewSessions(savedSessions);
        if (savedRuns.length) {
          setReport(savedRuns[0]);
          setSelectedRunId((current) => current ?? savedRuns[0].run_id);
          setSelectedId((current) => current ?? savedRuns[0].candidates[0]?.candidate_id ?? null);
        }
      } catch {
        if (!cancelled) {
          setRecordsError("历史记录加载失败，但仍可继续新建分析。");
        }
      }
    }
    loadWorkspaceState();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedRun = useMemo(() => {
    if (!runs.length) return report;
    return runs.find((item) => item.run_id === selectedRunId) ?? runs[0] ?? report;
  }, [report, runs, selectedRunId]);

  const selectedCandidate = useMemo(() => {
    if (!selectedRun) return null;
    return selectedRun.candidates.find((candidate) => candidate.candidate_id === selectedId) ?? selectedRun.candidates[0] ?? null;
  }, [selectedRun, selectedId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const nextReport = await createRun({
        jdText: jdInputMode === "text" ? jdText : "",
        resumeText: resumeInputMode === "text" ? resumeText : "",
        jdFile: jdInputMode === "file" ? jdFile : null,
        resumeFiles: resumeInputMode === "file" ? resumeFiles : []
      });
      setReport(nextReport);
      setRuns((current) => [nextReport, ...current.filter((item) => item.run_id !== nextReport.run_id)]);
      setSelectedRunId(nextReport.run_id);
      setSelectedId(nextReport.candidates[0]?.candidate_id ?? null);
      setActiveWorkspace("resumes");
      setActiveView("overview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败，请检查输入后重试。");
    } finally {
      setLoading(false);
    }
  }

  function handleResumeFiles(event: ChangeEvent<HTMLInputElement>) {
    setResumeFiles(Array.from(event.target.files ?? []));
  }

  function handleSelectRun(runId: string) {
    const nextRun = runs.find((item) => item.run_id === runId);
    setSelectedRunId(runId);
    setReport(nextRun ?? report);
    setSelectedId(nextRun?.candidates[0]?.candidate_id ?? null);
    setActiveView("overview");
  }

  function handleSessionChange(session: InterviewSession) {
    setRecordsError(null);
    setInterviewSessions((current) => [session, ...current.filter((item) => item.session_id !== session.session_id)]);
  }

  async function handleDeleteSession(sessionId: string) {
    setRecordsError(null);
    try {
      await deleteInterviewSession(sessionId);
      setInterviewSessions((current) => current.filter((item) => item.session_id !== sessionId));
    } catch (err) {
      setRecordsError(err instanceof Error ? err.message : "面试记录删除失败。");
    }
  }

  return (
    <div className="app-shell">
      <Sidebar activeWorkspace={activeWorkspace} onChange={setActiveWorkspace} />
      <main className="workspace-main">
        {activeWorkspace === "resumes" ? (
          <ResumeManagementWorkspace
            activeView={activeView}
            error={error}
            jdFile={jdFile}
            jdInputMode={jdInputMode}
            jdText={jdText}
            loading={loading}
            report={selectedRun}
            resumeFiles={resumeFiles}
            resumeInputMode={resumeInputMode}
            resumeText={resumeText}
            runs={runs}
            selectedCandidate={selectedCandidate}
            selectedRunId={selectedRun?.run_id ?? null}
            onActiveViewChange={setActiveView}
            onJdFileChange={setJdFile}
            onJdInputModeChange={setJdInputMode}
            onJdTextChange={setJdText}
            onResumeFilesChange={handleResumeFiles}
            onResumeInputModeChange={setResumeInputMode}
            onResumeTextChange={setResumeText}
            onSelectCandidate={setSelectedId}
            onSelectRun={handleSelectRun}
            onSubmit={handleSubmit}
          />
        ) : null}

        {activeWorkspace === "interview" ? (
          <MockInterviewWorkspace
            report={selectedRun}
            selectedCandidate={selectedCandidate}
            onSelectCandidate={setSelectedId}
            onSessionChange={handleSessionChange}
          />
        ) : null}

        {activeWorkspace === "records" ? (
          <InterviewRecordsWorkspace
            error={recordsError}
            sessions={interviewSessions}
            runs={runs}
            onDeleteSession={handleDeleteSession}
          />
        ) : null}

        {activeWorkspace === "settings" ? <SettingsWorkspace /> : null}
      </main>
    </div>
  );
}

function Sidebar({
  activeWorkspace,
  onChange
}: {
  activeWorkspace: WorkspaceView;
  onChange: (view: WorkspaceView) => void;
}) {
  return (
    <aside className="sidebar-shell" aria-label="主功能导航">
      <div className="sidebar-brand">
        <div className="brand-mark">
          <Bot size={24} aria-hidden="true" />
        </div>
        <div>
          <strong>AI Native 招聘助手</strong>
        </div>
      </div>

      <nav className="sidebar-nav">
        {WORKSPACE_GROUPS.map((group) => (
          <section className="sidebar-group" key={group.title}>
            <h2>{group.title}</h2>
            <div className="sidebar-items">
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = activeWorkspace === item.id;
                return (
                  <button
                    aria-pressed={active}
                    className={active ? "sidebar-item active" : "sidebar-item"}
                    key={item.id}
                    onClick={() => onChange(item.id)}
                    type="button"
                  >
                    <span className="sidebar-icon">
                      <Icon size={21} aria-hidden="true" />
                    </span>
                    <span className="sidebar-copy">
                      <strong>{item.label}</strong>
                      <small>{item.description}</small>
                    </span>
                    {active ? <ChevronRight size={17} aria-hidden="true" /> : null}
                  </button>
                );
              })}
            </div>
          </section>
        ))}
      </nav>

      <div className="sidebar-version">
        <strong>ai-native-recruiting-assistant</strong>
      </div>
    </aside>
  );
}

function PageTitle({
  icon: Icon,
  title,
  subtitle,
  action
}: {
  icon: LucideIcon;
  title: string;
  subtitle: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="workspace-title">
      <div className="workspace-title-main">
        <Icon size={32} aria-hidden="true" />
        <div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
      </div>
      {action ? <div className="workspace-title-action">{action}</div> : null}
    </header>
  );
}

function ResumeManagementWorkspace({
  activeView,
  error,
  jdFile,
  jdInputMode,
  jdText,
  loading,
  report,
  resumeFiles,
  resumeInputMode,
  resumeText,
  runs,
  selectedCandidate,
  selectedRunId,
  onActiveViewChange,
  onJdFileChange,
  onJdInputModeChange,
  onJdTextChange,
  onResumeFilesChange,
  onResumeInputModeChange,
  onResumeTextChange,
  onSelectCandidate,
  onSelectRun,
  onSubmit
}: {
  activeView: ResultView;
  error: string | null;
  jdFile: File | null;
  jdInputMode: InputMode;
  jdText: string;
  loading: boolean;
  report: RunReport | null;
  resumeFiles: File[];
  resumeInputMode: InputMode;
  resumeText: string;
  runs: RunReport[];
  selectedCandidate: CandidateReport | null;
  selectedRunId: string | null;
  onActiveViewChange: (view: ResultView) => void;
  onJdFileChange: (file: File | null) => void;
  onJdInputModeChange: (mode: InputMode) => void;
  onJdTextChange: (value: string) => void;
  onResumeFilesChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onResumeInputModeChange: (mode: InputMode) => void;
  onResumeTextChange: (value: string) => void;
  onSelectCandidate: (id: string) => void;
  onSelectRun: (id: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="workspace-stack">
      <PageTitle
        icon={FileStack}
        title="简历管理"
        subtitle="按岗位 JD 分组管理简历与分析结果"
        action={
          <button className="top-action" type="button" onClick={() => document.getElementById("resume-files")?.click()}>
            <Upload size={18} aria-hidden="true" />
            <span>上传简历</span>
          </button>
        }
      />

      <section className="card form-card workspace-card">
        <form className="input-form" onSubmit={onSubmit}>
          <div className="form-grid">
            <FieldGroup
              label="职位描述（JD）"
              hint="每个 JD 会形成一个独立岗位分组"
              mode={jdInputMode}
              onModeChange={onJdInputModeChange}
              modeId="jd-mode"
            >
              {jdInputMode === "file" ? (
                <FilePicker
                  id="jd-file"
                  accept=".pdf,.docx,.txt"
                  onChange={(event) => onJdFileChange(event.target.files?.[0] ?? null)}
                  label="选择 JD 文件"
                  summary={jdFile ? jdFile.name : "未选择文件（支持 .pdf / .docx / .txt）"}
                />
              ) : (
                <textarea
                  aria-label="JD 文本兜底"
                  id="jd-text"
                  value={jdText}
                  onChange={(event) => onJdTextChange(event.target.value)}
                  placeholder="粘贴职位描述、职责、技能要求、年限要求……"
                  rows={6}
                />
              )}
            </FieldGroup>

            <FieldGroup
              label="候选人简历"
              hint="上传后归入当前 JD 岗位分组"
              mode={resumeInputMode}
              onModeChange={onResumeInputModeChange}
              modeId="resume-mode"
            >
              {resumeInputMode === "file" ? (
                <FilePicker
                  id="resume-files"
                  accept=".pdf,.docx,.txt"
                  multiple
                  onChange={onResumeFilesChange}
                  label="选择简历文件"
                  summary={resumeFiles.length ? `已选择 ${resumeFiles.length} 份文件` : "未选择文件（支持批量上传）"}
                />
              ) : (
                <textarea
                  aria-label="简历文本兜底"
                  id="resume-text"
                  value={resumeText}
                  onChange={(event) => onResumeTextChange(event.target.value)}
                  placeholder="粘贴一份简历文本；多份简历建议改用文件上传。"
                  rows={6}
                />
              )}
            </FieldGroup>
          </div>

          {error ? (
            <div className="error-box" role="alert">
              <AlertCircle size={18} aria-hidden="true" />
              <span>{error}</span>
            </div>
          ) : null}

          <div className="form-footer">
            <p className="form-footer-hint">结构化解析 · 智能匹配 · 自动出题</p>
            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <ArrowUpRight size={16} aria-hidden="true" />}
              <span>{loading ? "分析中" : "开始智能筛选"}</span>
            </button>
          </div>
        </form>
      </section>

      <section className="job-groups">
        <div className="section-toolbar">
          <div className="search-box">
            <Search size={20} aria-hidden="true" />
            <input aria-label="搜索简历" placeholder="搜索简历..." />
          </div>
          <span>{runs.length} 个岗位分组</span>
        </div>
        {runs.length ? (
          <div className="job-group-list">
            {runs.map((item) => (
              <article className={item.run_id === selectedRunId ? "job-group active" : "job-group"} key={item.run_id}>
                <button type="button" onClick={() => onSelectRun(item.run_id)}>
                  <Briefcase size={20} aria-hidden="true" />
                  <span>
                    <strong>{item.jd_profile.job_title}</strong>
                    <small>{new Date(item.created_at).toLocaleDateString("zh-CN")} · {item.candidates.length} 份简历</small>
                  </span>
                  <ChevronRight size={18} aria-hidden="true" />
                </button>
                <div className="job-candidate-table">
                  {item.candidates.map((candidate) => (
                    <button
                      key={`${item.run_id}-${candidate.candidate_id}`}
                      type="button"
                      onClick={() => {
                        onSelectRun(item.run_id);
                        onSelectCandidate(candidate.candidate_id);
                      }}
                    >
                      <span className="document-icon"><FileText size={20} aria-hidden="true" /></span>
                      <span className="candidate-cell">
                        <strong>{candidate.profile.name}</strong>
                        <small>{candidate.source_name}</small>
                      </span>
                      <span className="status-ok"><CheckCircle2 size={18} aria-hidden="true" /> 分析完成</span>
                      <span className="score-cell">{candidate.match_report.total_score}</span>
                    </button>
                  ))}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="card empty-state compact-empty">
            <h2>等待创建岗位分组</h2>
            <p>上传 JD 与简历后，这里会按岗位展示候选人、分析状态和 AI 评分。</p>
          </div>
        )}
      </section>

      {report && selectedCandidate ? (
        <section className="card result-card">
          <RunSummary report={report} />
          <ResultNavigation activeView={activeView} onChange={onActiveViewChange} />
          {activeView === "overview" ? (
            <CandidateOverview
              candidates={report.candidates}
              selectedId={selectedCandidate.candidate_id}
              onSelect={onSelectCandidate}
            />
          ) : (
            <div className="result-grid">
              <CandidateRanking
                candidates={report.candidates}
                selectedId={selectedCandidate.candidate_id}
                onSelect={onSelectCandidate}
              />
              <CandidateDetail
                candidate={selectedCandidate}
                jdExtractionFacts={report.jd_extraction_facts}
                runId={report.run_id}
                view={activeView}
              />
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}

function MockInterviewWorkspace({
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
    ? !shouldSkipQuestionMaterials(selectedCandidate.match_report)
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
          <p>匹配分低于 40，建议先完成岗位匹配审核后再开始 AI 面试。</p>
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

function InterviewRecordsWorkspace({
  error,
  sessions,
  runs,
  onDeleteSession
}: {
  error: string | null;
  sessions: InterviewSession[];
  runs: RunReport[];
  onDeleteSession: (id: string) => void;
}) {
  return (
    <div className="workspace-stack">
      <PageTitle icon={Users} title="面试记录" subtitle="查看和管理已生成的面试评估报告" />
      {error ? (
        <div className="error-banner">
          <AlertCircle size={18} aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}
      {sessions.length ? (
        <div className="record-list">
          {sessions.map((session) => {
            const run = runs.find((item) => item.run_id === session.run_id);
            const candidate = run?.candidates.find((item) => item.candidate_id === session.candidate_id);
            return (
              <article className="record-card card" key={session.session_id}>
                <div className="record-main">
                  <span className="document-icon"><Bot size={20} aria-hidden="true" /></span>
                  <div>
                    <h2>{candidate?.profile.name ?? "未知候选人"}</h2>
                    <p>{run?.jd_profile.job_title ?? "未知岗位"} · {session.turns.length} 轮问答</p>
                  </div>
                </div>
                <div className="record-score">
                  <span>{session.final_report ? `总分 ${session.final_report.overall_score}` : sessionStatusLabel(session.status)}</span>
                  <strong>{session.final_report?.recommendation ?? "待生成最终报告"}</strong>
                </div>
                <button className="icon-button" type="button" onClick={() => onDeleteSession(session.session_id)} aria-label="删除面试记录">
                  <Trash2 size={18} aria-hidden="true" />
                </button>
                {session.final_report ? <InterviewFinalReportCard report={session.final_report} /> : null}
              </article>
            );
          })}
        </div>
      ) : (
        <div className="card empty-state compact-empty">
          <h2>暂无面试记录</h2>
          <p>完成一次模拟面试并生成最终报告后，记录会显示在这里。</p>
        </div>
      )}
    </div>
  );
}

function SettingsWorkspace() {
  const [providers, setProviders] = useState<ModelProvider[]>(FALLBACK_MODEL_PROVIDERS);
  const [defaultProvider, setDefaultProvider] = useState("openai-compatible");
  const [loading, setLoading] = useState(true);
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [editingApiKeyProvider, setEditingApiKeyProvider] = useState<string | null>(null);
  const [apiKeyDraft, setApiKeyDraft] = useState("");
  const [savingApiKeyProvider, setSavingApiKeyProvider] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadProviders() {
      setLoading(true);
      setError(null);
      try {
        const payload = await getModelProviders();
        if (cancelled) return;
        setProviders(payload.providers);
        setDefaultProvider(payload.default_provider_id);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "模型服务配置加载失败。");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    loadProviders();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSetDefault(providerId: string) {
    if (providerId === defaultProvider || savingProvider) return;
    setSavingProvider(providerId);
    setError(null);
    try {
      const payload = await updateDefaultModelProvider(providerId);
      setProviders(payload.providers);
      setDefaultProvider(payload.default_provider_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "默认模型服务切换失败。");
    } finally {
      setSavingProvider(null);
    }
  }

  function openApiKeyEditor(providerId: string) {
    setEditingApiKeyProvider(providerId);
    setApiKeyDraft("");
    setError(null);
  }

  function closeApiKeyEditor() {
    setEditingApiKeyProvider(null);
    setApiKeyDraft("");
  }

  async function handleSaveApiKey(providerId: string) {
    const apiKey = apiKeyDraft.trim();
    if (!apiKey || savingApiKeyProvider) {
      if (!apiKey) setError("请先粘贴 API Key。");
      return;
    }
    setSavingApiKeyProvider(providerId);
    setError(null);
    try {
      const payload = await updateModelProviderApiKey(providerId, apiKey);
      setProviders(payload.providers);
      setDefaultProvider(payload.default_provider_id);
      closeApiKeyEditor();
    } catch (err) {
      setError(err instanceof Error ? err.message : "API Key 保存失败。");
    } finally {
      setSavingApiKeyProvider(null);
    }
  }

  return (
    <div className="workspace-stack">
      <PageTitle icon={Settings} title="设置" subtitle="管理模型服务和默认推理配置" />
      {error ? (
        <div className="error-banner">
          <AlertCircle size={18} aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}
      <section className="settings-grid">
        {providers.map((provider) => {
          const isEditingApiKey = editingApiKeyProvider === provider.id;
          const isSavingApiKey = savingApiKeyProvider === provider.id;
          const apiKeyInputId = `provider-api-key-${provider.id}`;
          return (
            <article className={defaultProvider === provider.id ? "provider-card card active" : "provider-card card"} key={provider.id}>
              <div className="provider-head">
                <span className="document-icon"><Cpu size={20} aria-hidden="true" /></span>
                <div>
                  <h2>{provider.name}</h2>
                  <p>{defaultProvider === provider.id ? "默认聊天服务" : "备用模型服务"}</p>
                </div>
              </div>
              <label>
                模型名称
                <input value={provider.model} readOnly />
              </label>
              <label>
                Base URL
                <input value={provider.base_url} readOnly />
              </label>
              <div className="provider-field">
                <span className="provider-field-label">API Key</span>
                <span className="secret-input">
                  <KeyRound size={16} aria-hidden="true" />
                  {providerApiKeyLabel(provider)}
                </span>
              </div>
              {isEditingApiKey ? (
                <div className="provider-key-editor">
                  <label htmlFor={apiKeyInputId}>
                    新的 API Key
                    <input
                      aria-label={`${provider.name} API Key`}
                      autoComplete="off"
                      id={apiKeyInputId}
                      onChange={(event) => setApiKeyDraft(event.target.value)}
                      placeholder="粘贴 API Key"
                      type="password"
                      value={apiKeyDraft}
                    />
                  </label>
                  <div className="provider-key-actions">
                    <button
                      className="secondary-button"
                      type="button"
                      disabled={isSavingApiKey}
                      onClick={() => handleSaveApiKey(provider.id)}
                    >
                      <span>{isSavingApiKey ? "保存中..." : "保存 Key"}</span>
                    </button>
                    <button
                      className="secondary-button subtle"
                      type="button"
                      disabled={isSavingApiKey}
                      onClick={closeApiKeyEditor}
                    >
                      <span>取消</span>
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  className="secondary-button subtle"
                  type="button"
                  disabled={loading || savingProvider !== null || savingApiKeyProvider !== null}
                  onClick={() => openApiKeyEditor(provider.id)}
                >
                  <KeyRound size={16} aria-hidden="true" />
                  <span>粘贴 API Key</span>
                </button>
              )}
              <button
                className="secondary-button"
                type="button"
                disabled={loading || savingProvider !== null || savingApiKeyProvider !== null || defaultProvider === provider.id}
                onClick={() => handleSetDefault(provider.id)}
              >
                <span>
                  {savingProvider === provider.id
                    ? "切换中..."
                    : defaultProvider === provider.id
                      ? "当前默认"
                      : "设为默认"}
                </span>
              </button>
            </article>
          );
        })}
      </section>
    </div>
  );
}

function providerApiKeyLabel(provider: ModelProvider) {
  if (provider.api_key_source === "saved") return "已保存到本地配置";
  if (provider.api_key_source === "env") return "已通过环境变量配置";
  if (provider.api_key_configured) return "已配置";
  return "未配置，可粘贴";
}

function ConfigSection({ title, children }: { title: string; children: React.ReactNode }) {
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

function FieldGroup({
  label,
  hint,
  mode,
  onModeChange,
  modeId,
  children
}: {
  label: string;
  hint: string;
  mode: InputMode;
  onModeChange: (mode: InputMode) => void;
  modeId: string;
  children: React.ReactNode;
}) {
  return (
    <div className="field-group">
      <div className="field-head">
        <div>
          <label className="field-label" htmlFor={modeId}>
            {label}
          </label>
          <p className="field-hint">{hint}</p>
        </div>
        <div className="mode-select">
          <select
            id={modeId}
            value={mode}
            onChange={(event) => onModeChange(event.target.value as InputMode)}
          >
            <option value="file">文件上传</option>
            <option value="text">文本输入</option>
          </select>
        </div>
      </div>
      <div className="field-body">{children}</div>
    </div>
  );
}

function FilePicker({
  id,
  accept,
  multiple,
  onChange,
  label,
  summary
}: {
  id: string;
  accept: string;
  multiple?: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  label: string;
  summary: string;
}) {
  return (
    <div className="file-picker">
      <label className="file-picker-label" htmlFor={id}>
        <Paperclip size={15} aria-hidden="true" />
        <span>{label}</span>
      </label>
      <input
        accept={accept}
        className="file-picker-input"
        id={id}
        multiple={multiple}
        onChange={onChange}
        type="file"
      />
      <span className="file-picker-summary">
        <FileText size={14} aria-hidden="true" />
        <span>{summary}</span>
      </span>
    </div>
  );
}

function ResultNavigation({
  activeView,
  onChange
}: {
  activeView: ResultView;
  onChange: (view: ResultView) => void;
}) {
  return (
    <nav className="result-tabs" aria-label="结果视图">
      {DETAIL_VIEWS.map((view) => (
        <button
          aria-pressed={activeView === view.id}
          className={activeView === view.id ? "result-tab active" : "result-tab"}
          key={view.id}
          onClick={() => onChange(view.id)}
          type="button"
        >
          {view.label}
        </button>
      ))}
    </nav>
  );
}

function RunSummary({ report }: { report: RunReport }) {
  return (
    <div className="summary-band">
      <div>
        <span className="muted">岗位</span>
        <strong>{report.jd_profile.job_title}</strong>
      </div>
      <div>
        <span className="muted">候选人</span>
        <strong>{report.candidates.length} 人</strong>
      </div>
    </div>
  );
}

function CandidateRanking({
  candidates,
  selectedId,
  onSelect
}: {
  candidates: CandidateReport[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <aside className="ranking-list" aria-label="候选人排行">
      {candidates.map((candidate, index) => (
        <button
          key={candidate.candidate_id}
          type="button"
          className={candidate.candidate_id === selectedId ? "candidate-row active" : "candidate-row"}
          onClick={() => onSelect(candidate.candidate_id)}
        >
          <span className="rank-number">{String(index + 1).padStart(2, "0")}</span>
          <span className="candidate-main">
            <strong>{candidate.profile.name}</strong>
            <small>{candidateSummary(candidate.match_report)}</small>
          </span>
          <span className="score">{candidate.match_report.total_score}</span>
        </button>
      ))}
    </aside>
  );
}

function CandidateOverview({
  candidates,
  selectedId,
  onSelect
}: {
  candidates: CandidateReport[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="overview-pane">
      <header className="view-header">
        <div>
          <h2>候选人总览</h2>
        </div>
        <span className="view-meta">{candidates.length} 位候选人</span>
      </header>
      <div className="overview-list">
        {candidates.map((candidate, index) => (
          <button
            className={candidate.candidate_id === selectedId ? "overview-row active" : "overview-row"}
            key={candidate.candidate_id}
            onClick={() => onSelect(candidate.candidate_id)}
            type="button"
          >
            <span className="rank-number">{String(index + 1).padStart(2, "0")}</span>
            <span className="overview-main">
              <strong>{candidate.profile.name}</strong>
            </span>
            <span className="overview-score">{candidate.match_report.total_score}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function CandidateDetail({
  candidate,
  jdExtractionFacts,
  runId,
  view
}: {
  candidate: CandidateReport;
  jdExtractionFacts: ExtractedFact[];
  runId: string;
  view: Exclude<ResultView, "overview">;
}) {
  const report = candidate.match_report;
  return (
    <article className="detail-pane">
      <header className="candidate-header">
        <div>
          <h2>{candidate.profile.name}</h2>
          <p>{candidate.source_name}</p>
        </div>
        <div className="score-block">
          <span>{report.total_score}</span>
          <strong>匹配分</strong>
        </div>
      </header>

      {view === "extraction" ? (
        <section className="detail-section">
          <h3>抽取过程</h3>
          <ExtractionProcess jdFacts={jdExtractionFacts} profile={candidate.profile} resumeFacts={candidate.extraction_facts} />
        </section>
      ) : null}

      {view === "matching" ? (
        <>
          <section className="detail-section">
            <h3>匹配理由</h3>
            <List items={visibleDisplayItems(report.match_reasons)} />
          </section>
          <section className="detail-section">
            <h3>评分拆解</h3>
            <ScoreExplanation
              dimensionExplanations={report.dimension_explanations}
              dimensionScores={report.dimension_scores}
              requirementMatches={report.requirement_matches}
            />
          </section>
          <section className="detail-section risk-section">
            <h3>风险与待确认</h3>
            <List items={report.gap_reasons} />
          </section>
        </>
      ) : null}

      {view === "questions" ? (
        <section className="detail-section">
          <h3>面试问题</h3>
          {shouldSkipQuestionMaterials(report) ? (
            <p className="empty-facts">匹配分低于 40，已跳过面试题生成。</p>
          ) : (
            <ol className="question-list">
              {report.interview_questions.map((item, index) => (
                <li key={`${item.question}-${index}`}>
                  <strong>{item.question}</strong>
                  <span>{item.focus}</span>
                  <p>{item.scoring_criteria}</p>
                </li>
              ))}
            </ol>
          )}
        </section>
      ) : null}

    </article>
  );
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

function InterviewFinalReportCard({ report }: { report: InterviewFinalReport }) {
  return (
    <section className="interview-final-report followup-result">
      <h4>最终评估报告</h4>
      <div className="score-pills">
        <span>总分 {report.overall_score}</span>
        <span>清晰度 {report.clarity_score}</span>
        <span>深度 {report.depth_score}</span>
        <span>{consistencyLabel(report.evidence_consistency)}</span>
      </div>
      <div className="followup-question-card">
        <span>结论</span>
        <strong>{report.recommendation}</strong>
        <p>{report.summary}</p>
      </div>
      <div className="interview-report-grid">
        <div>
          <h5>优势</h5>
          <List items={report.strengths} />
        </div>
        <div>
          <h5>风险</h5>
          <List items={report.risks} />
        </div>
        <div>
          <h5>下一步</h5>
          <List items={report.next_steps} />
        </div>
      </div>
    </section>
  );
}

function ExtractionProcess({
  jdFacts,
  profile,
  resumeFacts
}: {
  jdFacts?: ExtractedFact[];
  profile?: CandidateProfile;
  resumeFacts?: ExtractedFact[];
}) {
  const visibleJdFacts = (jdFacts ?? []).slice(0, 12);
  const groupedResumeFacts = groupResumeFacts(resumeFacts ?? [], profile);
  return (
    <div className="extraction-grid">
      <ExtractionColumn title="JD 核心要求" facts={visibleJdFacts} emptyText="暂无 JD 抽取事实" />
      <ResumeExtractionColumn groups={groupedResumeFacts} />
    </div>
  );
}

function ExtractionColumn({ title, facts, emptyText }: { title: string; facts: ExtractedFact[]; emptyText: string }) {
  return (
    <div className="extraction-column">
      <div className="extraction-column-header">
        <strong>{title}</strong>
        <span>{facts.length} 项</span>
      </div>
      {facts.length ? (
        <div className="fact-list">
          {facts.map((fact, index) => (
            <FactRow fact={fact} key={`${fact.fact_type}-${fact.value}-${index}`} />
          ))}
        </div>
      ) : (
        <p className="empty-facts">{emptyText}</p>
      )}
    </div>
  );
}

interface FactGroup {
  section: string;
  facts: ExtractedFact[];
}

function ResumeExtractionColumn({ groups }: { groups: FactGroup[] }) {
  const total = groups.reduce((sum, group) => sum + group.facts.length, 0);
  return (
    <div className="extraction-column">
      <div className="extraction-column-header">
        <strong>简历中的重点</strong>
        <span>{total} 项</span>
      </div>
      {groups.length ? (
        <div className="section-fact-list">
          {groups.map((group) => (
            <FactSection group={group} key={group.section} />
          ))}
        </div>
      ) : (
        <p className="empty-facts">暂无简历中的重点</p>
      )}
    </div>
  );
}

function FactSection({ group }: { group: FactGroup }) {
  const skillFacts = group.facts.filter((fact) => fact.fact_type === "skill");
  const otherFacts = group.facts.filter((fact) => fact.fact_type !== "skill").slice(0, 4);
  return (
    <section className="fact-section">
      <div className="fact-section-header">
        <h4>{SECTION_LABELS[group.section] ?? group.section}</h4>
        <span>{group.facts.length} 项</span>
      </div>
      {skillFacts.length ? (
        <article className="fact-row compact-skill-row">
          <div className="fact-row-top">
            <span className="fact-type">专业技能</span>
          </div>
          <div className="skill-chip-list">
            {skillFacts.map((fact) => (
              <span className="skill-chip" key={`${fact.value}-${fact.line_start ?? "line"}`}>
                {fact.value}
              </span>
            ))}
          </div>
        </article>
      ) : null}
      {otherFacts.map((fact, index) => (
        <FactRow fact={fact} key={`${fact.fact_type}-${fact.value}-${index}`} />
      ))}
    </section>
  );
}

function FactRow({ fact }: { fact: ExtractedFact }) {
  return (
    <article className="fact-row">
      <div className="fact-row-top">
        <span className="fact-type">{factDisplayLabel(fact)}</span>
      </div>
      <strong>{fact.value}</strong>
    </article>
  );
}

function ScoreExplanation({
  dimensionExplanations,
  dimensionScores,
  requirementMatches
}: {
  dimensionExplanations?: DimensionExplanation[];
  dimensionScores: Record<string, number>;
  requirementMatches?: RequirementMatch[];
}) {
  const dimensions = dimensionExplanations?.length
    ? dimensionExplanations
    : Object.entries(dimensionScores).map(([dimension, score]) => ({
        dimension,
        score,
        max_score: dimension === "风险扣分" ? 0 : Math.max(score, 0),
        summary: dimension === "风险扣分" ? "辅助扣分项" : "旧报告未提供逐项解释"
      }));
  const visibleMatches = requirementMatches?.length ? requirementMatches : [];

  return (
    <div className="score-explanation">
      <div className="dimension-strip">
        {dimensions.map((item) => (
          <div className={item.dimension === "风险扣分" ? "dimension-card muted-card" : "dimension-card"} key={item.dimension}>
            <div>
              <span>{item.dimension}</span>
              <strong>
                {formatScore(item.score)}
                {item.max_score ? `/${formatScore(item.max_score)}` : ""}
              </strong>
            </div>
            <p>{item.summary}</p>
          </div>
        ))}
      </div>

      {visibleMatches.length ? (
        <div className="requirement-list">
          {visibleMatches.map((item, index) => (
            <RequirementMatchRow item={item} key={`${item.dimension}-${item.requirement}-${index}`} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function RequirementMatchRow({ item }: { item: RequirementMatch }) {
  return (
    <article className="requirement-row">
      <div className="requirement-main">
        <span className="dimension-label">{item.dimension}</span>
        <strong>{item.requirement}</strong>
        <p>{item.reason}</p>
      </div>
      <div className="requirement-score">
        <span className={`status-pill ${statusClass(item.status)}`}>{item.status}</span>
        <strong>贡献 {formatScore(item.contribution)}/{formatScore(item.max_score)}</strong>
      </div>
    </article>
  );
}

function List({ items }: { items: string[] }) {
  return (
    <ul>
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  );
}

function statusClass(status: string) {
  if (status === "强匹配" || status === "直接匹配") return "strong";
  if (status === "相关匹配") return "related";
  if (status === "弱匹配") return "weak";
  return "missing";
}

function consistencyLabel(value: string) {
  if (value === "consistent") return "证据一致";
  if (value === "contradictory") return "存在矛盾";
  return "证据较弱";
}

function sessionStatusLabel(value: string) {
  if (value === "completed") return "已完成";
  if (value === "ready_for_report") return "待生成报告";
  return "进行中";
}

function questionSourceLabel(value: string) {
  if (value === "dynamic_followup") return "动态追问";
  if (value === "fallback") return "兜底问题";
  return "面试问题";
}

function difficultyLabel(value: InterviewDifficulty) {
  return DIFFICULTY_OPTIONS.find((item) => item.id === value)?.label ?? "中级";
}

function interviewerStyleLabel(value: InterviewerStyle) {
  return INTERVIEWER_STYLES.find((item) => item.id === value)?.label ?? "亲切的 HR";
}

function candidateSummary(report: MatchReport) {
  const matchReasons = visibleDisplayItems(report.match_reasons);
  const gapReasons = visibleDisplayItems(report.gap_reasons);
  if (shouldPreferGapSummary(report)) {
    return gapReasons[0] ?? "暂未识别到明确匹配依据";
  }
  return matchReasons[0] ?? gapReasons[0] ?? "暂未识别到明确匹配依据";
}

function shouldPreferGapSummary(report: MatchReport) {
  const hasStrongEvidence = report.requirement_matches.some(
    (item) => (item.status === "强匹配" || item.status === "直接匹配") && item.contribution > 0
  );
  return report.total_score < 60 || !hasStrongEvidence;
}

function shouldSkipQuestionMaterials(report: MatchReport) {
  return report.total_score < QUESTION_MATERIAL_MIN_SCORE;
}

const SECTION_LABELS: Record<string, string> = {
  basic: "基本信息",
  education: "学历背景",
  experience: "实习/工作经验",
  projects: "项目经验",
  skills: "专业技能",
  summary: "自我评价",
  certifications: "证书资质",
  jd: "JD 核心要求"
};

const SECTION_ORDER = ["basic", "education", "experience", "projects", "skills", "summary", "certifications"];
const HIDDEN_RESUME_FACT_TYPES = new Set([
  "target_role",
  "location",
  "contact",
  "phone",
  "email",
  "domain_evidence",
  "领域证据",
  "ai_tool_application",
  "tool_application"
]);
const HIDDEN_DISPLAY_TEXT_PATTERNS = [/^AI\s*工具应用能力\s*[:：]/i];
const FACT_LABELS: Record<string, string> = {
  job_title: "岗位名称",
  required_skill: "必备技能",
  nice_to_have_skill: "加分项",
  responsibility: "核心职责",
  years_required: "年限要求",
  seniority: "级别要求",
  industry: "行业背景",
  hard_requirement: "硬性要求",
  education_summary: "学历背景",
  education: "学历背景",
  degree: "学历背景",
  work_summary: "核心工作",
  experience: "工作经历",
  experience_position: "任职信息",
  project: "项目经验",
  skill: "专业技能",
  certification: "证书资质",
  highlight: "亮点",
  summary: "亮点",
  metric: "量化成果",
  domain_evidence: "领域证据",
  risk: "风险点"
};

function groupResumeFacts(facts: ExtractedFact[], profile?: CandidateProfile): FactGroup[] {
  const factsWithProfileFallback = addProfileProjectFallback(facts, profile);
  const bySection = new Map<string, ExtractedFact[]>();
  for (const fact of factsWithProfileFallback.filter(isVisibleResumeFact)) {
    const section = fact.section || "unknown";
    bySection.set(section, [...(bySection.get(section) ?? []), fact]);
  }
  return [...bySection.entries()]
    .map(([section, sectionFacts]) => ({ section, facts: compactFactsForSection(section, sortFactsWithinSection(sectionFacts)) }))
    .filter((group) => group.facts.length > 0)
    .sort((left, right) => sectionRank(left.section) - sectionRank(right.section));
}

function sortFactsWithinSection(facts: ExtractedFact[]) {
  const rank: Record<string, number> = {
    education_summary: 1,
    work_summary: 1,
    project: 1,
    responsibility: 2,
    highlight: 3,
    experience_position: 3,
    education: 2,
    degree: 3,
    skill: 4,
    certification: 5,
    metric: 6,
    domain_evidence: 7,
    summary: 8
  };
  return [...facts].sort((left, right) => {
    if (left.section === right.section && ["experience", "projects", "summary"].includes(left.section)) {
      const lineDelta = (left.line_start ?? 9999) - (right.line_start ?? 9999);
      if (lineDelta !== 0) return lineDelta;
    }
    return (rank[left.fact_type] ?? 99) - (rank[right.fact_type] ?? 99);
  });
}

function compactFactsForSection(section: string, facts: ExtractedFact[]) {
  if (section === "education") {
    return facts.filter((fact) => fact.fact_type === "education_summary" || fact.fact_type === "education").slice(0, 1);
  }
  if (section === "experience") {
    const richerFacts = facts.filter(
      (fact) =>
        fact.fact_type === "work_summary"
        || fact.fact_type === "responsibility"
        || fact.fact_type === "highlight"
        || fact.fact_type === "summary"
        || fact.fact_type === "metric"
    );
    const displayFacts = richerFacts.length ? richerFacts : facts;
    return compactNarrativeFacts(displayFacts, "experience").slice(0, 4);
  }
  if (section === "projects") {
    return compactNarrativeFacts(facts, "projects").slice(0, 6);
  }
  if (section === "skills") {
    return compactSkillFacts(facts);
  }
  if (section === "summary") {
    const highlightFacts = facts.filter((fact) => fact.fact_type === "summary" || fact.fact_type === "highlight");
    return compactSummaryFacts(highlightFacts.length ? highlightFacts : facts).slice(0, 4);
  }
  return facts.slice(0, 6);
}

function isVisibleResumeFact(fact: ExtractedFact) {
  return fact.section !== "basic"
    && !HIDDEN_RESUME_FACT_TYPES.has(fact.fact_type)
    && !isCitationOnlyText(fact.value)
    && !isLowContextMetricFact(fact);
}

function addProfileProjectFallback(facts: ExtractedFact[], profile?: CandidateProfile) {
  if (!profile?.projects?.length) return facts;
  const projectFacts = facts.filter((fact) => fact.section === "projects");
  const hasProjectNarrative = projectFacts.some(
    (fact) => fact.fact_type === "project" && cleanFactText(fact.value).length >= 12
  );
  if (hasProjectNarrative) return facts;
  const projectSummary = profile.projects.map(cleanFactText).find((value) => value.length >= 16);
  if (!projectSummary) return facts;
  const fallbackFact: ExtractedFact = {
    fact_type: "project",
    value: projectSummary,
    evidence: projectSummary,
    section: "projects",
    line_start: 0,
    line_end: 0,
    confidence: 0.7,
    extractor: "profile_projection"
  };
  return [fallbackFact, ...facts];
}

function isLowContextMetricFact(fact: ExtractedFact) {
  return fact.fact_type === "metric" && isLowContextMetricText(fact.value);
}

function isLowContextMetricText(value: string) {
  const text = cleanFactText(value);
  if (!text) return true;
  const semanticText = text
    .replace(/百分之|以上|以下|左右|约|超过|余|多|近|达|达到/g, "")
    .replace(/[0-9０-９一二三四五六七八九十百千万亿两零点.,+/%％\s-]/g, "")
    .replace(/(项|件|条|个|次|名|场|倍|人|元|小时|分钟|天|个月|年|分|套|份|篇)$/g, "")
    .trim();
  return semanticText.length < 2;
}

function visibleDisplayItems(items: string[]) {
  return items.filter((item) => !isHiddenDisplayText(item));
}

function isHiddenDisplayText(value: string) {
  return HIDDEN_DISPLAY_TEXT_PATTERNS.some((pattern) => pattern.test(value.trim()));
}

function compactNarrativeFacts(facts: ExtractedFact[], section: string) {
  const result: ExtractedFact[] = [];
  let current: ExtractedFact | null = null;
  for (const fact of facts.filter((item) => !isCitationOnlyText(item.value))) {
    if (!current) {
      current = fact;
      continue;
    }
    if (isContainedText(current.value, fact.value)) {
      continue;
    }
    if (isContainedText(fact.value, current.value)) {
      current = { ...fact, fact_type: current.fact_type };
      continue;
    }
    if (shouldMergeWithPrevious(current, fact, section)) {
      current = mergeFacts(current, fact, section === "projects" && isProjectTitleLike(current.value) ? "colon" : "plain");
      continue;
    }
    result.push(current);
    current = fact;
  }
  if (current) {
    result.push(current);
  }
  return dedupeFactsByValue(result);
}

function compactSummaryFacts(facts: ExtractedFact[]) {
  if (!facts.length) return [];
  const base = facts[0];
  const phrases: string[] = [];
  for (const fact of facts) {
    for (const phrase of splitSummaryPhrases(fact.value)) {
      appendSummaryPhrase(phrases, phrase);
    }
  }
  return removeRedundantPhrases(phrases).map((value, index) => ({
    ...base,
    value,
    line_start: facts[index]?.line_start ?? base.line_start,
    line_end: facts[index]?.line_end ?? base.line_end
  }));
}

function splitSummaryPhrases(value: string) {
  return cleanFactText(value)
    .split(/\s*[；;]\s*/)
    .map((item) => trimEndingPunctuation(trimStartingPunctuation(item)))
    .filter((item) => item.length >= 4);
}

function appendSummaryPhrase(phrases: string[], phrase: string) {
  if (phrases.some((existing) => isContainedText(existing, phrase))) return;
  const containedIndex = phrases.findIndex((existing) => isContainedText(phrase, existing));
  if (containedIndex >= 0) {
    phrases.splice(containedIndex, 1);
  }
  const last = phrases[phrases.length - 1];
  if (last && shouldJoinSummaryPhrase(last, phrase)) {
    phrases[phrases.length - 1] = `${trimEndingPunctuation(last)}${trimStartingPunctuation(phrase)}`;
    return;
  }
  phrases.push(phrase);
}

function shouldMergeWithPrevious(previous: ExtractedFact, current: ExtractedFact, section: string) {
  const previousText = cleanFactText(previous.value);
  const currentText = cleanFactText(current.value);
  if (!previousText || !currentText) return false;
  if (section === "projects" && isProjectTitleLike(previousText)) return true;
  if (!areAdjacentFacts(previous, current)) return false;
  if (isContinuationFragment(currentText) || isMetricLikeFragment(currentText)) return true;
  if (endsLikeUnfinishedPhrase(previousText)) return true;
  return false;
}

function mergeFacts(previous: ExtractedFact, current: ExtractedFact, mode: "plain" | "colon") {
  const previousText = trimEndingPunctuation(cleanFactText(previous.value));
  const currentText = trimStartingPunctuation(cleanFactText(current.value));
  const separator = mode === "plain" && shouldInsertSpaceBetweenFragments(previousText, currentText) ? " " : "";
  const value = mode === "colon"
    ? `${previousText}：${currentText}`
    : `${previousText}${separator}${currentText}`;
  return {
    ...previous,
    value,
    evidence: [previous.evidence, current.evidence].filter(Boolean).join("\n"),
    line_end: current.line_end ?? previous.line_end
  };
}

function compactSkillFacts(facts: ExtractedFact[]) {
  const skillFacts = facts.filter((fact) => fact.fact_type === "skill");
  if (!skillFacts.length) return facts.slice(0, 6);
  const base = skillFacts[0];
  const groups: SkillDisplayGroup[] = [];
  let activeGroup: SkillDisplayGroup | null = null;
  for (const fact of skillFacts) {
    for (const segment of splitSkillPhrase(fact.value)) {
      const parsed = parseSkillSegment(segment);
      if (!parsed.value) continue;
      if (isParentheticalOnly(parsed.value) && groups.length) {
        appendToLastSkillItem(groups[groups.length - 1], parsed.value, "concat");
        continue;
      }
      if (parsed.label) {
        activeGroup = createSkillGroup(parsed.value, fact, parsed.label);
        groups.push(activeGroup);
        continue;
      }
      if (activeGroup && shouldAttachSkillContinuation(activeGroup, parsed.value, fact)) {
        appendToLastSkillItem(
          activeGroup,
          parsed.value,
          shouldConcatSkillContinuation(activeGroup.items[activeGroup.items.length - 1], parsed.value) ? "concat" : "slash"
        );
        activeGroup.line_end = fact.line_end ?? activeGroup.line_end;
        continue;
      }
      activeGroup = null;
      groups.push(createSkillGroup(parsed.value, fact));
    }
  }
  const displayValues = removeRedundantPhrases(groups.map(formatSkillGroup).filter(Boolean));
  return displayValues.map((value, index) => ({
    ...base,
    value,
    line_start: groups[index]?.line_start ?? base.line_start,
    line_end: groups[index]?.line_end ?? base.line_end
  }));
}

interface SkillDisplayGroup {
  label?: string;
  items: string[];
  line_start?: number;
  line_end?: number;
}

function splitSkillPhrase(value: string) {
  return value
    .split(/\s*[；;]\s*/)
    .map(cleanSkillText)
    .filter((item) => item.length >= 2 && !["熟悉", "熟练", "精通", "掌握"].includes(item));
}

function parseSkillSegment(value: string) {
  const text = cleanSkillText(value);
  const match = text.match(/^([^:：]{2,16})[:：]\s*(.+)$/u);
  if (!match) return { value: text };
  const label = cleanSkillLabel(match[1]);
  const item = cleanSkillText(match[2]);
  if (!label || !item) return { value: text };
  return { label, value: item };
}

function cleanSkillText(value: string) {
  return cleanFactText(value)
    .replace(/^[•·\-\*]\s*/u, "")
    .replace(/\s*\[\d+\]\s*/gu, "")
    .replace(/^(熟练掌握|熟练运用|熟练使用|熟悉掌握|精通|熟悉|掌握|了解|具备)\s*/u, "")
    .replace(/[:：]\s*(熟练掌握|熟练运用|熟练使用|熟悉掌握|精通|熟悉|掌握|了解|具备)\s*/u, "：")
    .replace(/^极强的/u, "")
    .replace(/AIGC\s*工作流/giu, "AIGC 工作流")
    .replace(/TikTok\s*平台/giu, "TikTok平台")
    .replace(/[。；;]+$/u, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function cleanSkillLabel(value: string) {
  const label = cleanFactText(value).replace(/^[•·\-\*]\s*/u, "").trim();
  if (!/^[\u4e00-\u9fa5A-Za-z0-9 /&+-]{2,16}$/u.test(label)) return "";
  return label;
}

function createSkillGroup(value: string, fact: ExtractedFact, label?: string): SkillDisplayGroup {
  return {
    label,
    items: [value],
    line_start: fact.line_start ?? undefined,
    line_end: fact.line_end ?? undefined
  };
}

function shouldAttachSkillContinuation(group: SkillDisplayGroup, value: string, fact: ExtractedFact) {
  if (!group.label) return false;
  if (fact.line_start && group.line_end && fact.line_start > group.line_end + 1) return false;
  if (/^(具备|拥有|负责|带领|参与|主导|获得|获|能够|能)/u.test(value)) return false;
  return true;
}

function appendToLastSkillItem(group: SkillDisplayGroup, value: string, mode: "concat" | "slash") {
  const cleaned = cleanSkillText(value);
  if (!cleaned) return;
  if (!group.items.length) {
    group.items.push(cleaned);
    return;
  }
  if (mode === "concat") {
    group.items[group.items.length - 1] = `${trimEndingPunctuation(group.items[group.items.length - 1])}${trimStartingPunctuation(cleaned)}`;
    return;
  }
  if (!group.items.some((item) => normalizeComparableText(item) === normalizeComparableText(cleaned))) {
    group.items.push(cleaned);
  }
}

function shouldConcatSkillContinuation(previous: string | undefined, current: string) {
  if (!previous) return false;
  if (/^(频|视频|图片|图|片|\/)/u.test(current)) return true;
  return /[视图]$/u.test(previous);
}

function formatSkillGroup(group: SkillDisplayGroup) {
  const items = removeRedundantPhrases(group.items);
  if (!items.length) return "";
  const text = items.join(" / ");
  return group.label ? `${group.label}：${text}` : text;
}

function removeRedundantPhrases(phrases: string[]) {
  const unique = dedupeStrings(phrases);
  return unique.filter((phrase, index) => {
    const normalized = normalizeComparableText(phrase);
    return !unique.some((other, otherIndex) => {
      if (index === otherIndex) return false;
      const otherNormalized = normalizeComparableText(other);
      return otherNormalized.includes(normalized) && otherNormalized.length > normalized.length;
    });
  }).slice(0, 8);
}

function dedupeFactsByValue(facts: ExtractedFact[]) {
  const seen = new Set<string>();
  return facts.filter((fact) => {
    const key = normalizeComparableText(fact.value);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function dedupeStrings(values: string[]) {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const key = normalizeComparableText(value);
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(value);
  }
  return result;
}

function areAdjacentFacts(previous: ExtractedFact, current: ExtractedFact) {
  if (!previous.line_end || !current.line_start) return true;
  return current.line_start <= previous.line_end + 1;
}

function isContinuationFragment(value: string) {
  return /^(至|到|与|及|和|并|量|感|后|成本|爆款|日均|获|获得|提升|降低|缩短|节省)/u.test(value);
}

function isMetricLikeFragment(value: string) {
  return value.length <= 16 && /\d/.test(value) && /(条|个|人|元|%|小时|天|万|次|名|场)/u.test(value);
}

function endsLikeUnfinishedPhrase(value: string) {
  return /(累计产出|从\d+(?:\.\d+)?[天小时分钟]*缩短|节省设计|通过\s*AI\s*批|与情|结合|与售|提升|降低|缩短|产出|完成|利用|使用|负责|拥有|逻辑)$/u.test(value);
}

function shouldInsertSpaceBetweenFragments(previous: string, current: string) {
  return /[\u4e00-\u9fa5]$/u.test(previous) && /^[A-Za-z0-9]/u.test(current);
}

function isCitationOnlyText(value: string) {
  return /^[\s。.,，；;]*[\[［【]\d+[\]］】][\s。.,，；;]*$/u.test(value);
}

function shouldJoinSummaryPhrase(previous: string, current: string) {
  if (/^思维/u.test(current) && /逻辑$/u.test(previous)) return true;
  if (isContinuationFragment(current)) return true;
  return endsLikeUnfinishedPhrase(previous) && !startsLikeNewFact(current);
}

function startsLikeNewFact(value: string) {
  return /^(具备|拥有|负责|带领|参与|主导|使用|利用|熟悉|精通|掌握|获得|获|能够|能)/u.test(value);
}

function isProjectTitleLike(value: string) {
  const text = cleanFactText(value);
  return text.length <= 36
    && /(项目|平台|系统|实战|营销|创业|案例)/u.test(text)
    && !/[，,；;。]/u.test(text)
    && !/(负责|带领|利用|使用|生成|节省|提升|降低|产出|完成)/u.test(text);
}

function isParentheticalOnly(value: string) {
  return /^[（(].+[）)]$/u.test(value);
}

function cleanFactText(value: string) {
  return value.replace(/\s*[\[［【]\d+[\]］】]\s*/gu, " ").replace(/\s+/g, " ").trim();
}

function trimEndingPunctuation(value: string) {
  return value.replace(/[。；;，,\s]+$/u, "");
}

function trimStartingPunctuation(value: string) {
  return value.replace(/^[。；;，,\s]+/u, "");
}

function normalizeComparableText(value: string) {
  return value.replace(/\s+/g, "").replace(/[。；;，,、:：]/g, "").toLowerCase();
}

function isContainedText(container: string, candidate: string) {
  const normalizedContainer = normalizeComparableText(container);
  const normalizedCandidate = normalizeComparableText(candidate);
  return normalizedCandidate.length >= 2
    && normalizedContainer.length > normalizedCandidate.length
    && normalizedContainer.includes(normalizedCandidate);
}

function factDisplayLabel(fact: ExtractedFact) {
  return FACT_LABELS[fact.fact_type] ?? (containsChinese(fact.fact_type) ? fact.fact_type : "关键事实");
}

function containsChinese(value: string) {
  return /[\u4e00-\u9fa5]/.test(value);
}

function sectionRank(section: string) {
  const index = SECTION_ORDER.indexOf(section);
  return index === -1 ? 99 : index;
}

function formatScore(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}
