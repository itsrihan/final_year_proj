function ControlButton({ children, onClick, variant = "default", tooltip, className = "" }) {
  const baseClassName = variant === "danger" ? "end-btn" : "control-btn";
  const combinedClassName = `${baseClassName} ${className}`.trim();

  return (
    <button className={combinedClassName} onClick={onClick} title={tooltip}>
      <span className="btn-icon">{children}</span>
      {tooltip && <span className="btn-tooltip">{tooltip}</span>}
    </button>
  );
}

export default ControlButton;
