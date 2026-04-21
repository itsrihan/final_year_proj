function MeetingTopBar({ timeNow, connected, theme, onThemeToggle }) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="brand-icon">🎥</div>
        <div>
          <div className="brand-title">Meeting</div>
          <div className="brand-subtitle">ASL Accessibility</div>
        </div>
      </div>

      <div className="topbar-right">
        <span className="top-pill">{timeNow}</span>
        <span className={`top-pill ${connected ? "success" : "muted"}`}>
          {connected ? "Connected" : "Disconnected"}
        </span>
        <button className="theme-toggle" onClick={onThemeToggle} title="Toggle theme">
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
      </div>
    </header>
  );
}

export default MeetingTopBar;
