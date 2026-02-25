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
  salary: string;
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
    score: number;
    breakdown: Record<string, number>;
    missing_keywords: string[];
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
