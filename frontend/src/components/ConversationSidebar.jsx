import React, { useMemo, useState } from "react";

const GROUPS = [
  "Aujourd'hui",
  "Hier",
  "7 derniers jours",
  "Plus ancien",
];

function dateGroup(value, now = new Date()) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Plus ancien";
  const today = new Date(now);
  today.setHours(0, 0, 0, 0);
  const day = new Date(date);
  day.setHours(0, 0, 0, 0);
  const daysAgo = Math.floor((today - day) / 86_400_000);
  if (daysAgo <= 0) return "Aujourd'hui";
  if (daysAgo === 1) return "Hier";
  if (daysAgo <= 7) return "7 derniers jours";
  return "Plus ancien";
}

function formattedDate(value, now = new Date()) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  if (dateGroup(value, now) === "Aujourd'hui") {
    return new Intl.DateTimeFormat("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
  }).format(date);
}

function ConversationItem({
  conversation,
  active,
  onSelect,
  onRename,
  onDelete,
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(conversation.title);

  function saveTitle() {
    const trimmed = title.trim();
    if (trimmed) onRename(conversation.id, trimmed);
    setEditing(false);
  }

  return (
    <div className={`conversation-item ${active ? "is-active" : ""}`}>
      {editing ? (
        <form
          className="conversation-rename-form"
          onSubmit={(event) => {
            event.preventDefault();
            saveTitle();
          }}
        >
          <label className="sr-only" htmlFor={`rename-${conversation.id}`}>
            Nouveau titre
          </label>
          <input
            id={`rename-${conversation.id}`}
            autoFocus
            value={title}
            maxLength={100}
            onChange={(event) => setTitle(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") setEditing(false);
            }}
          />
          <button type="submit" aria-label="Enregistrer le titre">
            OK
          </button>
        </form>
      ) : (
        <>
          <button
            className="conversation-select"
            type="button"
            onClick={() => onSelect(conversation.id)}
            aria-current={active ? "page" : undefined}
            title={conversation.title}
          >
            <span className="conversation-title">{conversation.title}</span>
            <time dateTime={conversation.updatedAt}>
              {formattedDate(conversation.updatedAt)}
            </time>
          </button>
          <details className="conversation-menu">
            <summary aria-label={`Options pour ${conversation.title}`} title="Options">
              <span aria-hidden="true">···</span>
            </summary>
            <div className="conversation-menu-popover">
              <button
                type="button"
                onClick={(event) => {
                  setTitle(conversation.title);
                  setEditing(true);
                  event.currentTarget.closest("details")?.removeAttribute("open");
                }}
              >
                Renommer
              </button>
              <button
                type="button"
                className="is-destructive"
                onClick={() => {
                  if (window.confirm("Supprimer cette conversation ?")) {
                    onDelete(conversation.id);
                  }
                }}
              >
                Supprimer
              </button>
            </div>
          </details>
        </>
      )}
    </div>
  );
}

export default function ConversationSidebar({
  open,
  conversations,
  activeConversationId,
  bookTitle,
  storageWarning,
  onClose,
  onNewConversation,
  onSelectConversation,
  onRenameConversation,
  onDeleteConversation,
  onClearAll,
}) {
  const [search, setSearch] = useState("");
  const groups = useMemo(() => {
    const filtered = conversations.filter((conversation) =>
      conversation.title.toLocaleLowerCase("fr").includes(search.toLocaleLowerCase("fr")),
    );
    return GROUPS.map((title) => ({
      title,
      conversations: filtered.filter(
        (conversation) => dateGroup(conversation.updatedAt) === title,
      ),
    })).filter((group) => group.conversations.length > 0);
  }, [conversations, search]);

  return (
    <>
      {open && (
        <button
          className="sidebar-backdrop"
          type="button"
          aria-label="Fermer la barre latérale"
          onClick={onClose}
        />
      )}
      <aside
        id="conversation-sidebar"
        className={`conversation-sidebar glass-panel ${open ? "is-open" : ""}`}
        aria-label="Historique des conversations"
        aria-hidden={!open}
        inert={!open}
      >
        <div className="sidebar-top">
          <button
            type="button"
            className="sidebar-new-button"
            onClick={onNewConversation}
            tabIndex={open ? 0 : -1}
          >
            <span aria-hidden="true">＋</span>
            Nouvelle conversation
          </button>
          <label className="sidebar-search">
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <circle cx="8.5" cy="8.5" r="5.5" />
              <path d="m13 13 4 4" />
            </svg>
            <input
              type="search"
              placeholder="Rechercher"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              tabIndex={open ? 0 : -1}
              aria-label="Rechercher une conversation"
            />
            <kbd>⌘ K</kbd>
          </label>
        </div>

        <div className="sidebar-list" aria-live="polite">
          {groups.length ? (
            groups.map((group) => (
              <section className="conversation-group" key={group.title}>
                <h2>{group.title}</h2>
                {group.conversations.map((conversation) => (
                  <ConversationItem
                    key={conversation.id}
                    conversation={conversation}
                    active={conversation.id === activeConversationId}
                    onSelect={onSelectConversation}
                    onRename={onRenameConversation}
                    onDelete={onDeleteConversation}
                  />
                ))}
              </section>
            ))
          ) : (
            <p className="sidebar-empty">
              {search ? "Aucune conversation trouvée." : "Vos conversations apparaîtront ici."}
            </p>
          )}
        </div>

        <div className="sidebar-bottom">
          {storageWarning && (
            <p className="storage-warning" role="status">
              La mémoire locale est indisponible ou pleine. Libérez de l’espace pour
              enregistrer vos échanges.
            </p>
          )}
          {conversations.length > 0 && (
            <button
              className="sidebar-clear-button"
              type="button"
              onClick={() => {
                if (
                  window.confirm(
                    "Effacer définitivement toutes les conversations enregistrées ?",
                  )
                ) {
                  onClearAll();
                }
              }}
              tabIndex={open ? 0 : -1}
            >
              Tout effacer
            </button>
          )}
          <div className="sidebar-book">
            <span className="sidebar-book-mark" aria-hidden="true">▤</span>
            <span>
              <strong>{bookTitle || "Marginalia"}</strong>
              <small>Vos échanges restent sur cet appareil</small>
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}
