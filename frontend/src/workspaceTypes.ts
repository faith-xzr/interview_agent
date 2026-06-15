export type ResultView = "overview" | "extraction" | "matching" | "questions";

export type InputMode = "file" | "text";

export interface PendingAnalysisGroup {
  id: string;
  title: string;
  candidateNames: string[];
  createdAt: string;
}
