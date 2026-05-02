import { useMemo, useState } from "react";
import { getSignVideoPath } from "../data/signLexicons";
import { textToSignWords } from "../data/signGrammar";

export function useTextToSign() {
  const [signLanguage, setSignLanguage] = useState("asl");
  const [inputText, setInputText] = useState("");
  const [signQueue, setSignQueue] = useState([]);
  const [missingWords, setMissingWords] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  const currentWord = signQueue[currentIndex] || null;

  const currentVideoSrc = useMemo(() => {
    if (!currentWord) return null;
    return getSignVideoPath(signLanguage, currentWord);
  }, [signLanguage, currentWord]);

  function handleSubmit() {
    const trimmed = inputText.trim();
    if (!trimmed) return;

    const result = textToSignWords(trimmed);

    setSignQueue(result.selected);
    setMissingWords(result.missing);
    setCurrentIndex(0);
  }

  function handleVideoEnded() {
    setCurrentIndex((prev) => {
      if (prev + 1 >= signQueue.length) return prev;
      return prev + 1;
    });
  }

  function resetTextToSign() {
    setInputText("");
    setSignQueue([]);
    setMissingWords([]);
    setCurrentIndex(0);
  }

  return {
    signLanguage,
    setSignLanguage,
    inputText,
    setInputText,
    signQueue,
    missingWords,
    currentIndex,
    currentWord,
    currentVideoSrc,
    handleSubmit,
    handleVideoEnded,
    resetTextToSign,
  };
}
