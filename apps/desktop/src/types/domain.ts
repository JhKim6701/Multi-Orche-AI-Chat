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
  segment_id?: number | null;
  role: string;
  content_markdown: string;
  model_name?: string | null;
  model_role?: string | null;
  sequence_no: number;
}

export interface MessageListResponse {
  items: Message[];
  scope_meta: {
    scope: 'active' | 'segment' | 'all';
    active_segment_id?: number | null;
    selected_segment_id?: number | null;
    segment_boundaries: number[];
  };
}

export interface Asset {
  id: number;
  chat_thread_id: number;
  message_id?: number | null;
  source_type?: string;
  original_filename: string;
  mime_type: string;
  stored_path: string;
  created_at: string;
  derived_metadata_json?: { ingest_status?: string; preview?: string; chunk_count?: number } | null;
  producing_model?: string | null;
  producing_role?: string | null;
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
  segment_id?: number;
  topic_label?: string;
  parent_segment_id?: number;
  divergence_reason?: string;
  current_active_step?: string | null;
  routing_reason?: string | null;
  used_asset_ids?: number[];
  used_segment_id?: number | null;
  parent_segment_summary_used?: boolean | null;
  reviewer_decision?: string | null;
  generated_artifact_ids?: number[];
  artifact_summary?: Array<{ id: number; filename: string; mime_type?: string; producing_model?: string | null; producing_role?: string | null }>;
  vision_used?: boolean;
  image_asset_ids?: number[];
  gpu_enabled?: boolean;
  critic_model?: string | null;
  critic_summary?: string | null;
}

export interface OrchestrationStep {
  id: number;
  step_name: string;
  assigned_role: string;
  status: string;
  model_name?: string | null;
  input_summary?: string | null;
  output_summary?: string | null;
  routing_reason?: string | null;
  reviewer_decision?: string | null;
  used_asset_ids?: number[];
  image_asset_ids?: number[];
  vision_used?: boolean | null;
  gpu_enabled?: boolean | null;
  used_segment_id?: number | null;
  parent_segment_summary_used?: boolean | null;
}
