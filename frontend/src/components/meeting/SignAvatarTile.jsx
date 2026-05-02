function SignAvatarTile({
  visible,
  videoSrc,
  currentWord,
  onEnded,
}) {
  if (!visible) return null;

  return (
    <div className="sign-avatar-tile">
      <div className="sign-avatar-video-wrap">
        {videoSrc ? (
          <video
            className="sign-avatar-video"
            src={videoSrc}
            autoPlay
            muted
            playsInline
            preload="auto"
            onEnded={onEnded}
          />
        ) : (
          <div className="sign-avatar-empty">
            Type a sentence to generate signs
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