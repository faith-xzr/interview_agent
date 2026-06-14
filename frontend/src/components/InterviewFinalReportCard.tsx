import { consistencyLabel } from "../interviewDisplay";
import type { InterviewFinalReport } from "../types";
import { List } from "./List";

export function InterviewFinalReportCard({ report }: { report: InterviewFinalReport }) {
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
