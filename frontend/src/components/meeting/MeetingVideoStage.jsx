import { FiVideoOff } from "react-icons/fi";

function MeetingVideoStage({
  videoRef,
  cameraOn,
  aslEnabled,
  showCaptions,
  prediction,
  confidence,
  translationWords,
}) {
  const trayVisible = aslEnabled && showCaptions;

  return (
    <section className={`video-area ${trayVisible ? "asl-tray-open" : ""}`}>
      <div className="main-video-container">
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
        </div>
      </div>

      <div className={`translation-tray ${trayVisible ? "visible" : ""}`}>
        <div className="translation-tray-header">
          <div className="translation-tray-title">Live Translation</div>
          <div className="translation-tray-subtitle">
            Words appear here as they are confirmed.
          </div>
        </div>

        <div className="translation-word-list">
          {translationWords.length > 0 ? (
            translationWords.map((word, index) => (
              <span key={`${word}-${index}`} className="translation-word-chip">
                {word}
              </span>
            ))
          ) : (
            <div className="translation-empty-state">
              Start signing to build your translated phrase.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export default MeetingVideoStage;
