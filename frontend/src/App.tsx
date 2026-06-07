import { AlertCircle, ArrowUpRight, FileText, Loader2, Paperclip } from "lucide-react";
import { ChangeEvent, FormEvent, useMemo, useState } from "react";

import { createRun } from "./api";
import type {
  CandidateReport,
  DimensionExplanation,
  EvidenceSnippet,
  ExtractedFact,
  RequirementMatch,
  RunReport
} from "./types";
import "./styles.css";

type ResultView = "overview" | "extraction" | "matching" | "questions" | "followups";
type InputMode = "file" | "text";

const RESULT_VIEWS: Array<{ id: ResultView; label: string }> = [
  { id: "overview", label: "总览" },
  { id: "extraction", label: "结构化提取" },
  { id: "matching", label: "智能匹配打分" },
  { id: "questions", label: "试题生成" },
  { id: "followups", label: "追问模拟" }
];

export default function App() {
  const [jdText, setJdText] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [resumeFiles, setResumeFiles] = useState<File[]>([]);
  const [jdInputMode, setJdInputMode] = useState<InputMode>("file");
  const [resumeInputMode, setResumeInputMode] = useState<InputMode>("file");
  const [report, setReport] = useState<RunReport | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<ResultView>("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedCandidate = useMemo(() => {
    if (!report) return null;
    return report.candidates.find((candidate) => candidate.candidate_id === selectedId) ?? report.candidates[0] ?? null;
  }, [report, selectedId]);

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
      setSelectedId(nextReport.candidates[0]?.candidate_id ?? null);
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

  return (
    <div className="page">
      <main className="container">
        <header className="masthead">
          <span className="eyebrow">Recruiting Intelligence</span>
          <h1>智能简历解析与试题生成引擎</h1>
        </header>

        <section className="card form-card">
          <form className="input-form" onSubmit={handleSubmit}>
            <div className="form-grid">
              <FieldGroup
                label="职位描述（JD）"
                hint="选择上传文件或直接粘贴文本，二选一即可"
                mode={jdInputMode}
                onModeChange={setJdInputMode}
                modeId="jd-mode"
              >
                {jdInputMode === "file" ? (
                  <FilePicker
                    id="jd-file"
                    accept=".pdf,.docx,.txt"
                    onChange={(event) => setJdFile(event.target.files?.[0] ?? null)}
                    label="选择 JD 文件"
                    summary={jdFile ? jdFile.name : "未选择文件（支持 .pdf / .docx / .txt）"}
                  />
                ) : (
                  <textarea
                    aria-label="JD 文本兜底"
                    id="jd-text"
                    value={jdText}
                    onChange={(event) => setJdText(event.target.value)}
                    placeholder="粘贴职位描述、职责、技能要求、年限要求……"
                    rows={6}
                  />
                )}
              </FieldGroup>

              <FieldGroup
                label="候选人简历"
                hint="支持一次上传多份；或粘贴单份简历文本"
                mode={resumeInputMode}
                onModeChange={setResumeInputMode}
                modeId="resume-mode"
              >
                {resumeInputMode === "file" ? (
                  <FilePicker
                    id="resume-files"
                    accept=".pdf,.docx,.txt"
                    multiple
                    onChange={handleResumeFiles}
                    label="选择简历文件"
                    summary={
                      resumeFiles.length
                        ? `已选择 ${resumeFiles.length} 份文件`
                        : "未选择文件（支持批量上传）"
                    }
                  />
                ) : (
                  <textarea
                    aria-label="简历文本兜底"
                    id="resume-text"
                    value={resumeText}
                    onChange={(event) => setResumeText(event.target.value)}
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
              <p className="form-footer-hint">
                结构化解析 · 智能匹配 · 自动出题
              </p>
              <button className="primary-button" type="submit" disabled={loading}>
                {loading ? (
                  <Loader2 className="spin" size={16} aria-hidden="true" />
                ) : (
                  <ArrowUpRight size={16} aria-hidden="true" />
                )}
                <span>{loading ? "分析中" : "开始智能筛选"}</span>
              </button>
            </div>
          </form>
        </section>

        <section className="results">
          {report && selectedCandidate ? (
            <div className="card result-card">
              <RunSummary report={report} />
              <ResultNavigation activeView={activeView} onChange={setActiveView} />
              {activeView === "overview" ? (
                <CandidateOverview
                  candidates={report.candidates}
                  selectedId={selectedCandidate.candidate_id}
                  onSelect={setSelectedId}
                />
              ) : (
                <div className="result-grid">
                  <CandidateRanking
                    candidates={report.candidates}
                    selectedId={selectedCandidate.candidate_id}
                    onSelect={setSelectedId}
                  />
                  <CandidateDetail
                    candidate={selectedCandidate}
                    jdExtractionFacts={report.jd_extraction_facts}
                    view={activeView}
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="card empty-state">
              <span className="eyebrow muted">Awaiting input</span>
              <h2>等待提交材料</h2>
              <p>提交 JD 与简历后，这里会呈现候选人匹配分数、推进建议、面试题与追问。</p>
            </div>
          )}
        </section>
      </main>
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
      {RESULT_VIEWS.map((view) => (
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
      <div>
        <span className="muted">必备技能</span>
        <strong>{report.jd_profile.required_skills.join(" · ") || "未识别"}</strong>
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
            <small>{candidate.match_report.match_reasons[0]}</small>
          </span>
          <span className={`decision ${decisionClass(candidate.match_report.decision)}`}>
            {candidate.match_report.decision}
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
          <p>仅呈现推进建议与匹配分数；点击任一行查看完整解析。</p>
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
              <small>{candidate.source_name}</small>
              <span>{candidate.match_report.match_reasons[0]}</span>
            </span>
            <span className={`decision ${decisionClass(candidate.match_report.decision)}`}>
              {candidate.match_report.decision}
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
          <strong>{report.decision}</strong>
        </div>
      </header>

      {view === "extraction" ? (
        <section className="detail-section">
          <h3>抽取过程</h3>
          <ExtractionProcess jdFacts={jdExtractionFacts} resumeFacts={candidate.extraction_facts} />
        </section>
      ) : null}

      {view === "matching" ? (
        <>
          <section className="detail-section">
            <h3>匹配理由</h3>
            <List items={report.match_reasons} />
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
          <ol className="question-list">
            {report.interview_questions.map((item, index) => (
              <li key={`${item.question}-${index}`}>
                <strong>{item.question}</strong>
                <span>{item.focus} · {item.difficulty}</span>
                <p>{item.scoring_criteria}</p>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {view === "followups" ? (
        <section className="detail-section">
          <h3>追问模拟</h3>
          <ol className="question-list compact">
            {report.followup_questions.map((item, index) => (
              <li key={`${item.question}-${index}`}>
                <strong>{item.question}</strong>
                <p>{item.reason}</p>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </article>
  );
}

function ExtractionProcess({ jdFacts, resumeFacts }: { jdFacts?: ExtractedFact[]; resumeFacts?: ExtractedFact[] }) {
  const visibleJdFacts = (jdFacts ?? []).slice(0, 12);
  const groupedResumeFacts = groupResumeFacts(resumeFacts ?? []);
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
        <strong>简历抽取事实</strong>
        <span>{total} 项</span>
      </div>
      {groups.length ? (
        <div className="section-fact-list">
          {groups.map((group) => (
            <FactSection group={group} key={group.section} />
          ))}
        </div>
      ) : (
        <p className="empty-facts">暂无简历抽取事实</p>
      )}
    </div>
  );
}

function FactSection({ group }: { group: FactGroup }) {
  const skillFacts = group.facts.filter((fact) => fact.fact_type === "skill");
  const otherFacts = group.facts.filter((fact) => fact.fact_type !== "skill").slice(0, 4);
  const skillEvidence = skillFacts[0];
  return (
    <section className="fact-section">
      <div className="fact-section-header">
        <h4>{SECTION_LABELS[group.section] ?? group.section}</h4>
        <span>{group.facts.length} 项</span>
      </div>
      {skillFacts.length ? (
        <article className="fact-row compact-skill-row">
          <div className="fact-row-top">
            <span className="fact-type">skill</span>
            <span className="fact-confidence">{Math.round(Math.max(...skillFacts.map((fact) => fact.confidence)) * 100)}%</span>
          </div>
          <div className="skill-chip-list">
            {skillFacts.map((fact) => (
              <span className="skill-chip" key={`${fact.value}-${fact.line_start ?? "line"}`}>
                {fact.value}
              </span>
            ))}
          </div>
          {skillEvidence ? <p>{skillEvidence.evidence}</p> : null}
          {skillEvidence ? <span className="fact-meta">{formatFactMeta(skillEvidence)}</span> : null}
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
        <span className="fact-type">{fact.fact_type}</span>
        <span className="fact-confidence">{Math.round(fact.confidence * 100)}%</span>
      </div>
      <strong>{fact.value}</strong>
      <p>{fact.evidence}</p>
      <span className="fact-meta">{formatFactMeta(fact)}</span>
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
  const evidence = item.evidence[0];
  return (
    <article className="requirement-row">
      <div className="requirement-main">
        <span className="dimension-label">{item.dimension}</span>
        <strong>{item.requirement}</strong>
        <p>{item.reason}</p>
        {evidence ? (
          <blockquote className="inline-evidence">
            <strong>{formatEvidenceMeta(evidence)}</strong>
            <span>{evidence.text}</span>
          </blockquote>
        ) : null}
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

function decisionClass(decision: string) {
  if (decision === "推荐推进") return "go";
  if (decision === "人工复核") return "review";
  return "stop";
}

function statusClass(status: string) {
  if (status === "强匹配" || status === "直接匹配") return "strong";
  if (status === "相关匹配") return "related";
  if (status === "弱匹配") return "weak";
  return "missing";
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

function groupResumeFacts(facts: ExtractedFact[]): FactGroup[] {
  const bySection = new Map<string, ExtractedFact[]>();
  for (const fact of facts) {
    const section = fact.section || "unknown";
    bySection.set(section, [...(bySection.get(section) ?? []), fact]);
  }
  return [...bySection.entries()]
    .map(([section, sectionFacts]) => ({ section, facts: sortFactsWithinSection(sectionFacts).slice(0, 6) }))
    .sort((left, right) => sectionRank(left.section) - sectionRank(right.section));
}

function sortFactsWithinSection(facts: ExtractedFact[]) {
  const rank: Record<string, number> = {
    experience_position: 1,
    project: 1,
    responsibility: 2,
    education: 2,
    degree: 3,
    skill: 4,
    certification: 5,
    metric: 6,
    domain_evidence: 7,
    summary: 8
  };
  return [...facts].sort((left, right) => (rank[left.fact_type] ?? 99) - (rank[right.fact_type] ?? 99));
}

function sectionRank(section: string) {
  const index = SECTION_ORDER.indexOf(section);
  return index === -1 ? 99 : index;
}

function formatScore(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function formatEvidenceMeta(evidence: EvidenceSnippet) {
  const line = evidence.line_start ? `第 ${evidence.line_start} 行` : "原文证据";
  return `${evidence.source} · ${line}`;
}

function formatFactMeta(fact: ExtractedFact) {
  const line = fact.line_start ? `第 ${fact.line_start} 行` : "无行号";
  return `${fact.section} · ${line} · ${fact.extractor}`;
}
