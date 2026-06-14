import type { InterviewAnswerFollowUp, InterviewSession, ModelProviderSettingsResponse, RunReport } from "./types";

export interface RunInput {
  jdText: string;
  resumeText: string;
  jdFile?: File | null;
  resumeFiles: File[];
}

export async function createRun(input: RunInput): Promise<RunReport> {
  const body = new FormData();
  if (input.jdText.trim()) {
    body.append("jd_text", input.jdText.trim());
  }
  if (input.resumeText.trim()) {
    body.append("resume_texts", input.resumeText.trim());
  }
  if (input.jdFile) {
    body.append("jd_file", input.jdFile);
  }
  input.resumeFiles.forEach((file) => body.append("resume_files", file));

  const response = await fetch("/api/runs", {
    method: "POST",
    body
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "请求失败，请检查输入后重试。" }));
    throw new Error(error.detail || "请求失败，请检查输入后重试。");
  }
  return response.json();
}

export async function listRuns(): Promise<RunReport[]> {
  const response = await fetch("/api/runs");
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "运行记录加载失败。" }));
    throw new Error(error.detail || "运行记录加载失败。");
  }
  const payload = await response.json();
  if (!Array.isArray(payload)) {
    throw new Error("运行记录加载失败。");
  }
  return payload;
}

export interface AnswerFollowUpInput {
  runId: string;
  candidateId: string;
  questionIndex: number;
  candidateAnswer: string;
}

export async function generateAnswerFollowup(input: AnswerFollowUpInput): Promise<InterviewAnswerFollowUp> {
  const response = await fetch(`/api/runs/${encodeURIComponent(input.runId)}/answer-followup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      candidate_id: input.candidateId,
      question_index: input.questionIndex,
      candidate_answer: input.candidateAnswer
    })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "追问生成失败，请稍后重试。" }));
    throw new Error(error.detail || "追问生成失败，请稍后重试。");
  }
  return response.json();
}

export interface StartInterviewInput {
  runId: string;
  candidateId: string;
  mode?: string;
}

export async function startInterview(input: StartInterviewInput): Promise<InterviewSession> {
  const response = await fetch(`/api/runs/${encodeURIComponent(input.runId)}/interviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      candidate_id: input.candidateId,
      mode: input.mode ?? "structured"
    })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "AI 面试会话创建失败，请稍后重试。" }));
    throw new Error(error.detail || "AI 面试会话创建失败，请稍后重试。");
  }
  return response.json();
}

export async function listInterviewSessions(): Promise<InterviewSession[]> {
  const response = await fetch("/api/interviews");
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "面试记录加载失败。" }));
    throw new Error(error.detail || "面试记录加载失败。");
  }
  const payload = await response.json();
  if (!Array.isArray(payload)) {
    throw new Error("面试记录加载失败。");
  }
  return payload;
}

export async function deleteInterviewSession(sessionId: string): Promise<void> {
  const response = await fetch(`/api/interviews/${encodeURIComponent(sessionId)}`, {
    method: "DELETE"
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "面试记录删除失败。" }));
    throw new Error(error.detail || "面试记录删除失败。");
  }
}

export interface SubmitInterviewTurnInput {
  sessionId: string;
  candidateAnswer: string;
}

export async function submitInterviewTurn(input: SubmitInterviewTurnInput): Promise<InterviewSession> {
  const response = await fetch(`/api/interviews/${encodeURIComponent(input.sessionId)}/turns`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      candidate_answer: input.candidateAnswer
    })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "回答提交失败，请稍后重试。" }));
    throw new Error(error.detail || "回答提交失败，请稍后重试。");
  }
  return response.json();
}

export async function finalizeInterview(sessionId: string): Promise<InterviewSession> {
  const response = await fetch(`/api/interviews/${encodeURIComponent(sessionId)}/final-report`, {
    method: "POST"
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "最终报告生成失败，请稍后重试。" }));
    throw new Error(error.detail || "最终报告生成失败，请稍后重试。");
  }
  return response.json();
}

export async function getModelProviders(): Promise<ModelProviderSettingsResponse> {
  const response = await fetch("/api/settings/model-providers");
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "模型服务配置加载失败。" }));
    throw new Error(error.detail || "模型服务配置加载失败。");
  }
  return response.json();
}

export async function updateDefaultModelProvider(providerId: string): Promise<ModelProviderSettingsResponse> {
  const response = await fetch("/api/settings/model-providers/default", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider_id: providerId })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "默认模型服务切换失败。" }));
    throw new Error(error.detail || "默认模型服务切换失败。");
  }
  return response.json();
}

export async function updateModelProviderApiKey(
  providerId: string,
  apiKey: string
): Promise<ModelProviderSettingsResponse> {
  const response = await fetch(`/api/settings/model-providers/${encodeURIComponent(providerId)}/api-key`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "API Key 保存失败。" }));
    throw new Error(error.detail || "API Key 保存失败。");
  }
  return response.json();
}
