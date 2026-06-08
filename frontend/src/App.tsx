import { AlertCircle, ArrowUpRight, FileText, Loader2, Paperclip } from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

import { createRun, generateAnswerFollowup } from "./api";
import type {
  CandidateReport,
  DimensionExplanation,
  ExtractedFact,
  InterviewAnswerFollowUp,
  MatchReport,
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
const QUESTION_MATERIAL_MIN_SCORE = 40;

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
                    runId={report.run_id}
                    view={activeView}
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="card empty-state">
              <span className="eyebrow muted">Awaiting input</span>
              <h2>等待提交材料</h2>
              <p>提交 JD 与简历后，这里会呈现候选人匹配分数、关键依据、面试题与追问。</p>
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
          <ExtractionProcess jdFacts={jdExtractionFacts} resumeFacts={candidate.extraction_facts} />
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

      {view === "followups" ? (
        <section className="detail-section">
          <h3>追问模拟</h3>
          {shouldSkipQuestionMaterials(report) ? (
            <p className="empty-facts">匹配分低于 40，已跳过追问生成。</p>
          ) : (
            <FollowupSimulator candidate={candidate} runId={runId} />
          )}
        </section>
      ) : null}
    </article>
  );
}

function FollowupSimulator({ candidate, runId }: { candidate: CandidateReport; runId: string }) {
  const questions = candidate.match_report.interview_questions;
  const [questionIndex, setQuestionIndex] = useState(0);
  const [candidateAnswer, setCandidateAnswer] = useState("");
  const [result, setResult] = useState<InterviewAnswerFollowUp | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedQuestion = questions[questionIndex] ?? questions[0] ?? null;
  const questionSelectId = `followup-question-${candidate.candidate_id}`;
  const answerId = `candidate-answer-${candidate.candidate_id}`;

  useEffect(() => {
    setQuestionIndex(0);
    setCandidateAnswer("");
    setResult(null);
    setError(null);
  }, [candidate.candidate_id, runId]);

  async function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!candidateAnswer.trim()) {
      setError("候选人回答不能为空。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const nextResult = await generateAnswerFollowup({
        runId,
        candidateId: candidate.candidate_id,
        questionIndex,
        candidateAnswer
      });
      setResult(nextResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "追问生成失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="followup-panel">
      <form className="followup-form" onSubmit={handleGenerate}>
        <div className="followup-control">
          <label htmlFor={questionSelectId}>选择面试题</label>
          <select
            id={questionSelectId}
            value={questionIndex}
            onChange={(event) => {
              setQuestionIndex(Number(event.target.value));
              setResult(null);
              setError(null);
            }}
          >
            {questions.map((item, index) => (
              <option key={`${item.question}-${index}`} value={index}>
                {`第 ${index + 1} 题：${item.focus}`}
              </option>
            ))}
          </select>
        </div>
        {selectedQuestion ? (
          <div className="selected-question">
            <strong>{selectedQuestion.question}</strong>
            <span>{selectedQuestion.focus}</span>
          </div>
        ) : null}
        <div className="followup-control">
          <label htmlFor={answerId}>候选人回答</label>
          <textarea
            aria-label="候选人回答"
            id={answerId}
            value={candidateAnswer}
            onChange={(event) => setCandidateAnswer(event.target.value)}
            placeholder="粘贴或输入候选人对这道题的回答"
            rows={5}
          />
        </div>
        {error ? (
          <div className="error-box" role="alert">
            <AlertCircle size={18} aria-hidden="true" />
            <span>{error}</span>
          </div>
        ) : null}
        <button className="secondary-button" type="submit" disabled={loading}>
          {loading ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <ArrowUpRight size={16} aria-hidden="true" />}
          <span>{loading ? "生成中" : "生成追问"}</span>
        </button>
      </form>

      {result ? (
        <section className="followup-result">
          <h4>回答诊断</h4>
          <div className="score-pills">
            <span>清晰度 {result.clarity_score}</span>
            <span>深度 {result.depth_score}</span>
            <span>{consistencyLabel(result.evidence_consistency)}</span>
          </div>
          <p>{result.answer_summary}</p>
          {result.issues.length ? <List items={result.issues} /> : null}
          <div className="followup-question-card">
            <span>动态追问</span>
            <strong>{result.followup_question}</strong>
            <p>{result.reason}</p>
            <small>{result.expected_signal}</small>
          </div>
        </section>
      ) : null}

      {candidate.match_report.followup_questions.length ? (
        <section className="followup-static">
          <h4>预面试待确认</h4>
          <ol className="question-list compact">
            {candidate.match_report.followup_questions.map((item, index) => (
              <li key={`${item.question}-${index}`}>
                <strong>{item.question}</strong>
                <p>{item.reason}</p>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
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

function groupResumeFacts(facts: ExtractedFact[]): FactGroup[] {
  const bySection = new Map<string, ExtractedFact[]>();
  for (const fact of facts.filter(isVisibleResumeFact)) {
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
      (fact) => fact.fact_type === "work_summary" || fact.fact_type === "responsibility" || fact.fact_type === "metric"
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
  return fact.section !== "basic" && !HIDDEN_RESUME_FACT_TYPES.has(fact.fact_type);
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
  for (const fact of facts) {
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
      current = mergeFacts(current, fact, isProjectTitleLike(current.value) ? "colon" : "plain");
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
  const value = mode === "colon"
    ? `${previousText}：${currentText}`
    : `${previousText}${currentText}`;
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
  const phrases: string[] = [];
  for (const fact of skillFacts) {
    for (const phrase of splitSkillPhrase(fact.value)) {
      if (!phrase) continue;
      if (isParentheticalOnly(phrase) && phrases.length) {
        phrases[phrases.length - 1] = `${phrases[phrases.length - 1]}${phrase}`;
        continue;
      }
      phrases.push(phrase);
    }
  }
  return removeRedundantPhrases(phrases).map((value, index) => ({
    ...base,
    value,
    line_start: skillFacts[index]?.line_start ?? base.line_start,
    line_end: skillFacts[index]?.line_end ?? base.line_end
  }));
}

function splitSkillPhrase(value: string) {
  return value
    .split(/\s*[；;]\s*/)
    .map(cleanSkillText)
    .filter((item) => item.length >= 2 && !["熟悉", "熟练", "精通", "掌握"].includes(item));
}

function cleanSkillText(value: string) {
  return cleanFactText(value)
    .replace(/^(熟练掌握|熟练运用|熟悉掌握|精通|熟悉|掌握|了解|具备)\s*/u, "")
    .replace(/^极强的/u, "")
    .replace(/AIGC\s*工作流/giu, "AIGC 工作流")
    .replace(/TikTok\s*平台/giu, "TikTok平台");
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
  return /^(至|到|与|及|和|并|成本|爆款|日均|获|获得|提升|降低|缩短|节省)/u.test(value);
}

function isMetricLikeFragment(value: string) {
  return value.length <= 16 && /\d/.test(value) && /(条|个|人|元|%|小时|天|万|次|名|场)/u.test(value);
}

function endsLikeUnfinishedPhrase(value: string) {
  return /(累计产出|从\d+(?:\.\d+)?[天小时分钟]*缩短|节省设计|提升|降低|缩短|产出|完成|利用|使用|负责|拥有|逻辑)$/u.test(value);
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
  return value.replace(/\s+/g, " ").trim();
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
