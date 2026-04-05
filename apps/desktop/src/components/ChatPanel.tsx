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
  const [viewMode, setViewMode] = useState<ViewMode>('active');
  const [selectedSegmentId, setSelectedSegmentId] = useState<number | null>(null);
  const [divergence, setDivergence] = useState<DetectResponse | null>(null);
  const [liveEvents, setLiveEvents] = useState<StreamEvent[]>([]);

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
    queryFn: () => api.get<{ run: OrchestrationRun & { final_message_id?: number; segment_id?: number }; steps: OrchestrationStep[]; final_message?: { content_markdown: string } }>(`/orchestration/runs/${selectedRunId}`),
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
        message_asset_ids: assetIds
      }),
    onSuccess: (run) => {
      setMessage('');
      setSelectedRunId(run.id);
      qc.invalidateQueries({ queryKey: ['orchestration-runs', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['segments', selectedChatId] });
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
          </div>
        ))}
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
              {runs.map((r) => <button key={r.id} onClick={() => setSelectedRunId(r.id)} style={{ fontSize: 11, marginRight: 4 }}>#{r.id} {r.status}</button>)}
              {runDetail?.steps?.length ? (
                <ol style={{ marginTop: 6, paddingLeft: 18 }}>
                  {runDetail.steps.map((step) => (
                    <li key={step.id} style={{ fontSize: 12, background: activeStepId === step.id ? '#fff7d6' : 'transparent' }}>
                      <div><strong>{step.step_name}</strong> role={step.assigned_role} model={step.model_name ?? '-'}</div>
                      <div>input: {step.input_summary ?? '-'}</div>
                      <div>output: {step.output_summary ?? '-'}</div>
                    </li>
                  ))}
                </ol>
              ) : null}
              {!!liveEvents.length && (
                <div style={{ marginTop: 6, fontSize: 11, borderTop: '1px dashed #ddd', paddingTop: 6 }}>
                  {liveEvents.map((evt, idx) => (
                    <div key={`${evt.timestamp}-${idx}`}>
                      [{evt.event_type}] step={evt.step_name ?? '-'} status={evt.status} model={evt.model_name ?? '-'} seg#{evt.segment_id ?? '-'}
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
          <small>{sending ? 'Processing request...' : `Ready · scope=${queryScope}${queryScope === 'segment' ? `#${selectedSegmentId}` : ''}`}</small>
          <div style={{ display: 'flex', gap: 4 }}>
            <button type="button" onClick={previewStream} style={{ fontSize: 12 }}>Stream Preview</button>
            <button type="submit" disabled={!canSend || sending} style={{ fontSize: 12 }}>Send</button>
          </div>
        </div>
      </form>
      {streamPreview && <pre style={{ margin: 0, maxHeight: 120, overflow: 'auto', fontSize: 11, background: '#f5f5f5', padding: 6 }}>{streamPreview}</pre>}
      {(manualRunMutation.error || orchestrateMutation.error || branchMutation.error || switchSegment.error) && <p style={{ color: 'red' }}>{((manualRunMutation.error || orchestrateMutation.error || branchMutation.error || switchSegment.error) as Error).message}</p>}
    </main>
  );
}
