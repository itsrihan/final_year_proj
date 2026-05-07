import { useEffect, useRef, useState } from "react";

function SignAvatarTile({
  visible,
  videoSrc,
  currentWord,
  onEnded,
  emptyMessage,
}) {
  const videoRef = useRef(null);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed, videoSrc]);

  if (!visible) return null;

  return (
    <div className="sign-avatar-tile">
      <div className="sign-avatar-speed-control">
        <span className="sign-avatar-speed-label">Speed</span>
        <select
          className="sign-avatar-speed-select"
          value={playbackSpeed}
          onChange={(event) => setPlaybackSpeed(Number(event.target.value))}
        >
          <option value={1}>1x</option>
          <option value={0.75}>0.75x</option>
          <option value={0.5}>0.5x</option>
          <option value={0.25}>0.25x</option>
        </select>
      </div>

      <div className="sign-avatar-video-wrap">
        {videoSrc ? (
          <video
            ref={videoRef}
            className="sign-avatar-video"
            src={videoSrc}
            autoPlay
            muted
            playsInline
            preload="auto"
            onLoadedMetadata={() => {
              if (videoRef.current) {
                videoRef.current.playbackRate = playbackSpeed;
              }
            }}
            onEnded={onEnded}
          />
        ) : (
          <div className="sign-avatar-empty">
            <img
              className="sign-avatar-empty-icon"
              src="/sign-videos/avatar_icon.png"
              alt="Sign avatar"
            />
          </div>
        )}
      </div>

      <div className="sign-avatar-label">
        Sign Avatar {currentWord ? `• ${currentWord}` : ""}
      </div>
    </div>
  );
}

export default SignAvatarTile;