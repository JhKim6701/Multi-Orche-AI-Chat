import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FormEvent, useMemo, useState } from 'react';

import { api } from '../lib/api';
import { useUiStore } from '../store/uiStore';
import { ChatThread, Project } from '../types/domain';

export function ProjectPanel() {
  const qc = useQueryClient();
  const [projectName, setProjectName] = useState('');
  const [chatTitle, setChatTitle] = useState('');
  const selectedProjectId = useUiStore((s) => s.selectedProjectId);
  const selectedChatId = useUiStore((s) => s.selectedChatId);
  const setProject = useUiStore((s) => s.setSelectedProject);
  const setChat = useUiStore((s) => s.setSelectedChat);

  const { data: projects = [], isLoading: projectsLoading } = useQuery({ queryKey: ['projects'], queryFn: () => api.get<Project[]>('/projects') });

  const { data: chats = [], isLoading: chatsLoading } = useQuery({
    queryKey: ['chats', selectedProjectId],
    queryFn: () => api.get<ChatThread[]>(`/chats?project_id=${selectedProjectId}`),
    enabled: !!selectedProjectId
  });

  const createProject = useMutation({
    mutationFn: (name: string) => api.post<Project>('/projects', { name, description: null }),
    onSuccess: () => {
      setProjectName('');
      qc.invalidateQueries({ queryKey: ['projects'] });
    }
  });

  const deleteProject = useMutation({
    mutationFn: (projectId: number) => api.delete<{ ok: boolean }>(`/projects/${projectId}`),
    onSuccess: () => {
      setProject(undefined);
      setChat(undefined);
      qc.invalidateQueries({ queryKey: ['projects'] });
      qc.invalidateQueries({ queryKey: ['chats'] });
      qc.invalidateQueries({ queryKey: ['messages'] });
    }
  });

  const createChat = useMutation({
    mutationFn: () => api.post<ChatThread>('/chats', { project_id: selectedProjectId, title: chatTitle || 'New Chat' }),
    onSuccess: (chat) => {
      setChatTitle('');
      setChat(chat.id);
      qc.invalidateQueries({ queryKey: ['chats', selectedProjectId] });
    }
  });

  const deleteChat = useMutation({
    mutationFn: (chatId: number) => api.delete<{ ok: boolean }>(`/chats/${chatId}`),
    onSuccess: () => {
      setChat(undefined);
      qc.invalidateQueries({ queryKey: ['chats', selectedProjectId] });
      qc.invalidateQueries({ queryKey: ['messages'] });
    }
  });

  const selectedProject = useMemo(() => projects.find((p) => p.id === selectedProjectId), [projects, selectedProjectId]);

  const onCreateProject = (e: FormEvent) => {
    e.preventDefault();
    if (!projectName.trim()) return;
    createProject.mutate(projectName.trim());
  };

  return (
    <aside style={{ padding: 8, height: '100%', overflow: 'auto', borderRight: '1px solid #eee' }}>
      <h3 style={{ margin: '4px 0' }}>Projects</h3>
      <form onSubmit={onCreateProject} style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
        <input value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder="New project" style={{ flex: 1, fontSize: 12 }} />
        <button type="submit" style={{ fontSize: 12 }}>+</button>
      </form>

      {projectsLoading ? <p>Loading...</p> : projects.length === 0 ? <p>No projects</p> : null}
      {projects.map((p) => (
        <div key={p.id} style={{ display: 'flex', gap: 4, marginBottom: 4 }}>
          <button
            style={{ flex: 1, fontSize: 12, background: p.id === selectedProjectId ? '#e8f0ff' : '#fff' }}
            onClick={() => {
              setProject(p.id);
              setChat(undefined);
            }}
          >
            {p.name}
          </button>
          <button style={{ fontSize: 11 }} onClick={() => deleteProject.mutate(p.id)}>x</button>
        </div>
      ))}

      <hr style={{ margin: '10px 0' }} />
      <h4 style={{ margin: '4px 0' }}>Chats</h4>
      {selectedProject ? (
        <>
          <form onSubmit={(e) => { e.preventDefault(); createChat.mutate(); }} style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
            <input value={chatTitle} onChange={(e) => setChatTitle(e.target.value)} placeholder="New chat" style={{ flex: 1, fontSize: 12 }} />
            <button type="submit" style={{ fontSize: 12 }}>+</button>
          </form>
          {chatsLoading ? <p>Loading chats...</p> : chats.length === 0 ? <p>No chats</p> : null}
          {chats.map((c) => (
            <div key={c.id} style={{ display: 'flex', gap: 4, marginBottom: 4 }}>
              <button
                style={{ flex: 1, fontSize: 12, background: c.id === selectedChatId ? '#eef8ee' : '#fff' }}
                onClick={() => setChat(c.id)}
              >
                {c.title}
              </button>
              <button style={{ fontSize: 11 }} onClick={() => deleteChat.mutate(c.id)}>x</button>
            </div>
          ))}
        </>
      ) : (
        <p style={{ fontSize: 12 }}>Select a project</p>
      )}
    </aside>
  );
}
