function CaptionsPanel({
  aslEnabled,
  showCaptions,
  prediction,
  status,
  confidence,
  handsCount,
  modelName,
  inferenceDevice,
  inferenceMode,
}) {
  return (
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

      <div className="info-box">
        <div className="info-label">Hands detected (frame)</div>
        <div className="info-value small">{handsCount}</div>
      </div>

      <div className="info-box">
        <div className="info-label">model name</div>
        <div className="info-value small">{modelName}</div>
      </div>

      <div className="info-box">
        <div className="info-label">Inference device</div>
        <div className="info-value small">{inferenceDevice}</div>
      </div>

      <div className="info-box">
        <div className="info-label">Inference mode</div>
        <div className="info-value small">{inferenceMode}</div>
      </div>

      <div className="helper-text">
        Your React UI is sending camera frames to the Python backend. The backend
        runs MediaPipe + your phrase model and returns live prediction data here.
      </div>
    </div>
  );
}

export default CaptionsPanel;
