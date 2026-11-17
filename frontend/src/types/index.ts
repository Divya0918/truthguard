// Shared TypeScript types aligned with the backend API

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'admin' | 'customer';
  is_active: boolean;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAdmin: boolean;
}

// ─── Documents ──────────────────────────────────────────
export type DocStatus = 'pending' | 'processing' | 'published' | 'rejected';

export interface Document {
  id: string;
  title: string;
  description: string | null;
  original_filename: string;
  file_type: string;
  status: DocStatus;
  version_label: string | null;
  effective_date: string | null;
  chunk_count: number;
  processing_error: string | null;
  created_at: string;
  published_at: string | null;
  supersedes_id: string | null;
  is_priority?: boolean;
}

export interface ChunkDetail {
  chunk_index: number;
  content: string;
  section_title: string | null;
  word_count: number;
}

export interface DocumentDetail extends Document {
  file_size_bytes: number | null;
  content?: string | null;
  chunks?: ChunkDetail[];
  chunks_preview: { index: number; excerpt: string; section: string | null }[];
}

// ─── Chat ─────────────────────────────────────────────────
export type AnswerStatus = 'approved' | 'abstained' | 'error';

export interface Citation {
  chunk_id: string;
  document_title: string;
  excerpt: string;
  effective_date: string | null;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  answer_status: AnswerStatus;
  citations: Citation[];
  critic_decision: string | null;
  critic_reason: string | null;
  resolution_task_id: string | null;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  answer_status: AnswerStatus | null;
  created_at: string;
  citations: Citation[];
}

export interface ConversationDetail {
  id: string;
  title: string | null;
  created_at: string;
  messages: Message[];
}

// ─── Admin: Chat History ──────────────────────────────────
export interface AdminCitation extends Citation {
  relevance_score: number;
}

export interface AdminMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  answer_status: AnswerStatus | null;
  retry_count: number;
  created_at: string;
  citations: AdminCitation[];
  agent_trace: Record<string, unknown> | null;
}

export interface ConvAdminSummary {
  id: string;
  title: string | null;
  user_id: string;
  user_email: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  has_abstention: boolean;
}

export interface ConvAdminDetail {
  id: string;
  title: string | null;
  user_id: string;
  created_at: string;
  messages: AdminMessage[];
}

// ─── Resolution ────────────────────────────────────────────
export type TaskStatus = 'open' | 'in_review' | 'resolved';
export type ClarificationStatus = 'draft' | 'approved' | 'published';

export interface EvidenceItem {
  chunk_id: string | null;
  document_title: string;
  excerpt: string;
}

export interface ResolutionTask {
  id: string;
  question: string;
  abstention_reason: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
  conversation_id: string | null;
  retrieved_evidence: EvidenceItem[];
  clarification_id: string | null;
  clarification_status: ClarificationStatus | null;
}

export interface Clarification {
  id: string;
  task_id: string;
  question: string;
  answer: string;
  status: ClarificationStatus;
  created_at: string;
  approved_at: string | null;
  published_at: string | null;
}

// ─── Dashboard ─────────────────────────────────────────────
export interface DashboardStats {
  total_conversations: number;
  total_messages: number;
  approved_answers: number;
  abstained_answers: number;
  total_documents: number;
  published_documents: number;
  open_resolution_tasks: number;
}
