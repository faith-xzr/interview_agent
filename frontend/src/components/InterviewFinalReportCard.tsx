import { consistencyLabel } from "../interviewDisplay";
import type { InterviewFinalReport } from "../types";
import { List } from "./List";

export function InterviewFinalReportCard({ report }: { report: InterviewFinalReport }) {
  const referenceByQuestion = new Map(
    (report.reference_answers ?? []).map((item) => [item.question_index, item])
  );
  const categoryScores = report.category_scores ?? [];
  const questionEvaluations = report.question_evaluations ?? [];

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
      {categoryScores.length ? (
        <div className="interview-category-scores">
          <h5>类别得分</h5>
          <div className="category-score-strip">
            {categoryScores.map((item) => (
              <span key={item.category}>
                {item.category} {item.score} 分 · {item.question_count} 题
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {questionEvaluations.length ? (
        <div className="interview-question-evaluations">
          <h5>逐题评估</h5>
          {questionEvaluations.map((item) => {
            const reference = referenceByQuestion.get(item.question_index);
            return (
              <article className="question-evaluation-item" key={`${item.question_index}-${item.question}`}>
                <div className="question-evaluation-head">
                  <span>Q{item.question_index + 1} · {item.category} · {item.score} 分</span>
                  <strong>{item.question}</strong>
                </div>
                <p>{item.feedback}</p>
                {reference?.reference_answer ? (
                  <div className="reference-answer">
                    <span>参考答案</span>
                    <p>{reference.reference_answer}</p>
                    {reference.key_points.length ? <List items={reference.key_points} /> : null}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
