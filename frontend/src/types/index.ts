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

export interface UserProfile {
  user_id: number;
  target_role: string;
  experience_level: string;
  skills: string[];
  bio: string;
  linkedin_url: string;
  github_username: string;
  location: string;
}

export interface UserResume {
  id: number;
  user_id: number;
  name: string;
  is_default: number;
  char_count: number;
  created_at: string;
  updated_at: string;
}

export interface AgentActivity {
  agent: string;
  status: "running" | "complete" | "failed";
  message: string;
}

export interface RoutingInfo {
  intent: string;
  agents: string[];
}

export interface Goal {
  id: number;
  user_id: number;
  title: string;
  description: string;
  status: "active" | "paused" | "completed" | "abandoned";
  created_at: string;
  updated_at: string;
}

export interface GoalStep {
  id: number;
  goal_id: number;
  step_number: number;
  title: string;
  description: string;
  agent_name: string;
  status: "pending" | "in_progress" | "completed" | "skipped" | "failed";
  output: string;
  trace_id: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface Suggestion {
  id: string;
  message: string;
  action: string;
  priority: number;
}

export interface EvaluatorEvent {
  decision: "continue" | "loop_back" | "skip_next" | "stop" | "add_agent";
  reason: string;
  target_agent: string;
}

export interface AgentReasoningEvent {
  agent: string;
  thought: string;
  tool: string;
}

export interface GoalStepEvent {
  step_number: number;
  title: string;
  agent: string;
  status: string;
  output_preview?: string;
}

export interface GoalReplanEvent {
  adjustment: string;
  reason: string;
}

export interface Notification {
  id: number;
  user_id: number;
  type: string;
  title: string;
  message: string;
  data: string;
  read: number;
  created_at: string;
}

export interface TraceIdsEvent {
  ids: number[];
}
