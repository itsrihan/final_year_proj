import { useState } from "react";
import ControlsBar from "./ControlsBar";
import MeetingVideoStage from "./MeetingVideoStage";
import SidePanel from "./SidePanel";

function MeetingLayout({
  videoRef,
  canvasRef,
  connected,
  cameraOn,
  micOn,
  aslEnabled,
  showCaptions,
  activeTab,
  prediction,
  confidence,
  status,
  timeNow,
  onToggleMic,
  onToggleCamera,
  onToggleCaptions,
  onToggleAsl,
  onSetActiveTab,
  theme,
  onThemeToggle,
}) {
  const [panelOpen, setPanelOpen] = useState(false);

  return (
    <div className="app" data-theme={theme}>
      <main className={`main-layout ${panelOpen ? "panel-open" : ""}`}>
        <MeetingVideoStage
          videoRef={videoRef}
          cameraOn={cameraOn}
          aslEnabled={aslEnabled}
          showCaptions={showCaptions}
          prediction={prediction}
          confidence={confidence}
        />

        {panelOpen && (
          <SidePanel
            activeTab={activeTab}
            aslEnabled={aslEnabled}
            showCaptions={showCaptions}
            prediction={prediction}
            confidence={confidence}
            status={status}
            onSetActiveTab={onSetActiveTab}
            onClose={() => setPanelOpen(false)}
          />
        )}
      </main>

      {/* Floating meeting info */}
      <div className="floating-meeting-info">
        <div className="meeting-code">
          <span className="code-label">Code:</span>
          <span className="code-value">abc-defg-hij</span>
        </div>
        <button className="theme-toggle-float" onClick={onThemeToggle} title="Toggle theme">
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
      </div>

      {/* Floating you indicator */}
      <div className="floating-person you">
        <div className="person-avatar-float">Y</div>
        <div className="person-info-float">
          <div className="person-name-float">You</div>
          <div className={`status-dot ${connected ? "online" : "offline"}`} />
        </div>
      </div>

      {/* Floating other participant */}
      <div className="floating-person other">
        <div className="person-avatar-float">A</div>
        <div className="person-info-float">
          <div className="person-name-float">Alex</div>
          <div className="status-dot online" />
        </div>
      </div>

      <ControlsBar
        micOn={micOn}
        cameraOn={cameraOn}
        showCaptions={showCaptions}
        aslEnabled={aslEnabled}
        onToggleMic={onToggleMic}
        onToggleCamera={onToggleCamera}
        onToggleCaptions={onToggleCaptions}
        onToggleAsl={onToggleAsl}
        onOpenPanel={() => setPanelOpen(!panelOpen)}
        panelOpen={panelOpen}
      />

      <canvas ref={canvasRef} style={{ display: "none" }} />
    </div>
  );
}

export default MeetingLayout;
