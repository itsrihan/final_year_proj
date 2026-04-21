function MeetingVideoStage({
  videoRef,
  cameraOn,
  aslEnabled,
  showCaptions,
  prediction,
  confidence,
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
              <div className="camera-off-icon">📷</div>
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
    </section>
  );
}

export default MeetingVideoStage;
