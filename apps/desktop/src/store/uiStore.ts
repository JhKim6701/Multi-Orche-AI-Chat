import { create } from 'zustand';

export type ExecutionMode = 'independent' | 'chained' | 'ordered';

interface UiState {
  orchestratorOn: boolean;
  executionMode: ExecutionMode;
  selectedProjectId?: number;
  selectedChatId?: number;
  selectedModelNames: string[];
  toggleOrchestrator: () => void;
  setExecutionMode: (mode: ExecutionMode) => void;
  setSelectedProject: (id?: number) => void;
  setSelectedChat: (id?: number) => void;
  toggleSelectedModel: (name: string) => void;
}

const load = <T,>(key: string, fallback: T): T => {
  const raw = localStorage.getItem(key);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
};

export const useUiStore = create<UiState>((set, get) => ({
  orchestratorOn: load('orchestratorOn', false),
  executionMode: load<ExecutionMode>('executionMode', 'independent'),
  selectedProjectId: load<number | undefined>('selectedProjectId', undefined),
  selectedChatId: load<number | undefined>('selectedChatId', undefined),
  selectedModelNames: load<string[]>('selectedModelNames', []),

  toggleOrchestrator: () => {
    const next = !get().orchestratorOn;
    localStorage.setItem('orchestratorOn', JSON.stringify(next));
    set({ orchestratorOn: next });
  },
  setExecutionMode: (mode) => {
    localStorage.setItem('executionMode', JSON.stringify(mode));
    set({ executionMode: mode });
  },
  setSelectedProject: (id) => {
    localStorage.setItem('selectedProjectId', JSON.stringify(id));
    set({ selectedProjectId: id });
  },
  setSelectedChat: (id) => {
    localStorage.setItem('selectedChatId', JSON.stringify(id));
    set({ selectedChatId: id });
  },
  toggleSelectedModel: (name) => {
    const exists = get().selectedModelNames.includes(name);
    const next = exists ? get().selectedModelNames.filter((x) => x !== name) : [...get().selectedModelNames, name];
    localStorage.setItem('selectedModelNames', JSON.stringify(next));
    set({ selectedModelNames: next });
  }
}));
