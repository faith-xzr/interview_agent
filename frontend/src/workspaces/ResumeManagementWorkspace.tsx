import {
  AlertCircle,
  ArrowUpRight,
  Briefcase,
  CheckCircle2,
  ChevronRight,
  FileStack,
  FileText,
  Loader2,
  Paperclip,
  Search,
  Upload
} from "lucide-react";
import { ChangeEvent, FormEvent, type ReactNode } from "react";

import { List } from "../components/List";
import { PageTitle } from "../components/PageTitle";
import {
  SECTION_LABELS,
  factDisplayLabel,
  formatScore,
  groupResumeFacts,
  visibleDisplayItems,
  type FactGroup
} from "../factDisplay";
import { candidateSummary, hasQuestionMaterials } from "../matchReportDisplay";
import type {
  CandidateProfile,
  CandidateReport,
  DimensionExplanation,
  ExtractedFact,
  RequirementMatch,
  RunReport
} from "../types";
import type { InputMode, ResultView } from "../workspaceTypes";

const DETAIL_VIEWS: Array<{ id: ResultView; label: string }> = [
  { id: "overview", label: "总览" },
  { id: "extraction", label: "结构化提取" },
  { id: "matching", label: "智能匹配打分" },
  { id: "questions", label: "试题生成" }
];

export function ResumeManagementWorkspace({
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
                    <small>
                      {new Date(item.created_at).toLocaleDateString("zh-CN")} · {item.candidates.length} 份简历
                    </small>
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
                view={activeView}
              />
            </div>
          )}
        </section>
      ) : null}
    </div>
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
  hint: string;
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

function statusClass(status: string) {
  if (status === "强匹配" || status === "直接匹配") return "strong";
  if (status === "相关匹配") return "related";
  if (status === "弱匹配") return "weak";
  return "missing";
}
