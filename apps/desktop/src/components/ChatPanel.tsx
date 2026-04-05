import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FormEvent, useMemo, useState } from 'react';

import { api } from '../lib/api';
import { useUiStore } from '../store/uiStore';
import { Asset, Message } from '../types/domain';

export function ChatPanel() {
  const qc = useQueryClient();
  const selectedProjectId = useUiStore((s) => s.selectedProjectId);
  const selectedChatId = useUiStore((s) => s.selectedChatId);
  const selectedModelNames = useUiStore((s) => s.selectedModelNames);
  const orchestratorOn = useUiStore((s) => s.orchestratorOn);
  const executionMode = useUiStore((s) => s.executionMode);

  const [message, setMessage] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [sending, setSending] = useState(false);

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

  const runMutation = useMutation({
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
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['assets', selectedChatId] });
    }
  });

  const orchestrateMutation = useMutation({
    mutationFn: (userMessageId: number) =>
      api.post('/orchestration/run', {
        project_id: selectedProjectId,
        chat_thread_id: selectedChatId,
        user_message_id: userMessageId
      })
  });

  const canSend = !!selectedChatId && !!selectedProjectId && !!message.trim() && (orchestratorOn || selectedModelNames.length > 0);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSend) return;
    setSending(true);
    try {
      let uploaded: Asset | null = null;
      if (file) uploaded = await uploadMutation.mutateAsync({ file });
      const assetIds = uploaded ? [uploaded.id] : [];

      const runResult = await runMutation.mutateAsync(assetIds);
      if (orchestratorOn && runResult?.user_message?.id) {
        await orchestrateMutation.mutateAsync(runResult.user_message.id);
      }
    } finally {
      setSending(false);
    }
  };

  const timeline = useMemo(() => messages.slice().sort((a, b) => a.sequence_no - b.sequence_no), [messages]);

  return (
    <main style={{ padding: 10, height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <h3 style={{ margin: 0 }}>Chat</h3>
      {!selectedChatId && <p style={{ fontSize: 12 }}>Select chat to start.</p>}
      {messageError && <p style={{ color: 'red' }}>Failed to load messages</p>}

      <section style={{ flex: 1, overflow: 'auto', border: '1px solid #eee', borderRadius: 6, padding: 8 }}>
        {timeline.length === 0 ? <p style={{ fontSize: 12 }}>No messages yet</p> : null}
        {timeline.map((m) => (
          <div key={m.id} style={{ marginBottom: 8, padding: 8, background: m.role === 'user' ? '#f7fbff' : '#f8f8f8', borderRadius: 6 }}>
            <div style={{ fontSize: 11, color: '#666' }}>
              {m.role}
              {m.model_name ? ` · ${m.model_name}` : ''}
            </div>
            <div style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{m.content_markdown}</div>
          </div>
        ))}
      </section>

      <section style={{ border: '1px solid #eee', borderRadius: 6, padding: 8 }}>
        <div style={{ fontSize: 12, marginBottom: 6 }}>Assets</div>
        {assets.length === 0 ? <small>No uploads</small> : assets.map((a) => (
          <div key={a.id} style={{ fontSize: 12 }}>
            <a href={`${import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'}/assets/${a.id}/download`} target="_blank">{a.original_filename}</a>
          </div>
        ))}
      </section>

      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={4} placeholder="Type message..." style={{ fontSize: 13 }} />
        <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <small>{sending ? 'Streaming/processing...' : 'Ready'}</small>
          <button type="submit" disabled={!canSend || sending} style={{ fontSize: 12 }}>Send</button>
        </div>
      </form>
      {runMutation.error && <p style={{ color: 'red' }}>{(runMutation.error as Error).message}</p>}
    </main>
  );
}
