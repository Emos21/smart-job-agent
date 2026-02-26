export interface Job {
  id: number;
  title: string;
  company: string;
  location: string;
  url: string;
  source: string;
  tags: string;
  salary_min: number | null;
  salary_max: number | null;
  saved_at: string;
  notes: string;
}

export interface SearchJob {
  title: string;
  company: string;
  location: string;
  url: string;
  source: string;
  tags: string[];
  salary_min?: number | null;
  salary_max?: number | null;
}

export interface Application {
  id: number;
  job_id: number;
  status: string;
  title: string;
  company: string;
  jd_text: string;
  updated_at: string;
  notes: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface AnalysisResult {
  jd_analysis: Record<string, unknown>;
  resume_analysis: Record<string, unknown>;
  ats_score: {
    success: boolean;
    overall_score: number;
    grade: string;
    keyword_analysis: {
      found_keywords: string[];
      missing_keywords: string[];
      keyword_match_rate: number;
    };
    section_analysis: {
      found_sections: string[];
      missing_sections: string[];
      section_completeness: number;
    };
    formatting_analysis: {
      formatting_score: number;
      issues: string[];
      has_email: boolean;
      has_phone: boolean;
      word_count: number;
      action_verbs_found: string[];
      has_metrics: boolean;
    };
    suggestions: string[];
  };
}

export interface PipelineResult {
  analysis: Record<string, unknown>;
  materials: Record<string, unknown>;
  interview_prep: Record<string, unknown>;
}

export interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: number;
  email: string;
  name: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}
