import React from "react";

const suggestions = [
  {
    eyebrow: "SE CONCENTRER",
    title: "La méthode Pomodoro",
    question: "Que conseille le livre sur la technique Pomodoro ?",
    icon: "◷",
    tone: "lavender",
  },
  {
    eyebrow: "FAIRE LES BONS CHOIX",
    title: "Éviter la dette",
    question: "Comment le livre recommande-t-il d'éviter la dette ?",
    icon: "↗",
    tone: "mint",
  },
  {
    eyebrow: "FAIRE CARRIÈRE",
    title: "La série A",
    question: "Que faut-il savoir sur le financement de série A ?",
    icon: "✳",
    tone: "peach",
  },
  {
    eyebrow: "SE FAIRE CONNAÎTRE",
    title: "Lancer un blog",
    question: "Quels conseils le livre donne-t-il pour lancer un blog ?",
    icon: "⌁",
    tone: "blue",
  },
];

export default function Welcome({ onAsk }) {
  return (
    <section className="welcome" aria-labelledby="welcome-title">
      <div className="welcome-orbit" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="eyebrow welcome-eyebrow">
        <span className="eyebrow-line" />
        LE LIVRE, À VOTRE RYTHME
      </div>
      <h1 id="welcome-title">
        Les bonnes idées,
        <br />
        <span>à portée de question.</span>
      </h1>
      <p className="welcome-description">
        Explorez <em>Soft Skills: The Software Developer’s Life Manual</em>.
        Posez une question, le livre vous répond avec ses propres mots.
      </p>

      <div className="suggestion-heading">
        <span>Pour commencer</span>
        <span className="suggestion-hint">Choisissez une piste</span>
      </div>
      <div className="suggestion-grid">
        {suggestions.map((suggestion, index) => (
          <button
            className={`suggestion-card tone-${suggestion.tone}`}
            key={suggestion.title}
            onClick={() => onAsk(suggestion.question)}
            style={{ "--card-delay": `${index * 70}ms` }}
          >
            <span className="suggestion-icon" aria-hidden="true">
              {suggestion.icon}
            </span>
            <span className="suggestion-copy">
              <span className="suggestion-eyebrow">{suggestion.eyebrow}</span>
              <strong>{suggestion.title}</strong>
            </span>
            <span className="suggestion-arrow" aria-hidden="true">
              ↗
            </span>
          </button>
        ))}
      </div>
      <div className="welcome-note">
        <span className="note-sparkle" aria-hidden="true">✦</span>
        Ancré dans le livre. Toujours sourcé.
      </div>
    </section>
  );
}
