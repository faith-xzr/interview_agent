import type { RunReport } from "./types";

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

