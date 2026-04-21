import CaptionsPanel from "./CaptionsPanel";
import ChatPanel from "./ChatPanel";
import PanelTabs from "./PanelTabs";
import PeoplePanel from "./PeoplePanel";

function SidePanel({
  activeTab,
  aslEnabled,
  showCaptions,
  prediction,
  confidence,
  status,
  onSetActiveTab,
  onClose,
}) {
  return (
    <aside className="side-panel">
      <div className="panel-header">
        <PanelTabs activeTab={activeTab} onSetActiveTab={onSetActiveTab} />
        <button className="panel-close" onClick={onClose}>✕</button>
      </div>

      {activeTab === "captions" && (
        <CaptionsPanel
          aslEnabled={aslEnabled}
          showCaptions={showCaptions}
          prediction={prediction}
          confidence={confidence}
          status={status}
        />
      )}

      {activeTab === "people" && <PeoplePanel />}

      {activeTab === "chat" && <ChatPanel />}
    </aside>
  );
}

export default SidePanel;
