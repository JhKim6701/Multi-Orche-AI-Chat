import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FormEvent, useMemo, useState } from 'react';

import { api } from '../lib/api';
import { useUiStore } from '../store/uiStore';
import { Asset, Message, OrchestrationRun, OrchestrationStep } from '../types/domain';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

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

  const { data: messages = [], error: messageError } = useQuery({
    queryKey: ['messages', selectedChatId],
    queryFn: () => api.get<Message[]>(`/messages?chat_thread_id=${selectedChatId}`),
    enabled: !!selectedChatId
  });

  const { data: assets = [] } = useQuery({
    queryKey: ['assets', selectedChatId],
    queryFn: () => api.get<Asset[]>(`/assets/chat/${selectedChatId}`),
    enabled: !!selectedChatId
  });

  const { data: runs = [] } = useQuery({
    queryKey: ['orchestration-runs', selectedChatId],
    queryFn: () => api.get<OrchestrationRun[]>(`/orchestration/runs?chat_thread_id=${selectedChatId}`),
    enabled: !!selectedChatId && orchestratorOn,
    refetchInterval: orchestratorOn ? 3000 : false,
  });

  const { data: runDetail } = useQuery({
    queryKey: ['orchestration-run-detail', selectedRunId],
    queryFn: () => api.get<{ run: OrchestrationRun & { final_message_id?: number }; steps: OrchestrationStep[]; final_message?: { content_markdown: string } }>(`/orchestration/runs/${selectedRunId}`),
    enabled: !!selectedRunId && orchestratorOn,
    refetchInterval: orchestratorOn ? 3000 : false,
  });

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
      api.post<{ user_message: { id: number } }>('/messages/execute', {
        project_id: selectedProjectId,
        chat_thread_id: selectedChatId,
        content_markdown: message,
        selected_model_names: selectedModelNames,
        execution_mode: executionMode,
        message_asset_ids: assetIds
      }),
    onSuccess: () => {
      setMessage('');
      setStreamPreview('');
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['assets', selectedChatId] });
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
    }
  });

  const canSend = !!selectedChatId && !!selectedProjectId && !!message.trim() && selectedModelNames.length > 0;

  const previewStream = async () => {
    if (!selectedChatId || selectedModelNames.length === 0 || !message.trim()) return;
    const url = new URL(`${API_BASE}/messages/stream`);
    url.searchParams.set('chat_thread_id', String(selectedChatId));
    url.searchParams.set('model_name', selectedModelNames[0]);
    url.searchParams.set('prompt', message);

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

      if (orchestratorOn) {
        await orchestrateMutation.mutateAsync(assetIds);
      } else {
        await manualRunMutation.mutateAsync(assetIds);
      }
    } finally {
      setSending(false);
    }
  };

  const timeline = useMemo(() => messages.slice().sort((a, b) => a.sequence_no - b.sequence_no), [messages]);
  const activeStepId = runDetail?.steps?.find((step) => step.status === 'running')?.id;

  return (
    <main style={{ padding: 10, height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <h3 style={{ margin: 0 }}>Chat {orchestratorOn ? '(Orchestrator ON)' : '(Manual Mode)'}</h3>
      {!selectedChatId && <p style={{ fontSize: 12 }}>Select chat to start.</p>}
      {messageError && <p style={{ color: 'red' }}>Failed to load messages</p>}

      <section style={{ flex: 1, overflow: 'auto', border: '1px solid #eee', borderRadius: 6, padding: 8 }}>
        {timeline.length === 0 ? <p style={{ fontSize: 12 }}>No messages yet</p> : null}
        {timeline.map((m) => (
          <div key={m.id} style={{ marginBottom: 8, padding: 8, background: m.role === 'user' ? '#f7fbff' : '#f8f8f8', borderRadius: 6 }}>
            <div style={{ fontSize: 11, color: '#666' }}>
              {m.role}
              {m.model_name ? ` · ${m.model_name}` : ''}
              {m.role === 'assistant' && m.model_name ? ` (${m.model_name})` : ''}
            </div>
            <div style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{m.content_markdown}</div>
          </div>
        ))}
      </section>

      <section style={{ border: '1px solid #eee', borderRadius: 6, padding: 8 }}>
        <div style={{ fontSize: 12, marginBottom: 6 }}>Assets</div>
        {assets.length === 0 ? <small>No uploads</small> : assets.map((a) => (
          <div key={a.id} style={{ fontSize: 12, marginBottom: 4 }}>
            <a href={`${API_BASE}/assets/${a.id}/download`} target="_blank">{a.original_filename}</a>
            {a.mime_type.startsWith('image/') && (
              <div>
                <img src={`${API_BASE}/assets/${a.id}/download`} alt={a.original_filename} style={{ maxWidth: 140, maxHeight: 100, marginTop: 4 }} />
              </div>
            )}
          </div>
        ))}
      </section>

      {orchestratorOn && (
        <section style={{ border: '1px solid #eee', borderRadius: 6, padding: 8 }}>
          <button onClick={() => setShowRunDetail((v) => !v)} style={{ fontSize: 12 }}>
            {showRunDetail ? 'Hide' : 'Show'} Orchestration Detail
          </button>
          {showRunDetail && (
            <>
              <div style={{ fontSize: 12, marginTop: 6 }}>Run Status: {runDetail?.run?.status ?? '-'}</div>
              {runs.length === 0 ? <small>No runs</small> : (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {runs.map((r) => (
                    <button key={r.id} onClick={() => setSelectedRunId(r.id)} style={{ fontSize: 11 }}>
                      #{r.id} {r.status}
                    </button>
                  ))}
                </div>
              )}
              {runDetail?.steps?.length ? (
                <ol style={{ marginTop: 6, paddingLeft: 18 }}>
                  {runDetail.steps.map((step) => (
                    <li key={step.id} style={{ fontSize: 12, marginBottom: 4, background: activeStepId === step.id ? '#fff7d6' : 'transparent' }}>
                      <div><strong>{step.step_name}</strong> · role={step.assigned_role} · model={step.model_name ?? '-'}</div>
                      <div>input: {step.input_summary ?? '-'}</div>
                      <div>output: {step.output_summary ?? '-'}</div>
                    </li>
                  ))}
                </ol>
              ) : null}
              {runDetail?.final_message ? (
                <div style={{ marginTop: 6, padding: 6, background: '#eef8ee', fontSize: 12 }}>
                  <strong>Final Result</strong>
                  <div>{runDetail.final_message.content_markdown}</div>
                </div>
              ) : null}
            </>
          )}
        </section>
      )}

      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={4} placeholder="Type message..." style={{ fontSize: 13 }} />
        <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
          <small>{sending ? 'Processing request...' : 'Ready'}</small>
          <div style={{ display: 'flex', gap: 4 }}>
            <button type="button" onClick={previewStream} style={{ fontSize: 12 }}>Stream Preview</button>
            <button type="submit" disabled={!canSend || sending} style={{ fontSize: 12 }}>Send</button>
          </div>
        </div>
      </form>
      {streamPreview && (
        <pre style={{ margin: 0, maxHeight: 120, overflow: 'auto', fontSize: 11, background: '#f5f5f5', padding: 6 }}>{streamPreview}</pre>
      )}
      {(manualRunMutation.error || orchestrateMutation.error) && (
        <p style={{ color: 'red' }}>{((manualRunMutation.error || orchestrateMutation.error) as Error).message}</p>
      )}
    </main>
  );
}
