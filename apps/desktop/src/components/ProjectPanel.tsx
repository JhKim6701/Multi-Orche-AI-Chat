import { useQuery } from '@tanstack/react-query';

import { getJson } from '../lib/api';
import { useUiStore } from '../store/uiStore';

type Project = { id: number; name: string };

export function ProjectPanel() {
  const { data } = useQuery({ queryKey: ['projects'], queryFn: () => getJson<Project[]>('/projects') });
  const setProject = useUiStore((s) => s.setSelectedProject);

  return (
    <aside style={{ padding: 8 }}>
      <h3>Projects</h3>
      {(data ?? []).map((p) => (
        <button key={p.id} style={{ display: 'block', width: '100%', marginBottom: 6 }} onClick={() => setProject(p.id)}>
          {p.name}
        </button>
      ))}
    </aside>
  );
}
