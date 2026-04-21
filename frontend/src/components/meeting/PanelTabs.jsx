function PanelTabs({ activeTab, onSetActiveTab }) {
  const tabs = [
    ["captions", "Captions"],
    ["people", "People"],
    ["chat", "Chat"],
  ];

  return (
    <div className="side-tabs">
      {tabs.map(([key, label]) => (
        <button
          key={key}
          className={activeTab === key ? "tab active" : "tab"}
          onClick={() => onSetActiveTab(key)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export default PanelTabs;
