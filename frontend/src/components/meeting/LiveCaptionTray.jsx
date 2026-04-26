function LiveCaptionTray({ visible, translationWords }) {
  const translatedText = translationWords.join(" ");
  const isEmpty = !translatedText;

  return (
    <section className={`live-caption-tray ${visible ? "visible" : ""}`}>
      <div className="live-caption-label">Live ASL Translation</div>

      <div className={`live-caption-text ${isEmpty ? "empty" : ""}`}>
        {translatedText || "Start signing..."}
      </div>
    </section>
  );
}

export default LiveCaptionTray;