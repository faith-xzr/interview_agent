export interface JDProfile {
  job_title: string;
  responsibilities: string[];
  required_skills: string[];
  nice_to_have_skills: string[];
  seniority: string;
  years_required: number;
  industry_background: string[];
  hard_requirements: string[];
}

export interface SkillRouteResult {
  position_name: string;
  skill_id: string;
  skill_name: string;
  route_result: string;
  confidence: number;
  reason: string;
  source: string;
}

export interface CandidateProfile {
  name: string;
  target_role?: string | null;
  contacts: Record<string, string>;
  location?: string | null;
  education: string[];
  work_experiences: string[];
  projects: string[];
  skills: string[];
  certifications: string[];
  highlights: string[];
  risk_points: string[];
  ambiguous_points: string[];
}

export interface ExtractedFact {
  fact_type: string;
  value: string;
  normalized_value?: string | null;
  evidence: string;
  section: string;
  line_start?: number | null;
  line_end?: number | null;
  confidence: number;
  extractor: string;
}

export interface ScoreBreakdown {
  skill_score: number;
  experience_score: number;
  project_score: number;
  industry_score: number;
  education_score: number;
  risk_deduction: number;
}

export interface EvidenceSnippet {
  source: string;
  text: string;
  section?: string | null;
  line_start?: number | null;
  line_end?: number | null;
  fact_type?: string | null;
}

export interface RequirementMatch {
  dimension: string;
  requirement: string;
  requirement_type: string;
  status: string;
  max_score: number;
  contribution: number;
  confidence: number;
  reason: string;
  evidence: EvidenceSnippet[];
}

export interface DimensionExplanation {
  dimension: string;
  score: number;
  max_score: number;
  summary: string;
}

export interface InterviewQuestion {
  question: string;
  focus: string;
  scoring_criteria: string;
}

export interface FollowUpQuestion {
  question: string;
  reason: string;
  related_evidence?: string | null;
}

export interface InterviewAnswerFollowUp {
  question_index: number;
  original_question: string;
  candidate_answer: string;
  answer_summary: string;
  clarity_score: number;
  depth_score: number;
  evidence_consistency: string;
  issues: string[];
  followup_needed: boolean;
  followup_question: string;
  reason: string;
  expected_signal: string;
  source: string;
}

export interface InterviewTurnInputMetadata {
  source: "text" | "speech";
  transcript?: string | null;
  confidence?: number | null;
  locale?: string | null;
  finalized?: boolean;
  raw_text?: string | null;
}

export interface InterviewSessionQuestion {
  question: string;
  focus: string;
  scoring_criteria: string;
  source: string;
  question_index: number;
  skill_id?: string | null;
  stage?: string | null;
}

export interface InterviewTurn {
  turn_index: number;
  question: InterviewSessionQuestion;
  answer: string;
  answer_source?: string | null;
  answer_metadata?: InterviewTurnInputMetadata | null;
  diagnosis: InterviewAnswerFollowUp;
  created_at: string;
}

export interface InterviewFinalReport {
  overall_score: number;
  clarity_score: number;
  depth_score: number;
  evidence_consistency: string;
  recommendation: string;
  strengths: string[];
  risks: string[];
  summary: string;
  next_steps: string[];
  category_scores?: InterviewCategoryScore[];
  question_evaluations?: InterviewQuestionEvaluation[];
  reference_answers?: InterviewReferenceAnswer[];
}

export interface InterviewCategoryScore {
  category: string;
  score: number;
  question_count: number;
}

export interface InterviewQuestionEvaluation {
  question_index: number;
  question: string;
  category: string;
  user_answer: string;
  score: number;
  feedback: string;
}

export interface InterviewReferenceAnswer {
  question_index: number;
  question: string;
  reference_answer: string;
  key_points: string[];
}

export interface InterviewSession {
  session_id: string;
  run_id: string;
  candidate_id: string;
  mode: string;
  direction: string;
  difficulty: string;
  interviewer_style: string;
  skill_id?: string | null;
  skill_name?: string | null;
  flow: string[];
  status: string;
  created_at: string;
  updated_at: string;
  current_question?: InterviewSessionQuestion | null;
  turns: InterviewTurn[];
  final_report?: InterviewFinalReport | null;
}

export interface VoiceAsrSettings {
  model: string;
  sample_rate: number;
  input_audio_format: string;
  language: string;
  server_vad: boolean;
  silence_duration_ms: number;
}

export interface VoiceTtsSettings {
  model: string;
  voice: string;
  response_format: string;
  sample_rate: number;
}

export interface VoiceSettingsResponse {
  provider_id: string;
  api_key_configured: boolean;
  api_key_source: "env" | "saved" | "none" | string;
  asr: VoiceAsrSettings;
  tts: VoiceTtsSettings;
}

export interface VoiceInterviewSession {
  voice_session_id: string;
  interview_session_id: string;
  status: string;
  websocket_url: string;
  created_at: string;
  updated_at: string;
}

export type VoiceSocketMessage =
  | { type: "control"; action: string; message?: string }
  | { type: "subtitle"; text: string; isFinal: boolean }
  | { type: "interview_session"; session: InterviewSession }
  | { type: "audio_chunk"; data: string; index: number; isLast: boolean }
  | { type: "error"; message: string };

export interface ModelProvider {
  id: string;
  name: string;
  model: string;
  base_url: string;
  api_key_configured: boolean;
  api_key_source?: "env" | "saved" | "none" | string;
  is_default: boolean;
}

export interface ModelProviderSettingsResponse {
  default_provider_id: string;
  providers: ModelProvider[];
}

export interface AuditEvent {
  event: string;
  stage: string;
  failure_code: string;
  message: string;
  fallback_strategy: string;
  run_id?: string | null;
  candidate_id?: string | null;
  model?: string | null;
  prompt_version?: string | null;
  invalid_requirements: string[];
  details: Record<string, unknown>;
}

export interface ToolCallRecord {
  call_id: string;
  tool_name: string;
  stage: string;
  status: string;
  run_id?: string | null;
  candidate_id?: string | null;
  input_summary: string;
  output_summary: string;
  error_message?: string | null;
  started_at: string;
  completed_at: string;
  duration_ms: number;
  metadata: Record<string, unknown>;
}

export interface MatchReport {
  total_score: number;
  decision: string;
  dimension_scores: Record<string, number>;
  score_breakdown: ScoreBreakdown;
  match_reasons: string[];
  gap_reasons: string[];
  evidence_snippets: EvidenceSnippet[];
  requirement_matches: RequirementMatch[];
  dimension_explanations: DimensionExplanation[];
  interview_questions: InterviewQuestion[];
  followup_questions: FollowUpQuestion[];
}

export interface ResumeQualitySuggestion {
  category: string;
  priority: string;
  issue: string;
  recommendation: string;
}

export interface ResumeQualityScoreDetail {
  project_score: number;
  skill_match_score: number;
  content_score: number;
  structure_score: number;
  expression_score: number;
}

export interface ResumeQualityReport {
  overall_score: number;
  score_detail: ResumeQualityScoreDetail;
  summary: string;
  strengths: string[];
  suggestions: ResumeQualitySuggestion[];
}

export interface CandidateSourceFile {
  filename: string;
  content_type?: string | null;
}

export interface CandidateReport {
  candidate_id: string;
  source_name: string;
  source_file?: CandidateSourceFile | null;
  profile: CandidateProfile;
  match_report: MatchReport;
  resume_quality?: ResumeQualityReport;
  parse_warnings: string[];
  extraction_facts: ExtractedFact[];
}

export interface RunReport {
  run_id: string;
  created_at: string;
  jd_profile: JDProfile;
  jd_extraction_facts: ExtractedFact[];
  candidates: CandidateReport[];
  warnings: string[];
  audit_events?: AuditEvent[];
  tool_calls?: ToolCallRecord[];
}

export type ResumeAnalyzeStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface ResumeListItem {
  id: number;
  filename: string;
  file_size: number;
  uploaded_at: string;
  access_count: number;
  latest_score?: number | null;
  last_analyzed_at?: string | null;
  analyze_status: ResumeAnalyzeStatus;
  analyze_error?: string | null;
}

export interface ResumeAnalysisHistoryItem {
  analysis_id: number;
  created_at: string;
  overall_score: number;
  score_detail: ResumeQualityScoreDetail;
  summary: string;
  strengths: string[];
  suggestions: ResumeQualitySuggestion[];
  original_text?: string | null;
}

export interface ResumeDetailResponse {
  id: number;
  filename: string;
  file_size: number;
  content_type?: string | null;
  uploaded_at: string;
  access_count: number;
  analyze_status: ResumeAnalyzeStatus;
  analyze_error?: string | null;
  resume_text: string;
  analyses: ResumeAnalysisHistoryItem[];
}

export interface ResumeUploadResponse {
  resume: {
    id: number;
    filename: string;
    analyze_status: ResumeAnalyzeStatus;
  } | null;
  analysis: ResumeQualityReport | null;
  storage: {
    file_key: string;
    file_url: string;
    resume_id: number;
  };
  duplicate?: boolean;
}
