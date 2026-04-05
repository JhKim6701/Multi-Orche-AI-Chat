import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';

import { ChatPanel } from './components/ChatPanel';
import { ModelPanel } from './components/ModelPanel';
import { ProjectPanel } from './components/ProjectPanel';
import { TopBar } from './components/TopBar';

export function App() {
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <TopBar />
      <PanelGroup direction="horizontal" autoSaveId="main-layout">
        <Panel defaultSize={20} minSize={15}>
          <ProjectPanel />
        </Panel>
        <PanelResizeHandle style={{ width: 4, background: '#efefef' }} />
        <Panel defaultSize={55} minSize={35}>
          <ChatPanel />
        </Panel>
        <PanelResizeHandle style={{ width: 4, background: '#efefef' }} />
        <Panel defaultSize={25} minSize={20}>
          <ModelPanel />
        </Panel>
      </PanelGroup>
    </div>
  );
}
