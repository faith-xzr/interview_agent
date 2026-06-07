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

export interface CandidateReport {
  candidate_id: string;
  source_name: string;
  profile: CandidateProfile;
  match_report: MatchReport;
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
}
