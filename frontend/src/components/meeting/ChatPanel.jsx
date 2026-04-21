const messages = [
  { user: "System", message: "Messages are only visible to people in this call." },
  { user: "Alex", message: "Looks good. Start the demo." },
];

function ChatPanel() {
  return (
    <div className="panel-content">
      {messages.map((item) => (
        <div className="chat-box" key={`${item.user}-${item.message}`}>
          <div className="chat-user">{item.user}</div>
          <div className="chat-message">{item.message}</div>
        </div>
      ))}
    </div>
  );
}

export default ChatPanel;
