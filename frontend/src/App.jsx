import { useEffect, useRef, useState } from "react";

const WS_URL = "ws://localhost:8000/ws/asl";

function App() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const socketRef = useRef(null);
  const streamRef = useRef(null);

  const [connected, setConnected] = useState(false);
  const [cameraOn, setCameraOn] = useState(true);
  const [micOn, setMicOn] = useState(true);
  const [aslEnabled, setAslEnabled] = useState(true);
  const [showCaptions, setShowCaptions] = useState(true);
  const [activeTab, setActiveTab] = useState("captions");
  const [prediction, setPrediction] = useState("Waiting...");
  const [confidence, setConfidence] = useState(0);
  const [status, setStatus] = useState("Starting...");
  const [timeNow, setTimeNow] = useState("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeNow(
        now.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })
      );
    };

    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    startCamera();
    connectWebSocket();

    return () => {
      stopCamera();
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, []);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: false,
      });

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }

      setStatus("Camera active");
      setCameraOn(true);
    } catch (error) {
      console.error(error);
      setStatus("Camera permission denied");
      setCameraOn(false);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  const toggleCamera = async () => {
    if (cameraOn) {
      stopCamera();
      setCameraOn(false);
      setStatus("Camera off");
      setPrediction("Waiting...");
      setConfidence(0);
    } else {
      await startCamera();
    }
  };

  const connectWebSocket = () => {
    const socket = new WebSocket(WS_URL);
    socketRef.current = socket;

    socket.onopen = () => {
      setConnected(true);
      setStatus("Backend connected");
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setPrediction(data.text || "Waiting...");
      setConfidence(data.confidence || 0);
      setStatus(data.status || "Idle");
    };

    socket.onerror = () => {
      setConnected(false);
      setStatus("WebSocket error");
    };

    socket.onclose = () => {
      setConnected(false);
      setStatus("Backend disconnected");
    };
  };

  useEffect(() => {
    const interval = setInterval(() => {
      if (!cameraOn) return;
      if (!videoRef.current) return;
      if (!canvasRef.current) return;
      if (!socketRef.current) return;
      if (socketRef.current.readyState !== WebSocket.OPEN) return;

      const video = videoRef.current;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d");

      if (!video.videoWidth || !video.videoHeight) return;

      canvas.width = 320;
      canvas.height = 240;

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      const frame = canvas.toDataURL("image/jpeg", 0.7);

      socketRef.current.send(
        JSON.stringify({
          frame,
          asl_enabled: aslEnabled,
        })
      );
    }, 150);

    return () => clearInterval(interval);
  }, [cameraOn, aslEnabled]);

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
              onClick={() => setActiveTab("captions")}
            >
              Captions
            </button>
            <button
              className={activeTab === "people" ? "tab active" : "tab"}
              onClick={() => setActiveTab("people")}
            >
              People
            </button>
            <button
              className={activeTab === "chat" ? "tab active" : "tab"}
              onClick={() => setActiveTab("chat")}
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
                <div className="info-value">{showCaptions ? prediction : "Hidden"}</div>
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
        <button className="control-btn" onClick={() => setMicOn((prev) => !prev)}>
          {micOn ? "🎤 Mic On" : "🎤 Mic Off"}
        </button>

        <button className="control-btn" onClick={toggleCamera}>
          {cameraOn ? "📷 Camera On" : "📷 Camera Off"}
        </button>

        <button
          className="control-btn"
          onClick={() => setShowCaptions((prev) => !prev)}
        >
          {showCaptions ? "📝 Captions On" : "📝 Captions Off"}
        </button>

        <button
          className="control-btn"
          onClick={() => setAslEnabled((prev) => !prev)}
        >
          {aslEnabled ? "🌐 ASL On" : "🌐 ASL Off"}
        </button>

        <button className="end-btn">📞 End Call</button>
      </footer>

      <canvas ref={canvasRef} style={{ display: "none" }} />
    </div>
  );
}

export default App;