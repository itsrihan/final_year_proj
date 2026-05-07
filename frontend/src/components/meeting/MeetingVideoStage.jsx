import { FiVideoOff } from "react-icons/fi";

function MeetingVideoStage({
  videoRef,
  cameraOn,
  micOn,
  aslEnabled,
  showCaptions,
  prediction,
  confidence,
  micLevel = 0,
}) {
  return (
    <section className="video-area">
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