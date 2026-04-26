import { useState } from "react";
import { FiMoon, FiSun } from "react-icons/fi";
import ControlsBar from "./ControlsBar";
import MeetingVideoStage from "./MeetingVideoStage";
import SidePanel from "./SidePanel";
import FloatingParticipant from "./FloatingParticipant";
import LiveCaptionTray from "./LiveCaptionTray";

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
  handsCount,
  translationWords,
  modelName,
  inferenceDevice,
  inferenceMode,
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
  const captionOpen = aslEnabled && showCaptions;

  return (
    <div className="app" data-theme={theme}>
      <main className={`main-layout ${panelOpen ? "panel-open" : ""}`}>
        <section className={`video-caption-layout ${captionOpen ? "caption-open" : ""}`}>
          <MeetingVideoStage
            videoRef={videoRef}
            cameraOn={cameraOn}
            aslEnabled={aslEnabled}
            showCaptions={showCaptions}
            prediction={prediction}
            confidence={confidence}
          />

          <LiveCaptionTray
            visible={captionOpen}
            translationWords={translationWords}
          />
        </section>

        {panelOpen && (
          <SidePanel
            activeTab={activeTab}
            aslEnabled={aslEnabled}
            showCaptions={showCaptions}
            prediction={prediction}
            confidence={confidence}
            handsCount={handsCount}
            modelName={modelName}
            inferenceDevice={inferenceDevice}
            inferenceMode={inferenceMode}
            status={status}
            onSetActiveTab={onSetActiveTab}
            onClose={() => setPanelOpen(false)}
          />
        )}
      </main>

      <div className="floating-meeting-info">
        <button className="theme-toggle-float" onClick={onThemeToggle} title="Toggle theme">
          {theme === "dark" ? <FiMoon size={18} /> : <FiSun size={18} />}
        </button>
        <div className="meeting-code">
          <span className="code-label">Code:</span>
          <span className="code-value">abc-defg-hij</span>
        </div>
      </div>

      <div className="floating-person you">
        <div className="person-avatar-float">Y</div>
        <div className="person-info-float">
          <div className="person-name-float">You</div>
          <div className={`status-dot ${connected ? "online" : "offline"}`} />
        </div>
      </div>

      <FloatingParticipant visible={!panelOpen} name="Alex" initial="A" />

      <ControlsBar
        micOn={micOn}
        cameraOn={cameraOn}
        aslEnabled={aslEnabled}
        onToggleMic={onToggleMic}
        onToggleCamera={onToggleCamera}
        onToggleAsl={onToggleAsl}
        onEndCall={() => {}}
        onOpenPanel={() => setPanelOpen(!panelOpen)}
        panelOpen={panelOpen}
      />

      <canvas ref={canvasRef} style={{ display: "none" }} />
    </div>
  );
}

export default MeetingLayout;