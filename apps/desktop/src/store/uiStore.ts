import { create } from 'zustand';

interface UiState {
  orchestratorOn: boolean;
  selectedProjectId?: number;
  selectedChatId?: number;
  toggleOrchestrator: () => void;
  setSelectedProject: (id: number) => void;
  setSelectedChat: (id: number) => void;
}

export const useUiStore = create<UiState>((set) => ({
  orchestratorOn: true,
  toggleOrchestrator: () => set((s) => ({ orchestratorOn: !s.orchestratorOn })),
  setSelectedProject: (id) => set({ selectedProjectId: id }),
  setSelectedChat: (id) => set({ selectedChatId: id })
}));
