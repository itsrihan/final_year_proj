import { FiVideoOff } from "react-icons/fi";

function MeetingVideoStage({
  videoRef,
  cameraOn,
  micOn,
  aslEnabled,
  showCaptions,
  prediction,
  confidence,
  handsCount = 0,
  aslCaptureState,
  manualCaptureState,
  countdownMs = 0,
  micLevel = 0,
}) {
  const text = typeof prediction === "string" ? prediction.trim() : "";
  const isTranslating = text === "Translating...";
  const isWaiting = text === "Waiting...";
  const isSpecial =
    !text ||
    isTranslating ||
    isWaiting ||
    text === "ASL off" ||
    text === "Model unavailable" ||
    text.toLowerCase() === "null";
  const isDoneTranslating = !isSpecial && confidence > 0;

  let indicatorState = "off";
  if (cameraOn && aslEnabled) {
    if (aslCaptureState === "manual") {
      // Manual mode: derive ring from manualCaptureState
      if (countdownMs > 0) {
        indicatorState = "translating";  // Red during countdown
      } else if (manualCaptureState === "manual_capturing" || manualCaptureState === "manual_predicting") {
        indicatorState = "translating";  // Red
      } else if (manualCaptureState === "manual_result") {
        indicatorState = "hand-detected";  // Amber
      } else {
        indicatorState = "ready";  // Green = manual_ready
      }
    } else if (aslCaptureState === "ready") {
      indicatorState = "ready";  // Green
    } else if (aslCaptureState === "capturing") {
      indicatorState = "translating";  // Red
    } else if (aslCaptureState === "predicting") {
      indicatorState = "translating";  // Red
    } else if (aslCaptureState === "wait_for_release") {
      indicatorState = "hand-detected";  // Amber
    }
  }
  return (
    <section className="video-area">
      <div className="main-video-container">
        <div className={`video-frame asl-indicator asl-indicator-${indicatorState}`}>
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
              <FiVideoOff className="camera-off-icon" />
              <div>Camera is turned off</div>
            </div>
          )}

          <div className="video-overlay-name">You • Presenter</div>

          {aslEnabled && showCaptions && cameraOn && (
            <div className="asl-overlay">
              <div className="asl-overlay-title">ASL Recognition</div>
              <div className="asl-overlay-text">{prediction}</div>
              <div className="asl-overlay-confidence">
                Confidence: {confidence.toFixed(2)}
              </div>
            </div>
          )}

          {micOn && (
            <div className="mic-wave" aria-hidden="true">
              {[0.2, 0.45, 0.75, 1, 0.75, 0.45, 0.2].map((multiplier, index) => (
                <span
                  key={index}
                  className="mic-wave-bar"
                  style={{
                    height: `${Math.max(10, 10 + micLevel * multiplier * 32)}px`,
                    opacity: 0.35 + micLevel * 0.65,
                  }}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export default MeetingVideoStage;