import "./ui.css";

function Ui({
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
}) {
  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-left">
          <div className="brand-icon">🎥</div>
          <div>
            <div className="brand-title">Google Meet Clone UI</div>
            <div className="brand-subtitle">ASL Accessibility Demo</div>
          </div>
        </div>

        <div className="topbar-right">
          <span className="top-pill">{timeNow}</span>
          <span className="top-pill">abc-defg-hij</span>
          <span className={`top-pill ${connected ? "success" : "muted"}`}>
            {connected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </header>

      <main className="main-layout">
        <section className="video-area">
          <div className="main-video-card">
            <div className="main-video-header">
              <span>You</span>
              <span className="role-badge">Presenter</span>
            </div>

            <div className="video-frame">
              {cameraOn ? (
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="video-element"
                />
              ) : (
                <div className="camera-off-state">
                  <div className="camera-off-icon">📷</div>
                  <div>Camera is turned off</div>
                </div>
              )}

              <div className="video-overlay-name">You</div>

              {aslEnabled && showCaptions && cameraOn && (
                <div className="asl-overlay">
                  <div className="asl-overlay-title">ASL</div>
                  <div className="asl-overlay-text">{prediction}</div>
                  <div className="asl-overlay-confidence">
                    Confidence: {confidence.toFixed(2)}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="participants-row">
            <div className="mini-card">
              <div className="mini-video">
                <div className="avatar">A</div>
              </div>
              <div className="mini-name">Alex</div>
              <div className="mini-role">Participant</div>
            </div>

            <div className="mini-card">
              <div className="mini-video">
                <div className="avatar">S</div>
              </div>
              <div className="mini-name">Sara</div>
              <div className="mini-role">Participant</div>
            </div>
          </div>
        </section>

        <aside className="side-panel">
          <div className="side-tabs">
            <button
              className={activeTab === "captions" ? "tab active" : "tab"}
              onClick={() => onSetActiveTab("captions")}
            >
              Captions
            </button>
            <button
              className={activeTab === "people" ? "tab active" : "tab"}
              onClick={() => onSetActiveTab("people")}
            >
              People
            </button>
            <button
              className={activeTab === "chat" ? "tab active" : "tab"}
              onClick={() => onSetActiveTab("chat")}
            >
              Chat
            </button>
          </div>

          {activeTab === "captions" && (
            <div className="panel-content">
              <div className="status-chip">
                {aslEnabled ? "Translator ON" : "Translator OFF"}
              </div>

              <div className="info-box">
                <div className="info-label">Latest recognized sign</div>
                <div className="info-value">
                  {showCaptions ? prediction : "Hidden"}
                </div>
              </div>

              <div className="info-box">
                <div className="info-label">Recognition status</div>
                <div className="info-value small">{status}</div>
              </div>

              <div className="info-box">
                <div className="info-label">Confidence</div>
                <div className="info-value small">{confidence.toFixed(2)}</div>
              </div>

              <div className="helper-text">
                Your React UI is sending camera frames to the Python backend.
                The backend runs MediaPipe + your phrase model and returns live
                prediction data here.
              </div>
            </div>
          )}

          {activeTab === "people" && (
            <div className="panel-content">
              <div className="person-item">
                <div className="person-avatar">Y</div>
                <div>
                  <div className="person-name">You</div>
                  <div className="person-meta">Presenter</div>
                </div>
              </div>

              <div className="person-item">
                <div className="person-avatar">A</div>
                <div>
                  <div className="person-name">Alex</div>
                  <div className="person-meta">Participant</div>
                </div>
              </div>

              <div className="person-item">
                <div className="person-avatar">S</div>
                <div>
                  <div className="person-name">Sara</div>
                  <div className="person-meta">Participant</div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "chat" && (
            <div className="panel-content">
              <div className="chat-box">
                <div className="chat-user">System</div>
                <div className="chat-message">
                  Messages are only visible to people in this call.
                </div>
              </div>

              <div className="chat-box">
                <div className="chat-user">Alex</div>
                <div className="chat-message">Looks good. Start the demo.</div>
              </div>
            </div>
          )}
        </aside>
      </main>

      <footer className="bottom-bar">
        <button className="control-btn" onClick={onToggleMic}>
          {micOn ? "🎤 Mic On" : "🎤 Mic Off"}
        </button>

        <button className="control-btn" onClick={onToggleCamera}>
          {cameraOn ? "📷 Camera On" : "📷 Camera Off"}
        </button>

        <button className="control-btn" onClick={onToggleCaptions}>
          {showCaptions ? "📝 Captions On" : "📝 Captions Off"}
        </button>

        <button className="control-btn" onClick={onToggleAsl}>
          {aslEnabled ? "🌐 ASL On" : "🌐 ASL Off"}
        </button>

        <button className="end-btn">📞 End Call</button>
      </footer>

      <canvas ref={canvasRef} style={{ display: "none" }} />
    </div>
  );
}

export default Ui;