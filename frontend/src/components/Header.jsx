import React from "react";

function ThemeIcon({ theme }) {
  return theme === "dark" ? (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20.3 15.4A8.5 8.5 0 0 1 8.6 3.7 8.5 8.5 0 1 0 20.3 15.4Z" />
    </svg>
  );
}

export default function Header({
  health,
  theme,
  onToggleTheme,
  onNewConversation,
  bookAvailable,
  onOpenBook,
  sidebarOpen,
  onToggleSidebar,
}) {
  const online = health.status === "online";
  const healthLabel = online
    ? `${health.chunks ?? 0} passages indexés`
    : health.status === "checking"
      ? "Connexion au livre…"
      : "Serveur injoignable";

  return (
    <header className="topbar glass-panel">
      <a className="brand" href="#" aria-label="Accueil, Compagnon de lecture">
        <span className="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 32 32">
            <path d="M7 6.5c4.2-.8 7.2.1 9 2.4v16c-1.8-2.3-4.8-3.2-9-2.4v-16Zm18 0c-4.2-.8-7.2.1-9 2.4v16c1.8-2.3 4.8-3.2 9-2.4v-16Z" />
          </svg>
        </span>
        <span className="brand-copy">
          <strong>Marginalia</strong>
          <small>Votre compagnon de lecture</small>
        </span>
      </a>

      <div className="topbar-actions">
        <button
          className={`icon-button sidebar-toggle ${sidebarOpen ? "is-selected" : ""}`}
          type="button"
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? "Fermer l’historique" : "Ouvrir l’historique"}
          aria-expanded={sidebarOpen}
          aria-controls="conversation-sidebar"
          title={sidebarOpen ? "Fermer l’historique" : "Historique"}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
            <path d="M9 5v14" />
          </svg>
        </button>
        {bookAvailable && (
          <button
            className="book-button"
            type="button"
            onClick={onOpenBook}
            aria-label="Ouvrir le livre"
            title="Le livre"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4.5 5.5c3.4-.7 5.9 0 7.5 1.8v12c-1.6-1.8-4.1-2.5-7.5-1.8v-12Zm15 0c-3.4-.7-5.9 0-7.5 1.8v12c1.6-1.8 4.1-2.5 7.5-1.8v-12Z" />
            </svg>
            <span>Le livre</span>
          </button>
        )}
        <div
          className={`health-pill ${online ? "is-online" : ""} ${health.status === "checking" ? "is-checking" : ""}`}
          role="status"
          aria-live="polite"
          title={healthLabel}
        >
          <span className="health-dot" />
          <span>{healthLabel}</span>
        </div>
        <button
          className="icon-button"
          onClick={onNewConversation}
          aria-label="Nouvelle conversation"
          title="Nouvelle conversation"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>
        <button
          className="icon-button"
          onClick={onToggleTheme}
          aria-label={`Activer le thème ${theme === "dark" ? "clair" : "sombre"}`}
          title={`Thème ${theme === "dark" ? "clair" : "sombre"}`}
        >
          <ThemeIcon theme={theme} />
        </button>
      </div>
    </header>
  );
}
