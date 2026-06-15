import { AlertCircle, ArrowUpRight, Bot, Trash2, Users } from "lucide-react";

import { InterviewFinalReportCard } from "../components/InterviewFinalReportCard";
import { PageTitle } from "../components/PageTitle";
import { sessionStatusLabel } from "../interviewDisplay";
import type { InterviewSession, RunReport } from "../types";

export function InterviewRecordsWorkspace({
  error,
  sessions,
  runs,
  onDeleteSession,
  onResumeSession
}: {
  error: string | null;
  sessions: InterviewSession[];
  runs: RunReport[];
  onDeleteSession: (id: string) => void;
  onResumeSession: (session: InterviewSession) => void;
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
            const candidateName = candidate?.profile.name ?? "未知候选人";
            const jobTitle = run?.jd_profile.job_title ?? "未知岗位";
            const canResume = !session.final_report;
            const recordContent = (
              <>
                <div className="record-main">
                  <span className="document-icon"><Bot size={20} aria-hidden="true" /></span>
                  <div>
                    <h2>{candidateName}</h2>
                    <p>{jobTitle} · {session.turns.length} 轮问答</p>
                  </div>
                </div>
                <div className="record-score">
                  <span>{session.final_report ? `总分 ${session.final_report.overall_score}` : sessionStatusLabel(session.status)}</span>
                  <strong>{session.final_report?.recommendation ?? "待生成最终报告"}</strong>
                  {canResume ? (
                    <small className="record-resume-hint">
                      <ArrowUpRight size={14} aria-hidden="true" />
                      <span>继续面试</span>
                    </small>
                  ) : null}
                </div>
              </>
            );
            return (
              <article className={canResume ? "record-card card resumable" : "record-card card"} key={session.session_id}>
                {canResume ? (
                  <div
                    aria-label={`继续面试 ${candidateName} - ${jobTitle}`}
                    className="record-content-button"
                    onClick={() => onResumeSession(session)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onResumeSession(session);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                  >
                    {recordContent}
                  </div>
                ) : (
                  <div className="record-content">{recordContent}</div>
                )}
                <button className="icon-button" type="button" onClick={() => onDeleteSession(session.session_id)} aria-label="删除面试记录">
                  <Trash2 size={18} aria-hidden="true" />
                </button>
                {session.final_report ? (
                  <div className="record-report">
                    <InterviewFinalReportCard report={session.final_report} />
                  </div>
                ) : null}
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
