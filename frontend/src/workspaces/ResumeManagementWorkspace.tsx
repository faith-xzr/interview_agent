import {
  AlertCircle,
  ArrowUpRight,
  BarChart3,
  Briefcase,
  CheckCircle2,
  ChevronRight,
  FileArchive,
  FileQuestion,
  FileStack,
  FileText,
  FileType2,
  Loader2,
  Paperclip,
  Search,
  Trash2
} from "lucide-react";
import { ChangeEvent, FormEvent, type ReactNode } from "react";

import { List } from "../components/List";
import { PageTitle } from "../components/PageTitle";
import {
  factDisplayLabel,
  formatScore
} from "../factDisplay";
import { hasQuestionMaterials } from "../matchReportDisplay";
import type {
  CandidateReport,
  DimensionExplanation,
  AuditEvent,
  ExtractedFact,
  RequirementMatch,
  RunReport
} from "../types";
import type { InputMode, PendingAnalysisGroup, ResultView } from "../workspaceTypes";

const DETAIL_VIEWS: Array<{ id: ResultView; label: string }> = [
  { id: "overview", label: "总览" },
  { id: "extraction", label: "结构化提取" },
  { id: "matching", label: "智能匹配打分" },
  { id: "questions", label: "试题生成" }
];

function candidateSourceFileUrl(runId: string, candidateId: string) {
  return `/api/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(candidateId)}/source-file`;
}

export function ResumeManagementWorkspace({
  error,
  jdFile,
  jdInputMode,
  jdText,
  loading,
  pendingAnalysis,
  resumeFiles,
  resumeInputMode,
  resumeText,
  runs,
  selectedRunId,
  onJdFileChange,
  onJdInputModeChange,
  onJdTextChange,
  onResumeFilesChange,
  onResumeInputModeChange,
  onResumeTextChange,
  onSelectCandidate,
  onSelectRun,
  onDeleteCandidate,
  onDeleteAllRuns,
  onSubmit
}: {
  error: string | null;
  jdFile: File | null;
  jdInputMode: InputMode;
  jdText: string;
  loading: boolean;
  pendingAnalysis: PendingAnalysisGroup | null;
  resumeFiles: File[];
  resumeInputMode: InputMode;
  resumeText: string;
  runs: RunReport[];
  selectedRunId: string | null;
  onJdFileChange: (file: File | null) => void;
  onJdInputModeChange: (mode: InputMode) => void;
  onJdTextChange: (value: string) => void;
  onResumeFilesChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onResumeInputModeChange: (mode: InputMode) => void;
  onResumeTextChange: (value: string) => void;
  onSelectCandidate: (id: string) => void;
  onSelectRun: (id: string) => void;
  onDeleteCandidate: (runId: string, candidateId: string) => void;
  onDeleteAllRuns: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="workspace-stack">
      <PageTitle
        icon={FileStack}
        title="简历管理"
      />

      <section className="card form-card workspace-card">
        <form className="input-form" onSubmit={onSubmit}>
          <div className="form-grid">
            <FieldGroup
              label="职位描述（JD）"
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
                  files={jdFile ? [jdFile] : []}
                  emptySummary="支持 PDF / DOCX / TXT"
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
                  files={resumeFiles}
                  emptySummary="支持 PDF / DOCX / TXT，可批量选择"
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
          <div className="toolbar-actions">
            <span>{runs.length + (pendingAnalysis ? 1 : 0)} 个岗位分组</span>
            <button
              className="top-action top-action-danger"
              type="button"
              onClick={() => {
                if (runs.length === 0) {
                  return;
                }
                onDeleteAllRuns();
              }}
              disabled={runs.length === 0}
            >
              <Trash2 size={16} aria-hidden="true" />
              <span>清空历史上传</span>
            </button>
          </div>
        </div>
        {runs.length || pendingAnalysis ? (
          <div className="job-group-list">
            {pendingAnalysis ? <PendingJobGroup pending={pendingAnalysis} /> : null}
            {runs.map((item) => (
              <article className={item.run_id === selectedRunId ? "job-group active" : "job-group"} key={item.run_id}>
                <button type="button" onClick={() => onSelectRun(item.run_id)}>
                  <Briefcase size={20} aria-hidden="true" />
                  <span>
                    <strong>{item.jd_profile.job_title}</strong>
                    <small>
                      {new Date(item.created_at).toLocaleDateString("zh-CN")} · {item.candidates.length} 份简历
                    </small>
                  </span>
                  <ChevronRight size={18} aria-hidden="true" />
                </button>
                <div className="job-candidate-table">
                  {item.candidates.map((candidate) => (
                    <div
                      key={`${item.run_id}-${candidate.candidate_id}`}
                      className="job-candidate-row"
                      role="button"
                      tabIndex={0}
                      onClick={() => {
                        onSelectRun(item.run_id);
                        onSelectCandidate(candidate.candidate_id);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          onSelectRun(item.run_id);
                          onSelectCandidate(candidate.candidate_id);
                        }
                      }}
                    >
                      <span className="document-icon"><FileText size={20} aria-hidden="true" /></span>
                      <span className="candidate-cell">
                        <strong>{candidate.profile.name}</strong>
                        {candidate.source_file ? (
                          <a
                            className="candidate-source-link"
                            href={candidateSourceFileUrl(item.run_id, candidate.candidate_id)}
                            target="_blank"
                            rel="noreferrer"
                            aria-label={`打开源文件 ${candidate.source_file.filename}`}
                            onClick={(event) => event.stopPropagation()}
                          >
                            {candidate.source_name}
                          </a>
                        ) : (
                          <small>{candidate.source_name}</small>
                        )}
                      </span>
                      <span className="status-ok"><CheckCircle2 size={18} aria-hidden="true" /> 分析完成</span>
                      <span className="score-cell">{candidate.match_report.total_score}</span>
                      <button
                        className="icon-button candidate-delete-button"
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onDeleteCandidate(item.run_id, candidate.candidate_id);
                        }}
                        aria-label="删除这份简历历史"
                      >
                        <Trash2 size={16} aria-hidden="true" />
                      </button>
                    </div>
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
    </div>
  );
}

export function AnalysisResultsWorkspace({
  activeView,
  report,
  selectedCandidate,
  onActiveViewChange,
  onSelectCandidate
}: {
  activeView: ResultView;
  report: RunReport | null;
  selectedCandidate: CandidateReport | null;
  onActiveViewChange: (view: ResultView) => void;
  onSelectCandidate: (id: string) => void;
}) {
  return (
    <div className="workspace-stack">
      <PageTitle icon={BarChart3} title="分析结果" />
      {report ? <LlmFallbackAlert report={report} /> : null}
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
                view={activeView}
              />
            </div>
          )}
        </section>
      ) : (
        <div className="card empty-state">
          <h2>等待大模型评分结果</h2>
          <p>请先在简历管理上传 JD 和简历，并开始智能筛选。</p>
        </div>
      )}
    </div>
  );
}

function PendingJobGroup({ pending }: { pending: PendingAnalysisGroup }) {
  return (
    <article className="job-group pending-job-group" aria-label="分析中的岗位分组">
      <button type="button" disabled>
        <Briefcase size={20} aria-hidden="true" />
        <span>
          <strong>{pending.title}</strong>
          <small>
            {new Date(pending.createdAt).toLocaleDateString("zh-CN")} · {pending.candidateNames.length} 份简历
          </small>
        </span>
        <Loader2 className="spin" size={18} aria-hidden="true" />
      </button>
      <div className="job-candidate-table">
        {pending.candidateNames.map((candidateName, index) => (
          <div className="job-candidate-row pending-candidate-row" key={`${pending.id}-${candidateName}-${index}`}>
            <span className="document-icon"><FileText size={20} aria-hidden="true" /></span>
            <span className="candidate-cell">
              <strong>{candidateName}</strong>
              <small>评分未完成</small>
            </span>
            <span className="status-pending"><Loader2 className="spin" size={18} aria-hidden="true" /> 分析中</span>
            <span className="score-cell pending-score">评分未完成</span>
          </div>
        ))}
      </div>
    </article>
  );
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
  hint?: string;
  mode: InputMode;
  onModeChange: (mode: InputMode) => void;
  modeId: string;
  children: ReactNode;
}) {
  return (
    <div className="field-group">
      <div className="field-head">
        <div>
          <label className="field-label" htmlFor={modeId}>
            {label}
          </label>
          {hint ? <p className="field-hint">{hint}</p> : null}
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
  files = [],
  emptySummary
}: {
  id: string;
  accept: string;
  multiple?: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  label: string;
  files?: File[];
  emptySummary: string;
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
      <div className={files.length ? "file-picker-summary file-picker-summary-selected" : "file-picker-summary"}>
        {files.length ? (
          <div className="file-chip-list">
            {files.map((file) => (
              <SelectedFileChip file={file} key={`${file.name}-${file.size}-${file.lastModified}`} />
            ))}
          </div>
        ) : (
          <span className="file-picker-empty">{emptySummary}</span>
        )}
      </div>
    </div>
  );
}

function LlmFallbackAlert({ report }: { report: RunReport }) {
  const items = llmFallbackItems(report);
  if (!items.length) {
    return null;
  }
  return (
    <section className="llm-alert" role="alert" aria-label="LLM 服务调用失败">
      <AlertCircle size={20} aria-hidden="true" />
      <div className="llm-alert-main">
        <strong>LLM 服务调用失败</strong>
        <div className="llm-alert-list">
          {items.map((item) => (
            <span className="llm-alert-item" key={`${item.stage}-${item.reason}`}>
              <b>{item.label}</b>
              <small>按照预定义规则执行</small>
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function llmFallbackItems(report: RunReport) {
  const items: Array<{ stage: string; label: string; reason: string; model: string }> = [];
  for (const event of report.audit_events ?? []) {
    if (!isLlmFallbackEvent(event)) {
      continue;
    }
    items.push({
      stage: event.stage,
      label: llmStageLabel(event.stage),
      reason: compactDisplayText(event.failure_code || event.message),
      model: event.model ?? ""
    });
  }
  if (!items.length) {
    for (const warning of report.warnings ?? []) {
      if (!warning.includes("LLM")) {
        continue;
      }
      items.push({
        stage: warningStage(warning),
        label: llmStageLabel(warningStage(warning)),
        reason: compactDisplayText(warning),
        model: ""
      });
    }
  }
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = `${item.stage}-${item.reason}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function isLlmFallbackEvent(event: AuditEvent) {
  if (!event.fallback_strategy?.startsWith("local_rule")) {
    return false;
  }
  return (
    event.event.startsWith("extraction.") ||
    event.event.startsWith("scoring.") ||
    event.event.startsWith("question_generation.")
  );
}

function llmStageLabel(stage: string) {
  if (stage === "jd_extraction") return "JD 结构化抽取";
  if (stage === "resume_extraction") return "简历结构化抽取";
  if (stage === "resume_quality") return "简历质量分析";
  if (stage === "rubric_generation" || stage === "requirement_matching") return "智能匹配打分";
  if (stage === "question_generation") return "试题生成";
  return "LLM 服务";
}

function warningStage(warning: string) {
  if (warning.includes("JD")) return "jd_extraction";
  if (warning.includes("简历")) return "resume_extraction";
  return "llm";
}

function compactDisplayText(value: string) {
  const text = value.trim();
  if (text.length <= 120) {
    return text;
  }
  return `${text.slice(0, 117)}...`;
}

function SelectedFileChip({ file }: { file: File }) {
  const presentation = fileTypePresentation(file.name);
  const Icon = presentation.icon;
  return (
    <span
      aria-label={`已选择 ${presentation.label} 文件 ${file.name}`}
      className={`file-chip file-chip-${presentation.kind}`}
      title={file.name}
    >
      <span className="file-chip-logo" aria-hidden="true">
        <Icon size={16} />
      </span>
      <span className="file-chip-kind">{presentation.label}</span>
      <span className="file-chip-name">{file.name}</span>
    </span>
  );
}

function fileTypePresentation(fileName: string) {
  const extension = fileName.split(".").pop()?.toLowerCase() ?? "";
  if (extension === "pdf") {
    return { icon: FileArchive, kind: "pdf", label: "PDF" };
  }
  if (extension === "docx" || extension === "doc") {
    return { icon: FileText, kind: "docx", label: extension === "doc" ? "DOC" : "DOCX" };
  }
  if (extension === "txt") {
    return { icon: FileType2, kind: "txt", label: "TXT" };
  }
  return { icon: FileQuestion, kind: "other", label: "FILE" };
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
  view
}: {
  candidate: CandidateReport;
  jdExtractionFacts: ExtractedFact[];
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
          <ExtractionProcess jdFacts={jdExtractionFacts} />
        </section>
      ) : null}

      {view === "matching" ? (
        <>
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
          {!hasQuestionMaterials(report) ? (
            <p className="empty-facts">当前候选人未生成面试题，已跳过面试题展示。</p>
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

function ExtractionProcess({ jdFacts }: { jdFacts?: ExtractedFact[] }) {
  const visibleJdFacts = (jdFacts ?? []).slice(0, 12);
  return (
    <div className="extraction-grid">
      <ExtractionColumn title="JD 核心要求" facts={visibleJdFacts} emptyText="暂无 JD 抽取事实" />
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

function statusClass(status: string) {
  if (status === "强匹配" || status === "直接匹配") return "strong";
  if (status === "相关匹配") return "related";
  if (status === "弱匹配") return "weak";
  return "missing";
}
