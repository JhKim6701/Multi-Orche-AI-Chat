export interface Project {
  id: number;
  name: string;
  description?: string | null;
}

export interface ChatThread {
  id: number;
  project_id: number;
  title: string;
}

export interface Message {
  id: number;
  project_id: number;
  chat_thread_id: number;
  role: string;
  content_markdown: string;
  model_name?: string | null;
  sequence_no: number;
}

export interface Asset {
  id: number;
  chat_thread_id: number;
  message_id?: number | null;
  original_filename: string;
  mime_type: string;
  stored_path: string;
  created_at: string;
  derived_metadata_json?: { ingest_status?: string; preview?: string; chunk_count?: number } | null;
}

export interface Model {
  id: number;
  model_name: string;
  downloaded: boolean;
  enabled: boolean;
  sort_order: number;
}

export interface OrchestrationRun {
  id: number;
  status: string;
  graph_name: string;
  started_at: string;
  final_message_id?: number;
}

export interface OrchestrationStep {
  id: number;
  step_name: string;
  assigned_role: string;
  status: string;
  model_name?: string | null;
  input_summary?: string | null;
  output_summary?: string | null;
}
