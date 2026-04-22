import { useState } from "react";

function FloatingParticipant({ visible = true, name = "Demo", initial = "D" }) {
  const [isPinned, setIsPinned] = useState(false);

  if (!visible) {
    return null;
  }

  return (
    <div className={`secondary-video-window ${isPinned ? "pinned" : ""}`}>
      <div className="video-window-header">
        <span className="participant-name">{name}</span>
        <button
          className="pin-toggle"
          onClick={() => setIsPinned(!isPinned)}
          title={isPinned ? "Unpin" : "Pin participant"}
        >
          {isPinned ? "📌" : "📍"}
        </button>
      </div>
      <div className="video-window-content">
        <div className="participant-video-placeholder">
          <div className="video-avatar">{initial}</div>
          <div className="participant-status">
            <span className="status-dot online"></span>
            <span className="status-text">Connected</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default FloatingParticipant;
