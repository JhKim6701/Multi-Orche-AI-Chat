import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FormEvent, useEffect, useMemo, useState } from 'react';

import { api } from '../lib/api';
import { useUiStore } from '../store/uiStore';
import { Asset, MessageListResponse, OrchestrationRun, OrchestrationStep } from '../types/domain';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

type Segment = {
  id: number;
  topic_label: string;
  topic_summary: string;
  is_active: boolean;
  parent_segment_id?: number | null;
  branch_from_message_id?: number | null;
};

type ViewMode = 'active' | 'all' | 'segment';

type DetectResponse = {
  active_segment_id: number;
  diverged: boolean;
  overlap: number;
  reason: string;
  recommended_action: 'stay' | 'new_segment';
  suggested_topic_label: string;
};

type BranchResponse = {
  created_segment_id: number;
  topic_label: string;
  parent_segment_id: number | null;
  branch_from_message_id: number;
  active_switched: boolean;
  active_segment_id: number;
};

type StreamEvent = {
  event_type: string;
  run_id: number;
  step_id: number | null;
  step_name: string | null;
  status: string;
  model_name: string | null;
  segment_id: number | null;
  timestamp: string;
  final_message_id?: number | null;
  reviewer_decision?: string | null;
  assigned_role?: string | null;
  fallback_model_name?: string | null;
  retry_count?: number;
  approval_status?: string | null;
};

type RetrievalHit = {
  chunk_id: number;
  asset_id: number;
  filename: string;
  chunk_index: number;
  page?: number | null;
  snippet: string;
  score: number;
  retrieval_mode: string;
};

export function ChatPanel() {
  const qc = useQueryClient();
  const selectedProjectId = useUiStore((s) => s.selectedProjectId);
  const selectedChatId = useUiStore((s) => s.selectedChatId);
  const selectedModelNames = useUiStore((s) => s.selectedModelNames);
  const orchestratorOn = useUiStore((s) => s.orchestratorOn);
  const executionMode = useUiStore((s) => s.executionMode);
  const orchestratorModelName = useUiStore((s) => s.orchestratorModelName);

  const [message, setMessage] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [streamPreview, setStreamPreview] = useState('');
  const [showRunDetail, setShowRunDetail] = useState(true);
  const [showOrchestrationDrawer, setShowOrchestrationDrawer] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('active');
  const [selectedSegmentId, setSelectedSegmentId] = useState<number | null>(null);
  const [divergence, setDivergence] = useState<DetectResponse | null>(null);
  const [liveEvents, setLiveEvents] = useState<StreamEvent[]>([]);
  const [requireApprovalBeforePublish, setRequireApprovalBeforePublish] = useState(false);
  const [showRetrievalDebug, setShowRetrievalDebug] = useState(false);

  const queryScope = viewMode === 'segment' ? 'segment' : viewMode;
  const scopeQuery = viewMode === 'segment' && selectedSegmentId ? `&segment_id=${selectedSegmentId}` : '';

  const { data: messageResponse, error: messageError } = useQuery({
    queryKey: ['messages', selectedChatId, queryScope, selectedSegmentId],
    queryFn: () => api.get<MessageListResponse>(`/messages?chat_thread_id=${selectedChatId}&scope=${queryScope}${scopeQuery}`),
    enabled: !!selectedChatId
  });

  const messages = messageResponse?.items ?? [];
  const scopeMeta = messageResponse?.scope_meta;

  const { data: assets = [] } = useQuery({
    queryKey: ['assets', selectedChatId],
    queryFn: () => api.get<Asset[]>(`/assets/chat/${selectedChatId}`),
    enabled: !!selectedChatId
  });
  const { data: retrievalPreview } = useQuery({
    queryKey: ['retrieval-preview', selectedChatId, selectedSegmentId, message],
    queryFn: () => api.get<{ hits: RetrievalHit[] }>(`/assets/chat/${selectedChatId}/retrieval-preview?query=${encodeURIComponent(message)}${selectedSegmentId ? `&segment_id=${selectedSegmentId}` : ''}`),
    enabled: !!selectedChatId && showRetrievalDebug && message.trim().length > 2,
  });

  const { data: segments = [] } = useQuery({
    queryKey: ['segments', selectedChatId],
    queryFn: () => api.get<Segment[]>(`/segments?chat_thread_id=${selectedChatId}`),
    enabled: !!selectedChatId,
    refetchInterval: 3000,
  });

  const activeSegment = segments.find((s) => s.is_active);
  const selectedSegment = segments.find((s) => s.id === selectedSegmentId);

  useEffect(() => {
    if (!selectedSegmentId && activeSegment) {
      setSelectedSegmentId(activeSegment.id);
    }
  }, [activeSegment, selectedSegmentId]);

  const switchSegment = useMutation({
    mutationFn: (segmentId: number) => api.post<{ active_segment: { id: number } }>(`/segments/switch?chat_thread_id=${selectedChatId}`, { segment_id: segmentId }),
    onSuccess: ({ active_segment }) => {
      setSelectedSegmentId(active_segment.id);
      setViewMode('segment');
      qc.invalidateQueries({ queryKey: ['segments', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
    }
  });

  const branchMutation = useMutation({
    mutationFn: ({ messageId, topicLabel }: { messageId: number; topicLabel: string }) =>
      api.post<BranchResponse>(`/segments/branch?chat_thread_id=${selectedChatId}`, { from_message_id: messageId, topic_label: topicLabel }),
    onSuccess: (payload) => {
      setSelectedSegmentId(payload.created_segment_id);
      setViewMode('segment');
      qc.invalidateQueries({ queryKey: ['segments', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
    }
  });

  const { data: runs = [] } = useQuery({
    queryKey: ['orchestration-runs', selectedChatId],
    queryFn: () => api.get<OrchestrationRun[]>(`/orchestration/runs?chat_thread_id=${selectedChatId}`),
    enabled: !!selectedChatId && orchestratorOn,
    refetchInterval: orchestratorOn ? 3000 : false,
  });

  const { data: runDetail } = useQuery({
    queryKey: ['orchestration-run-detail', selectedRunId],
    queryFn: () => api.get<{ run: OrchestrationRun & { final_message_id?: number; segment_id?: number; generated_artifact_ids?: number[]; artifact_summary?: Array<{ id: number; filename: string; producing_model?: string; producing_role?: string }>; vision_used?: boolean; image_asset_ids?: number[]; approval_status?: string; pending_final_draft?: string; execution_graph_summary?: { parallel_groups?: Record<string, number[]>; step_count?: number }; final_publish_status?: string }; steps: OrchestrationStep[]; final_message?: { content_markdown: string; final_provenance_summary?: string; generated_artifact_ids?: number[] } }>(`/orchestration/runs/${selectedRunId}`),
    enabled: !!selectedRunId && orchestratorOn,
    refetchInterval: orchestratorOn ? 3000 : false,
  });

  useEffect(() => {
    if (!selectedRunId || !orchestratorOn) return;
    const source = new EventSource(`${API_BASE}/orchestration/runs/${selectedRunId}/stream`);
    const handle = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as StreamEvent;
        setLiveEvents((prev) => [...prev.slice(-9), payload]);
        qc.invalidateQueries({ queryKey: ['orchestration-run-detail', selectedRunId] });
        if (payload.event_type === 'run_completed' || payload.event_type === 'run_failed') {
          qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
          qc.invalidateQueries({ queryKey: ['segments', selectedChatId] });
        }
      } catch {
        // noop, fallback polling still active
      }
    };

    source.addEventListener('run_started', handle);
    source.addEventListener('step_started', handle);
    source.addEventListener('step_completed', handle);
    source.addEventListener('reviewer_started', handle);
    source.addEventListener('reviewer_completed', handle);
    source.addEventListener('revision_started', handle);
    source.addEventListener('revision_completed', handle);
    source.addEventListener('run_completed', handle);
    source.addEventListener('run_failed', handle);
    source.onerror = () => source.close();

    return () => source.close();
  }, [selectedRunId, orchestratorOn, qc, selectedChatId]);

  const uploadMutation = useMutation({
    mutationFn: (payload: { file: File; messageId?: number }) => {
      const form = new FormData();
      form.append('project_id', String(selectedProjectId));
      form.append('chat_thread_id', String(selectedChatId));
      form.append('source_type', 'user_upload');
      if (payload.messageId) form.append('message_id', String(payload.messageId));
      form.append('file', payload.file);
      return api.postForm<Asset>('/assets/upload', form);
    },
    onSuccess: () => {
      setFile(null);
      qc.invalidateQueries({ queryKey: ['assets', selectedChatId] });
    }
  });

  const manualRunMutation = useMutation({
    mutationFn: (assetIds: number[]) =>
      api.post<{ used_segment_id: number; user_message: { id: number } }>('/messages/execute', {
        project_id: selectedProjectId,
        chat_thread_id: selectedChatId,
        content_markdown: message,
        selected_model_names: selectedModelNames,
        execution_mode: executionMode,
        message_asset_ids: assetIds
      }),
    onSuccess: (result) => {
      setMessage('');
      setStreamPreview('');
      setSelectedSegmentId(result.used_segment_id);
      if (viewMode === 'segment' && result.used_segment_id) {
        setViewMode('segment');
      }
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['assets', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['segments', selectedChatId] });
    }
  });

  const orchestrateMutation = useMutation({
    mutationFn: (assetIds: number[]) =>
      api.post<{ id: number }>('/orchestration/run', {
        project_id: selectedProjectId,
        chat_thread_id: selectedChatId,
        content_markdown: message,
        selected_model_names: selectedModelNames,
        orchestrator_model_name: orchestratorModelName,
        message_asset_ids: assetIds,
        require_approval_before_publish: requireApprovalBeforePublish,
      }),
    onSuccess: (run) => {
      setMessage('');
      setSelectedRunId(run.id);
      qc.invalidateQueries({ queryKey: ['orchestration-runs', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['segments', selectedChatId] });
    }
  });
  const approveRunMutation = useMutation({
    mutationFn: (runId: number) => api.post(`/orchestration/runs/${runId}/approve`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['orchestration-run-detail', selectedRunId] });
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
    }
  });
  const rejectRunMutation = useMutation({
    mutationFn: (runId: number) => api.post(`/orchestration/runs/${runId}/reject`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['orchestration-run-detail', selectedRunId] });
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
    }
  });

  const canSend = !!selectedChatId && !!selectedProjectId && !!message.trim() && selectedModelNames.length > 0;

  const previewStream = async () => {
    if (!selectedChatId || selectedModelNames.length === 0 || !message.trim()) return;
    const detect = await api.post<DetectResponse>(`/segments/detect?chat_thread_id=${selectedChatId}&new_text=${encodeURIComponent(message)}`);
    setDivergence(detect);

    const url = new URL(`${API_BASE}/messages/stream`);
    url.searchParams.set('chat_thread_id', String(selectedChatId));
    url.searchParams.set('model_name', selectedModelNames[0]);
    url.searchParams.set('prompt', message);
    url.searchParams.set('scope', queryScope);
    if (queryScope === 'segment' && selectedSegmentId) {
      url.searchParams.set('segment_id', String(selectedSegmentId));
    }

    const res = await fetch(url.toString());
    if (!res.ok || !res.body) {
      setStreamPreview('stream unavailable');
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let text = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      text += decoder.decode(value, { stream: true });
      setStreamPreview(text.slice(-3000));
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSend) return;
    setSending(true);
    try {
      let uploaded: Asset | null = null;
      if (file) uploaded = await uploadMutation.mutateAsync({ file });
      const assetIds = uploaded ? [uploaded.id] : [];

      if (orchestratorOn) await orchestrateMutation.mutateAsync(assetIds);
      else await manualRunMutation.mutateAsync(assetIds);
    } finally {
      setSending(false);
    }
  };

  const timeline = useMemo(() => messages.slice().sort((a, b) => a.sequence_no - b.sequence_no), [messages]);
  const activeStepId = runDetail?.steps?.find((step) => step.status === 'running')?.id;
  const latestAssistant = [...timeline].reverse().find((m) => m.role === 'assistant');
  const usedAssetsLine = latestAssistant?.content_markdown?.split('\n').find((line) => line.includes('[Used assets]'));
  const provenanceLine = latestAssistant?.content_markdown?.split('\n').find((line) => line.includes('[Orchestration Provenance]'));
  const generatedByMessage = useMemo(() => {
    const map = new Map<number, Asset[]>();
    assets.filter((a) => a.source_type === 'ai_generated' && a.message_id).forEach((a) => {
      const key = a.message_id as number;
      const prev = map.get(key) ?? [];
      prev.push(a);
      map.set(key, prev);
    });
    return map;
  }, [assets]);
  const visionPending = file?.type?.startsWith('image/') ?? false;
  const surfaceError = (manualRunMutation.error || orchestrateMutation.error || branchMutation.error || switchSegment.error) as Error | null;
  const errorText = (surfaceError?.message ?? '').toLowerCase();
  const recoveryHint = errorText.includes('ollama')
    ? 'Ollama가 실행 중인지 확인 후 다시 시도하세요.'
    : errorText.includes('qdrant')
      ? 'Qdrant 연결을 확인하거나 retrieval fallback 상태를 확인하세요.'
      : errorText.includes('upload') || errorText.includes('write')
        ? '업로드/데이터 경로 권한을 확인하세요.'
        : '시스템 상태 배너를 확인하고 다시 시도하세요.';

  const divergenceLabel = useMemo(() => {
    if (!divergence) return '';
    if (divergence.reason.includes('shift_expression')) return '전환 표현 감지: 새 segment 권장';
    if (divergence.recommended_action === 'new_segment') return '새 segment 추천';
    return '현재 주제 유지';
  }, [divergence]);

  return (
    <main style={{ padding: 10, height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <h3 style={{ margin: 0 }}>Chat {orchestratorOn ? '(Orchestrator ON)' : '(Manual Mode)'}</h3>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <button style={{ fontSize: 12, background: viewMode === 'active' ? '#d8f0ff' : '#fff' }} onClick={() => setViewMode('active')}>Active Segment View</button>
        <button style={{ fontSize: 12, background: viewMode === 'all' ? '#d8f0ff' : '#fff' }} onClick={() => setViewMode('all')}>Full Timeline View</button>
        <button style={{ fontSize: 12, background: viewMode === 'segment' ? '#d8f0ff' : '#fff' }} onClick={() => setViewMode('segment')} disabled={!selectedSegmentId}>Selected Segment View</button>
      </div>

      <div style={{ fontSize: 12, background: '#fafafa', padding: 6, border: '1px solid #eee' }}>
        Active Segment: {activeSegment?.topic_label ?? 'N/A'} (#{scopeMeta?.active_segment_id ?? '-'})
        {activeSegment?.parent_segment_id ? ` · parent seg#${activeSegment.parent_segment_id}` : ''}
        {activeSegment?.branch_from_message_id ? ` · origin msg#${activeSegment.branch_from_message_id}` : ''}
        {viewMode === 'segment' && selectedSegment ? ` · viewing seg#${selectedSegment.id}:${selectedSegment.topic_label}` : ''}
      </div>

      {!!segments.length && (
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {segments.map((s) => (
            <button key={s.id} onClick={() => { setSelectedSegmentId(s.id); setViewMode('segment'); }} style={{ fontSize: 11, background: s.is_active ? '#e8f0ff' : '#fff' }}>
              seg#{s.id} {s.topic_label} {s.is_active ? '· active' : ''} {s.parent_segment_id ? `· child of #${s.parent_segment_id}` : '· root'} {s.branch_from_message_id ? `· from msg#${s.branch_from_message_id}` : ''}
            </button>
          ))}
          {viewMode === 'segment' && selectedSegmentId && (
            <button onClick={() => switchSegment.mutate(selectedSegmentId)} style={{ fontSize: 11 }}>Switch active to seg#{selectedSegmentId}</button>
          )}
        </div>
      )}

      {!selectedChatId && <p style={{ fontSize: 12 }}>Select chat to start.</p>}
      {messageError && <p style={{ color: 'red' }}>Failed to load messages</p>}

      <section style={{ flex: 1, overflow: 'auto', border: '1px solid #eee', borderRadius: 6, padding: 8 }}>
        {timeline.length === 0 ? <p style={{ fontSize: 12 }}>No messages yet</p> : null}
        {timeline.map((m, idx) => (
          <div key={m.id} style={{ marginBottom: 8, padding: 8, background: m.role === 'user' ? '#f7fbff' : '#f8f8f8', borderRadius: 6 }}>
            {scopeMeta?.scope === 'all' && scopeMeta.segment_boundaries.includes(m.sequence_no) && (
              <div style={{ fontSize: 11, color: '#8a5' }}>Segment boundary · segment #{m.segment_id}</div>
            )}
            {idx > 0 && timeline[idx - 1].segment_id !== m.segment_id && scopeMeta?.scope !== 'all' && (
              <div style={{ fontSize: 11, color: '#8a5' }}>새 주제 시작 (segment #{m.segment_id})</div>
            )}
            <div style={{ fontSize: 11, color: '#666' }}>{m.role} · seg#{m.segment_id ?? '-'} {m.model_name ? `· ${m.model_name}` : ''}</div>
            <div style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{m.content_markdown}</div>
            {m.role === 'assistant' && (
              <div style={{ marginTop: 6, fontSize: 11, borderTop: '1px dashed #ddd', paddingTop: 6 }}>
                {m.content_markdown.split('\n').filter((line) => line.startsWith('[Used ') || line.startsWith('[RAG Provenance]')).map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
              </div>
            )}
            {m.role === 'assistant' && (generatedByMessage.get(m.id)?.length ?? 0) > 0 && (
              <div style={{ marginTop: 6, borderTop: '1px dashed #ddd', paddingTop: 6, fontSize: 11 }}>
                <div>Generated Artifacts</div>
                {(generatedByMessage.get(m.id) ?? []).map((asset) => (
                  <div key={asset.id} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <a href={`${API_BASE}/assets/${asset.id}/download`} target="_blank">{asset.original_filename}</a>
                    <span>model={asset.producing_model ?? '-'}</span>
                    <span>role={asset.producing_role ?? '-'}</span>
                    <span>kind={asset.derived_metadata_json?.kind ?? 'unknown'}</span>
                    <span>summary={asset.derived_metadata_json?.artifact_summary ?? '-'}</span>
                  </div>
                ))}
              </div>
            )}
            {m.role === 'user' && (
              <div style={{ marginTop: 6 }}>
                <button
                  type="button"
                  onClick={() => branchMutation.mutate({ messageId: m.id, topicLabel: `${m.content_markdown.split(' ').slice(0, 4).join(' ') || 'branch'}-branch` })}
                  style={{ fontSize: 11 }}
                >
                  여기서 분기 만들기
                </button>
              </div>
            )}
          </div>
        ))}
      </section>

      <section style={{ border: '1px solid #eee', borderRadius: 6, padding: 8 }}>
        <div style={{ fontSize: 12, marginBottom: 6 }}>Assets</div>
        {assets.length === 0 ? <small>No uploads</small> : assets.map((a) => (
          <div key={a.id} style={{ fontSize: 12, marginBottom: 4 }}>
            <a href={`${API_BASE}/assets/${a.id}/download`} target="_blank">{a.original_filename}</a>
            <small style={{ marginLeft: 6 }}>[{a.derived_metadata_json?.ingest_status ?? 'uploaded'}] chunks:{a.derived_metadata_json?.chunk_count ?? 0}</small>
            <div style={{ fontSize: 11, color: '#555' }}>
              uploaded={String(a.derived_metadata_json?.ingest_pipeline?.uploaded ?? true)} ·
              extracted={String(a.derived_metadata_json?.ingest_pipeline?.extracted ?? false)} ·
              chunked={String(a.derived_metadata_json?.ingest_pipeline?.chunked ?? false)} ·
              embedded={String(a.derived_metadata_json?.ingest_pipeline?.embedded ?? false)} ·
              indexed={String(a.derived_metadata_json?.ingest_pipeline?.indexed ?? false)} ·
              ocr_fallback_used={String(a.derived_metadata_json?.ocr_fallback_used ?? false)} ·
              failed={String(a.derived_metadata_json?.ingest_pipeline?.failed ?? false)}
            </div>
          </div>
        ))}
      </section>
      <section style={{ border: '1px solid #eee', borderRadius: 6, padding: 8 }}>
        <button type="button" style={{ fontSize: 12 }} onClick={() => setShowRetrievalDebug((v) => !v)}>
          {showRetrievalDebug ? 'Hide' : 'Show'} Retrieval Preview
        </button>
        {showRetrievalDebug && (
          <div style={{ marginTop: 6, fontSize: 11 }}>
            {(retrievalPreview?.hits ?? []).map((hit) => (
              <div key={hit.chunk_id} style={{ marginBottom: 4, borderBottom: '1px dashed #eee' }}>
                asset#{hit.asset_id} {hit.filename} · chunk#{hit.chunk_id} idx={hit.chunk_index} page={hit.page ?? '-'} · score={hit.score}
                <div>{hit.snippet}</div>
              </div>
            ))}
            {(retrievalPreview?.hits ?? []).length === 0 && <small>No retrieval hits for current query.</small>}
          </div>
        )}
      </section>

      {usedAssetsLine && <div style={{ fontSize: 12, border: '1px solid #eee', padding: 6 }}>Used assets: {usedAssetsLine}</div>}
      {!!divergence && (
        <div style={{ fontSize: 12, color: '#555', border: '1px solid #eee', padding: 6 }}>
          {divergenceLabel} · overlap={divergence.overlap.toFixed(2)} · suggested label: {divergence.suggested_topic_label}
          {divergence.recommended_action === 'new_segment' && (
            <button
              style={{ fontSize: 11, marginLeft: 6 }}
              onClick={() => {
                if (!selectedChatId || !timeline.length) return;
                const lastUser = [...timeline].reverse().find((item) => item.role === 'user');
                if (!lastUser) return;
                branchMutation.mutate({ messageId: lastUser.id, topicLabel: divergence.suggested_topic_label });
              }}
            >
              새 segment로 분기
            </button>
          )}
        </div>
      )}

      {orchestratorOn && (
        <section style={{ border: '1px solid #eee', borderRadius: 6, padding: 8 }}>
          <button onClick={() => setShowRunDetail((v) => !v)} style={{ fontSize: 12 }}>{showRunDetail ? 'Hide' : 'Show'} Orchestration Detail</button>
          {showRunDetail && (
            <>
              <div style={{ fontSize: 12, marginTop: 6 }}>Run Status: {runDetail?.run?.status ?? '-'}</div>
              <div style={{ fontSize: 12 }}>Run Segment: {runDetail?.run?.segment_id ?? '-'} · topic: {runDetail?.run?.topic_label ?? '-'} · parent: {runDetail?.run?.parent_segment_id ?? '-'}</div>
              <div style={{ fontSize: 12 }}>Divergence reason: {runDetail?.run?.divergence_reason ?? '-'} · current step: {runDetail?.run?.current_active_step ?? '-'}</div>
              <div style={{ fontSize: 12 }}>
                Routing reason: {runDetail?.run?.routing_reason ?? '-'} · reviewer: {runDetail?.run?.reviewer_decision ?? '-'} · parent summary used: {String(runDetail?.run?.parent_segment_summary_used ?? false)}
              </div>
              <div style={{ fontSize: 12 }}>Used assets: {(runDetail?.run?.used_asset_ids ?? []).join(', ') || '-'} · used chunks: {(runDetail?.run?.used_chunk_ids ?? []).join(', ') || '-'} · image assets: {(runDetail?.run?.image_asset_ids ?? []).join(', ') || '-'} · vision used: {String(runDetail?.run?.vision_used ?? false)} · gpu enabled: {String(runDetail?.run?.gpu_enabled ?? true)}</div>
              <div style={{ fontSize: 12 }}>retrieval mode: {runDetail?.run?.retrieval_mode ?? '-'} · ocr used: {String(runDetail?.run?.ocr_used ?? false)}</div>
              <div style={{ fontSize: 12 }}>Critic model: {runDetail?.run?.critic_model ?? '-'} · critic summary: {runDetail?.run?.critic_summary ?? '-'}</div>
              <div style={{ fontSize: 12 }}>Approval: {runDetail?.run?.approval_status ?? '-'} · publish: {runDetail?.run?.final_publish_status ?? '-'}</div>
              {runDetail?.run?.pending_final_draft && (
                <div style={{ fontSize: 12, border: '1px dashed #ccc', padding: 6, marginTop: 4 }}>
                  Pending draft: {runDetail.run.pending_final_draft.slice(0, 300)}
                </div>
              )}
              {runDetail?.run?.approval_status === 'pending' && selectedRunId && (
                <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                  <button onClick={() => approveRunMutation.mutate(selectedRunId)} style={{ fontSize: 11 }}>Approve publish</button>
                  <button onClick={() => rejectRunMutation.mutate(selectedRunId)} style={{ fontSize: 11 }}>Reject run</button>
                </div>
              )}
              {runs.map((r) => <button key={r.id} onClick={() => { setSelectedRunId(r.id); setShowOrchestrationDrawer(true); }} style={{ fontSize: 11, marginRight: 4 }}>#{r.id} {r.status}</button>)}
              <button type="button" onClick={() => setShowOrchestrationDrawer(true)} style={{ fontSize: 11 }}>Open Visual Panel</button>
              {runDetail?.steps?.length ? (
                <ol style={{ marginTop: 6, paddingLeft: 18 }}>
                  {runDetail.steps.map((step) => (
                    <li key={step.id} style={{ fontSize: 12, background: activeStepId === step.id ? '#fff7d6' : 'transparent' }}>
                      <div><strong>{step.step_name}</strong> role={step.assigned_role} model={step.model_name ?? '-'}</div>
                      <div>input: {step.input_summary ?? '-'}</div>
                      <div>output: {step.output_summary ?? '-'}</div>
                      <div>routing_reason: {step.routing_reason ?? '-'} · reviewer_decision: {step.reviewer_decision ?? '-'} · execution_mode: {step.execution_mode ?? '-'}</div>
                      <div>used_asset_ids: {(step.used_asset_ids ?? []).join(', ') || '-'} · used_chunk_ids: {(step.used_chunk_ids ?? []).join(', ') || '-'} · image_asset_ids: {(step.image_asset_ids ?? []).join(', ') || '-'} · vision_used: {String(step.vision_used ?? false)}</div>
                      <div>used_segment: {step.used_segment_id ?? '-'} · parent_summary_used: {String(step.parent_segment_summary_used ?? false)} · retry={step.retry_count ?? 0} · fallback={step.fallback_model_name ?? '-'}</div>
                      <div>group={step.step_group ?? '-'} · depends_on={(step.depends_on_step_ids ?? []).join(', ') || '-'} · retrieval={step.retrieval_mode ?? '-'} · ocr={String(step.ocr_used ?? false)} · approval={step.approval_status ?? '-'}</div>
                    </li>
                  ))}
                </ol>
              ) : null}
              {!!liveEvents.length && (
                <div style={{ marginTop: 6, fontSize: 11, borderTop: '1px dashed #ddd', paddingTop: 6 }}>
                  {liveEvents.map((evt, idx) => (
                    <div key={`${evt.timestamp}-${idx}`} style={{ background: evt.event_type.includes('retry') || evt.event_type.includes('fallback') ? '#fff3e0' : evt.event_type.includes('approval') ? '#e8f5e9' : 'transparent' }}>
                      [{evt.event_type}] step={evt.step_name ?? '-'} role={evt.assigned_role ?? '-'} status={evt.status} model={evt.model_name ?? '-'} fallback={evt.fallback_model_name ?? '-'} retry={evt.retry_count ?? 0} approval={evt.approval_status ?? '-'}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      )}

      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={4} placeholder="Type message..." style={{ fontSize: 13 }} />
        <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        {visionPending && <small style={{ color: '#0a66c2' }}>Vision badge: 이미지 업로드 감지됨, vision-capable 모델이면 이미지 입력 경로 사용</small>}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
          {orchestratorOn && (
            <label style={{ fontSize: 11 }}>
              <input type="checkbox" checked={requireApprovalBeforePublish} onChange={(e) => setRequireApprovalBeforePublish(e.target.checked)} />
              require approval before publish
            </label>
          )}
          <small>{sending ? 'Processing request...' : `Ready · scope=${queryScope}${queryScope === 'segment' ? `#${selectedSegmentId}` : ''}`}</small>
          <div style={{ display: 'flex', gap: 4 }}>
            <button type="button" onClick={previewStream} style={{ fontSize: 12 }}>Stream Preview</button>
            <button type="submit" disabled={!canSend || sending} style={{ fontSize: 12 }}>Send</button>
          </div>
        </div>
      </form>
      {streamPreview && <pre style={{ margin: 0, maxHeight: 120, overflow: 'auto', fontSize: 11, background: '#f5f5f5', padding: 6 }}>{streamPreview}</pre>}
      {orchestratorOn && (
        <div style={{ fontSize: 11, border: '1px solid #eee', padding: 6 }}>
          <div>Provenance card</div>
          <div>run: {selectedRunId ?? '-'} · segment: {runDetail?.run?.used_segment_id ?? runDetail?.run?.segment_id ?? '-'}</div>
          <div>assets: {(runDetail?.run?.used_asset_ids ?? []).join(', ') || '-'}</div>
          <div>parent summary used: {String(runDetail?.run?.parent_segment_summary_used ?? false)}</div>
          <div>review outcome: {runDetail?.run?.reviewer_decision ?? '-'}</div>
          <div>revised final: {latestAssistant?.model_role === 'final_responder_revised' ? 'yes' : 'no'}</div>
          {provenanceLine && <div>{provenanceLine}</div>}
          {runDetail?.final_message?.final_provenance_summary && <div>{runDetail.final_message.final_provenance_summary}</div>}
        </div>
      )}
      {surfaceError && (
        <div style={{ color: '#b42318', border: '1px solid #fecdca', background: '#fef3f2', padding: 8, borderRadius: 6, fontSize: 12 }}>
          <div><strong>요청 처리 실패</strong></div>
          <div>{surfaceError.message}</div>
          <div style={{ marginTop: 4 }}>복구 안내: {recoveryHint}</div>
          <button style={{ marginTop: 6, fontSize: 11 }} onClick={() => {
            qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
            qc.invalidateQueries({ queryKey: ['orchestration-run-detail', selectedRunId] });
          }}>Retry load</button>
        </div>
      )}
      {showOrchestrationDrawer && (
        <aside style={{ position: 'fixed', right: 0, top: 0, width: 420, height: '100%', background: '#fff', borderLeft: '1px solid #ddd', padding: 12, overflow: 'auto', boxShadow: '-2px 0 8px rgba(0,0,0,0.08)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong>Orchestration Visual Panel</strong>
            <button onClick={() => setShowOrchestrationDrawer(false)}>Close</button>
          </div>
          <div style={{ fontSize: 12, marginTop: 8 }}>run #{selectedRunId ?? '-'} · routing={runDetail?.run?.routing_reason ?? '-'} · reviewer={runDetail?.run?.reviewer_decision ?? '-'}</div>
          <div style={{ fontSize: 12 }}>vision={String(runDetail?.run?.vision_used ?? false)} · images={(runDetail?.run?.image_asset_ids ?? []).join(', ') || '-'}</div>
          <div style={{ fontSize: 12 }}>generated artifacts={(runDetail?.run?.generated_artifact_ids ?? []).join(', ') || '-'}</div>
          <div style={{ fontSize: 12 }}>graph summary: steps={runDetail?.run?.execution_graph_summary?.step_count ?? 0}</div>
          <div style={{ fontSize: 12 }}>parallel groups: {JSON.stringify(runDetail?.run?.execution_graph_summary?.parallel_groups ?? {})}</div>
          <ol style={{ paddingLeft: 18, marginTop: 10 }}>
            {(runDetail?.steps ?? []).map((step, index) => (
              <li key={step.id} style={{ marginBottom: 8, background: activeStepId === step.id ? '#fff7d6' : '#f9f9f9', padding: 6, borderRadius: 6 }}>
                <div>#{index + 1} {step.step_name}</div>
                <div>role={step.assigned_role} · model={step.model_name ?? '-'}</div>
                <div>routing={step.routing_reason ?? '-'} · reviewer={step.reviewer_decision ?? '-'}</div>
                <div>role-tag={step.step_name.includes('critic') ? 'critic' : step.step_name.includes('reviewer') ? 'reviewer' : 'executor'}</div>
                <div>revision={step.step_name.includes('revision') ? 'yes' : 'no'} · used assets={(step.used_asset_ids ?? []).join(', ') || '-'} · gpu={String(step.gpu_enabled ?? true)}</div>
              </li>
            ))}
          </ol>
          {(runDetail?.run?.artifact_summary ?? []).map((a) => (
            <div key={a.id} style={{ fontSize: 12 }}>
              artifact#{a.id} {a.filename} ({a.producing_model ?? '-'}/{a.producing_role ?? '-'})
            </div>
          ))}
        </aside>
      )}
    </main>
  );
}
