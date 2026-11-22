import React, { useEffect, useRef } from "react";

export default function Composer({
  value,
  onChange,
  onSubmit,
  onStop,
  isGenerating,
}) {
  const textareaRef = useRef(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
    textarea.style.overflowY = textarea.scrollHeight > 180 ? "auto" : "hidden";
  }, [value]);

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <div className="composer-dock">
      <form
        className="composer glass-panel"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <label className="sr-only" htmlFor="question-input">
          Votre question
        </label>
        <textarea
          id="question-input"
          ref={textareaRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Posez une question sur le livre…"
          rows={1}
          maxLength={1000}
          disabled={isGenerating}
          aria-describedby="composer-hint"
        />
        <div className="composer-footer">
          <span id="composer-hint" className="composer-hint">
            <kbd>↵</kbd> envoyer <span className="hint-divider">·</span>{" "}
            <kbd>⇧ ↵</kbd> nouvelle ligne
          </span>
          {isGenerating ? (
            <button
              className="send-button stop-button"
              type="button"
              onClick={onStop}
              aria-label="Arrêter la génération"
            >
              <span className="stop-square" />
              Arrêter
            </button>
          ) : (
            <button
              className="send-button"
              type="submit"
              disabled={!value.trim()}
              aria-label="Envoyer la question"
            >
              Envoyer
              <svg viewBox="0 0 20 20" aria-hidden="true">
                <path d="M4 10h11m-4-4 4 4-4 4" />
              </svg>
            </button>
          )}
        </div>
      </form>
      <p className="composer-disclaimer">
        Les réponses s’appuient uniquement sur le contenu du livre.
      </p>
    </div>
  );
}
