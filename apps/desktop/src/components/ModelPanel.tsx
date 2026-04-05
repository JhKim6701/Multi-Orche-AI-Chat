import { useQuery } from '@tanstack/react-query';

import { getJson } from '../lib/api';
import { useUiStore } from '../store/uiStore';

type Model = { id: number; model_name: string; downloaded: boolean; enabled: boolean };

export function ModelPanel() {
  const orchestratorOn = useUiStore((s) => s.orchestratorOn);
  const toggle = useUiStore((s) => s.toggleOrchestrator);
  const { data } = useQuery({ queryKey: ['models'], queryFn: () => getJson<Model[]>('/models') });

  return (
    <aside style={{ padding: 8 }}>
      <h3>Models</h3>
      <button onClick={toggle}>Orchestrator: {orchestratorOn ? 'ON' : 'OFF'}</button>
      {(data ?? []).map((m) => (
        <div key={m.id} style={{ padding: 6, borderBottom: '1px solid #eee' }}>
          <div>{m.model_name}</div>
          <small>{m.downloaded ? 'downloaded' : 'not downloaded'} / {m.enabled ? 'enabled' : 'disabled'}</small>
        </div>
      ))}
    </aside>
  );
}
