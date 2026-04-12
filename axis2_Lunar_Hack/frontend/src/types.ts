export type Language = "en" | "fr" | "ar";

export interface StructuredOutput {
  business_type: string;
  need: string;
  recommended_strategy: string;
  estimated_impact: string;
  cta: string;
  lead_score: number;
  concern_area?: string;
  urgency?: string;
  priority_actions?: string[];
  missing_fields: string[];
}

export interface DecisionOption {
  title: string;
  summary: string;
  tradeoff: string;
}

export interface DecisionSupportProfile {
  business_type?: string | null;
  budget?: string | null;
  goals?: string | null;
  timeline?: string | null;
  intent?: string | null;
  domain?: string | null;
  concern_area?: string | null;
  urgency?: string | null;
  constraints?: string | null;
  kpis?: string | null;
  decision_options?: DecisionOption[];
  priority_actions?: string[];
  risks?: string[];
  immediate_actions?: string[];
  lead_score?: number;
}

export interface DecisionBrief {
  concernArea: string;
  urgency: string;
  constraints: string;
  kpis: string;
  decisionOptions: DecisionOption[];
  priorityActions: string[];
  risks: string[];
  immediateActions: string[];
}

export interface ChatApiRequest {
  user_id: string;
  session_id: string;
  message: string;
  language: Language;
  metadata?: Record<string, unknown>;
}

export interface ChatApiResponse {
  response: string;
  language: Language;
  structured: StructuredOutput;
  user_profile: DecisionSupportProfile;
  rag_sources: string[];
  follow_up_email: string;
  next_question?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: number;
  structured?: StructuredOutput;
  decision?: DecisionBrief;
  rag_sources?: string[];
  follow_up_email?: string;
}

export interface ChatSessionSummary {
  session_id: string;
  last_message: string;
  last_role: string;
  last_created_at: string;
  message_count: number;
}

export interface SessionHistoryMessage {
  role: "user" | "assistant";
  message: string;
  created_at: string;
}
