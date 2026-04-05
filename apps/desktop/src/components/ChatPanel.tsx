import { useQuery } from '@tanstack/react-query';

import { getJson } from '../lib/api';
import { useUiStore } from '../store/uiStore';

type Message = { id: number; role: string; content_markdown: string };

export function ChatPanel() {
  const selectedChatId = useUiStore((s) => s.selectedChatId);
  const { data } = useQuery({
    queryKey: ['messages', selectedChatId],
    queryFn: () => getJson<Message[]>(`/messages?chat_thread_id=${selectedChatId}`),
    enabled: Boolean(selectedChatId)
  });

  return (
    <main style={{ padding: 8, overflow: 'auto' }}>
      <h3>Timeline</h3>
      {!selectedChatId && <p>Select a chat.</p>}
      {(data ?? []).map((m) => (
        <div key={m.id} style={{ border: '1px solid #ddd', padding: 8, marginBottom: 8 }}>
          <strong>{m.role}</strong>
          <p>{m.content_markdown}</p>
        </div>
      ))}
    </main>
  );
}
