import type {
  InterviewAnswerFollowUp,
  InterviewSession,
  InterviewTurnInputMetadata,
  ModelProviderSettingsResponse,
  RunReport,
  SkillRouteResult,
  VoiceInterviewSession,
  VoiceSettingsResponse,
  VoiceSocketMessage
} from "./types";

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

export async function deleteRunCandidate(runId: string, candidateId: string): Promise<void> {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(candidateId)}`, {
    method: "DELETE"
  });
  if (!response.ok && response.status !== 204) {
    const error = await response.json().catch(() => ({ detail: "删除失败，请稍后重试。" }));
    throw new Error(error.detail || "删除失败，请稍后重试。");
  }
}

export async function deleteAllRuns(): Promise<void> {
  const response = await fetch("/api/runs", { method: "DELETE" });
  if (!response.ok && response.status !== 204) {
    const error = await response.json().catch(() => ({ detail: "全部历史上传删除失败，请稍后重试。" }));
    throw new Error(error.detail || "全部历史上传删除失败，请稍后重试。");
  }
}

export async function getSkillRoute(runId: string): Promise<SkillRouteResult> {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}/skill-route`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "JD skill 路由失败。" }));
    throw new Error(error.detail || "JD skill 路由失败。");
  }
  return response.json();
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
  skillId?: string;
}

export async function startInterview(input: StartInterviewInput): Promise<InterviewSession> {
  const response = await fetch(`/api/runs/${encodeURIComponent(input.runId)}/interviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      candidate_id: input.candidateId,
      mode: input.mode ?? "structured",
      skill_id: input.skillId
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
  answerMetadata?: InterviewTurnInputMetadata;
}

export async function submitInterviewTurn(input: SubmitInterviewTurnInput): Promise<InterviewSession> {
  const response = await fetch(`/api/interviews/${encodeURIComponent(input.sessionId)}/turns`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      candidate_answer: input.candidateAnswer,
      answer_metadata: input.answerMetadata
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

export async function getVoiceSettings(): Promise<VoiceSettingsResponse> {
  const response = await fetch("/api/settings/voice");
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "语音服务配置加载失败。" }));
    throw new Error(error.detail || "语音服务配置加载失败。");
  }
  return response.json();
}

export async function createVoiceInterviewSession(interviewSessionId: string): Promise<VoiceInterviewSession> {
  const response = await fetch("/api/voice-interviews", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ interview_session_id: interviewSessionId })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "语音面试会话创建失败。" }));
    throw new Error(error.detail || "语音面试会话创建失败。");
  }
  return response.json();
}

export interface VoiceWebSocketHandlers {
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (message: string) => void;
  onControl?: (action: string, message?: string) => void;
  onSubtitle?: (text: string, isFinal: boolean) => void;
  onInterviewSession?: (session: InterviewSession) => void;
  onAudioChunk?: (data: string, index: number, isLast: boolean) => void;
}

export class VoiceInterviewWebSocket {
  private socket: WebSocket | null = null;

  constructor(private url: string, private handlers: VoiceWebSocketHandlers) {}

  connect() {
    this.socket = new WebSocket(resolveVoiceWebSocketUrl(this.url));
    this.socket.onopen = () => this.handlers.onOpen?.();
    this.socket.onclose = () => this.handlers.onClose?.();
    this.socket.onerror = () => this.handlers.onError?.("云端语音连接异常。");
    this.socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as VoiceSocketMessage;
        switch (message.type) {
          case "control":
            this.handlers.onControl?.(message.action, message.message);
            break;
          case "subtitle":
            this.handlers.onSubtitle?.(message.text, message.isFinal);
            break;
          case "interview_session":
            this.handlers.onInterviewSession?.(message.session);
            break;
          case "audio_chunk":
            this.handlers.onAudioChunk?.(message.data, message.index, message.isLast);
            break;
          case "error":
            this.handlers.onError?.(message.message);
            break;
          default:
            break;
        }
      } catch {
        this.handlers.onError?.("语音消息解析失败。");
      }
    };
  }

  sendAudio(audioData: string): boolean {
    return this.send({ type: "audio", data: audioData });
  }

  submitText(text: string): boolean {
    return this.send({ type: "control", action: "submit_text", text });
  }

  speakCurrentQuestion(): boolean {
    return this.send({ type: "control", action: "speak_current_question" });
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  isConnected() {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  private send(payload: Record<string, unknown>) {
    if (!this.isConnected() || !this.socket) {
      return false;
    }
    this.socket.send(JSON.stringify(payload));
    return true;
  }
}

export function connectVoiceInterviewWebSocket(url: string, handlers: VoiceWebSocketHandlers): VoiceInterviewWebSocket {
  const socket = new VoiceInterviewWebSocket(url, handlers);
  socket.connect();
  return socket;
}

export function resolveVoiceWebSocketUrl(url: string): string {
  if (url.startsWith("ws://") || url.startsWith("wss://")) {
    return url;
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.port === "5173"
    ? `${window.location.hostname}:8000`
    : window.location.host;
  const path = url.startsWith("/") ? url : `/${url}`;
  return `${protocol}//${host}${path}`;
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
