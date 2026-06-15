import {
  BarChart3,
  Bot,
  ChevronRight,
  FileStack,
  Settings,
  Sparkles,
  Users,
  type LucideIcon
} from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

import {
  createRun,
  deleteInterviewSession,
  deleteRunCandidate,
  deleteAllRuns,
  listInterviewSessions,
  listRuns
} from "./api";
import type {
  InterviewSession,
  RunReport
} from "./types";
import type { InputMode, PendingAnalysisGroup, ResultView } from "./workspaceTypes";
import { InterviewRecordsWorkspace } from "./workspaces/InterviewRecordsWorkspace";
import { MockInterviewWorkspace } from "./workspaces/MockInterviewWorkspace";
import { AnalysisResultsWorkspace, ResumeManagementWorkspace } from "./workspaces/ResumeManagementWorkspace";
import { SettingsWorkspace } from "./workspaces/SettingsWorkspace";
import "./styles.css";

type WorkspaceView = "resumes" | "analysis" | "interview" | "records" | "settings";

const ROUTES: Record<WorkspaceView, string> = {
  resumes: "/history",
  analysis: "/analysis",
  interview: "/interview-hub",
  records: "/interviews",
  settings: "/settings"
};

function normalizePathname(pathname: string): string {
  if (pathname.length > 1 && pathname.endsWith("/")) {
    return pathname.slice(0, -1);
  }
  return pathname;
}

function workspaceFromPath(pathname: string): WorkspaceView {
  switch (normalizePathname(pathname)) {
    case "/":
    case "/history":
      return "resumes";
    case "/analysis":
      return "analysis";
    case "/interview-hub":
      return "interview";
    case "/interviews":
      return "records";
    case "/settings":
      return "settings";
    default:
      return "resumes";
  }
}

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
      { id: "resumes", label: "简历管理", description: "按 JD 分组给简历打分", icon: FileStack },
      { id: "analysis", label: "分析结果", description: "AI简历解析与评分", icon: BarChart3 },
      { id: "interview", label: "模拟面试", description: "配置面试流程", icon: Sparkles },
      { id: "records", label: "面试记录", description: "管理面试历史记录", icon: Users }
    ]
  },
  {
    title: "系统",
    items: [
      { id: "settings", label: "设置", description: "管理模型服务", icon: Settings }
    ]
  }
];

function createPendingAnalysisGroup({
  resumeFiles,
  resumeText,
  resumeInputMode
}: {
  resumeFiles: File[];
  resumeText: string;
  resumeInputMode: InputMode;
}): PendingAnalysisGroup {
  const candidateNames =
    resumeInputMode === "file" && resumeFiles.length
      ? resumeFiles.map((file) => file.name)
      : [resumeText.trim().split(/\s|，|,|\n/).filter(Boolean)[0] || "文本简历"];
  return {
    id: `pending-${Date.now()}`,
    title: "等待大模型评分结果",
    candidateNames,
    createdAt: new Date().toISOString()
  };
}

export default function App() {
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceView>(() =>
    workspaceFromPath(window.location.pathname)
  );
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
  const [pendingAnalysis, setPendingAnalysis] = useState<PendingAnalysisGroup | null>(null);
  const [interviewSessions, setInterviewSessions] = useState<InterviewSession[]>([]);
  const [resumeInterviewSession, setResumeInterviewSession] = useState<InterviewSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recordsError, setRecordsError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadWorkspaceState() {
      try {
        const [savedRuns, savedSessions] = await Promise.all([
          listRuns(),
          listInterviewSessions()
        ]);
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

  useEffect(() => {
    const syncWorkspaceFromPath = () => {
      setActiveWorkspace(workspaceFromPath(window.location.pathname));
    };
    window.addEventListener("popstate", syncWorkspaceFromPath);
    syncWorkspaceFromPath();
    return () => {
      window.removeEventListener("popstate", syncWorkspaceFromPath);
    };
  }, []);

  const navigateWorkspace = (workspace: WorkspaceView) => {
    const nextPath = ROUTES[workspace];
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, "", nextPath);
    }
    setActiveWorkspace(workspace);
  };

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
    const pending = createPendingAnalysisGroup({
      resumeFiles,
      resumeText,
      resumeInputMode
    });
    setPendingAnalysis(pending);
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
      setPendingAnalysis(null);
      navigateWorkspace("resumes");
      setActiveView("overview");
    } catch (err) {
      setPendingAnalysis(null);
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
    setResumeInterviewSession(null);
    setSelectedRunId(runId);
    setReport(nextRun ?? report);
    setSelectedId(nextRun?.candidates[0]?.candidate_id ?? null);
    setActiveView("overview");
  }

  function handleSessionChange(session: InterviewSession) {
    setRecordsError(null);
    setInterviewSessions((current) => [session, ...current.filter((item) => item.session_id !== session.session_id)]);
    setResumeInterviewSession((current) => (current?.session_id === session.session_id ? session : current));
  }

  function handleResumeInterviewSession(session: InterviewSession) {
    const availableRuns = report
      ? [report, ...runs.filter((item) => item.run_id !== report.run_id)]
      : runs;
    const nextRun = availableRuns.find((item) => item.run_id === session.run_id);
    if (!nextRun) {
      setRecordsError("无法继续该面试：找不到对应的简历分析结果。");
      return;
    }
    const nextCandidate = nextRun.candidates.find((candidate) => candidate.candidate_id === session.candidate_id);
    if (!nextCandidate) {
      setRecordsError("无法继续该面试：找不到对应的候选人。");
      return;
    }
    setRecordsError(null);
    setSelectedRunId(nextRun.run_id);
    setReport(nextRun);
    setSelectedId(nextCandidate.candidate_id);
    setResumeInterviewSession(session);
    navigateWorkspace("interview");
  }

  async function handleDeleteSession(sessionId: string) {
    setRecordsError(null);
    try {
      await deleteInterviewSession(sessionId);
      setInterviewSessions((current) => current.filter((item) => item.session_id !== sessionId));
      setResumeInterviewSession((current) => (current?.session_id === sessionId ? null : current));
    } catch (err) {
      setRecordsError(err instanceof Error ? err.message : "面试记录删除失败。");
    }
  }

  async function handleDeleteResume(runId: string, candidateId: string) {
    setError(null);
    try {
      await deleteRunCandidate(runId, candidateId);
      const nextRuns = await listRuns();
      const nextSessions = await listInterviewSessions();
      setRuns(nextRuns);
      setInterviewSessions(nextSessions);
      setResumeInterviewSession(null);

      const nextSelectedRun = nextRuns.find((item) => item.run_id === selectedRunId) ?? null;
      if (!nextRuns.length) {
        setReport(null);
        setSelectedRunId(null);
        setSelectedId(null);
        return;
      }

      const finalSelectedRunId = nextSelectedRun ? nextSelectedRun.run_id : nextRuns[0].run_id;
      const finalSelectedRun = nextRuns.find((item) => item.run_id === finalSelectedRunId) ?? nextRuns[0];
      setSelectedRunId(finalSelectedRun.run_id);
      setReport(finalSelectedRun);
      setSelectedId((current) => {
        const candidates = finalSelectedRun.candidates;
        if (candidates.some((item) => item.candidate_id === current)) {
          return current;
        }
        return candidates[0]?.candidate_id ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "候选人删除失败。");
    }
  }

  async function handleDeleteAllRuns() {
    setError(null);
    const confirmed = window.confirm("确定清空全部历史上传吗？该操作不可恢复。");
    if (!confirmed) {
      return;
    }
    try {
      await deleteAllRuns();
      const nextRuns = await listRuns();
      const nextSessions = await listInterviewSessions();
      setRuns(nextRuns);
      setInterviewSessions(nextSessions);
      setReport(null);
      setSelectedRunId(null);
      setSelectedId(null);
      setPendingAnalysis(null);
      setResumeInterviewSession(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "全部历史上传清空失败。")
    }
  }

  return (
    <div className="app-shell">
      <Sidebar activeWorkspace={activeWorkspace} onChange={navigateWorkspace} />
      <main className="workspace-main">
        {activeWorkspace === "resumes" ? (
          <ResumeManagementWorkspace
            error={error}
            jdFile={jdFile}
            jdInputMode={jdInputMode}
            jdText={jdText}
            loading={loading}
            pendingAnalysis={pendingAnalysis}
            resumeFiles={resumeFiles}
            resumeInputMode={resumeInputMode}
            resumeText={resumeText}
            runs={runs}
            selectedRunId={selectedRun?.run_id ?? null}
            onJdFileChange={setJdFile}
            onJdInputModeChange={setJdInputMode}
            onJdTextChange={setJdText}
            onResumeFilesChange={handleResumeFiles}
            onResumeInputModeChange={setResumeInputMode}
            onResumeTextChange={setResumeText}
            onSelectCandidate={setSelectedId}
            onSelectRun={handleSelectRun}
            onSubmit={handleSubmit}
            onDeleteCandidate={handleDeleteResume}
            onDeleteAllRuns={handleDeleteAllRuns}
          />
        ) : null}

        {activeWorkspace === "analysis" ? (
          <AnalysisResultsWorkspace
            activeView={activeView}
            report={selectedRun}
            selectedCandidate={selectedCandidate}
            onActiveViewChange={setActiveView}
            onSelectCandidate={setSelectedId}
          />
        ) : null}

        {activeWorkspace === "interview" ? (
          <MockInterviewWorkspace
            report={selectedRun}
            selectedCandidate={selectedCandidate}
            onSelectCandidate={setSelectedId}
            onSessionChange={handleSessionChange}
            resumeSession={resumeInterviewSession}
            onResumeSessionConsumed={() => setResumeInterviewSession(null)}
          />
        ) : null}

        {activeWorkspace === "records" ? (
          <InterviewRecordsWorkspace
            error={recordsError}
            sessions={interviewSessions}
            runs={runs}
            onDeleteSession={handleDeleteSession}
            onResumeSession={handleResumeInterviewSession}
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
