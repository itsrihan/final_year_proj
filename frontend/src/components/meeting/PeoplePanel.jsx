const people = [
  { initial: "Y", name: "You", meta: "Presenter" },
  { initial: "A", name: "Alex", meta: "Participant" },
];

function PeoplePanel() {
  return (
    <div className="panel-content">
      {people.map((person) => (
        <div className="person-item" key={person.name}>
          <div className="person-avatar">{person.initial}</div>
          <div className="person-details">
            <div className="person-name">{person.name}</div>
            <div className="person-meta">{person.meta}</div>
          </div>
          <div className={`status-indicator ${person.name === "You" ? "active" : "online"}`} />
        </div>
      ))}
    </div>
  );
}

export default PeoplePanel;
