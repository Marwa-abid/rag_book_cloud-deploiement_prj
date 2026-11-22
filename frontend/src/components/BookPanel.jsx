import React from "react";
import { getBookUrl } from "../api.js";

export default function BookPanel({ page, title, onClose }) {
  const bookUrl = getBookUrl();
  const pageUrl = getBookUrl(page);

  return (
    <aside className="book-panel glass-panel" aria-label="Lecteur du livre">
      <div className="book-panel-header">
        <div className="book-panel-heading">
          <span className="eyebrow">LECTURE</span>
          <h2>{title || "Le livre"}</h2>
        </div>
        <div className="book-panel-actions">
          <a
            className="book-action"
            href={pageUrl}
            target="_blank"
            rel="noreferrer"
            aria-label="Ouvrir le livre dans un nouvel onglet"
          >
            Ouvrir
          </a>
          <a
            className="book-action"
            href={bookUrl}
            download
            aria-label="Télécharger le livre"
          >
            Télécharger
          </a>
          <button
            className="icon-button book-close"
            type="button"
            onClick={onClose}
            aria-label="Fermer le lecteur"
            title="Fermer"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m6 6 12 12M18 6 6 18" />
            </svg>
          </button>
        </div>
      </div>
      <iframe
        key={page || "first-page"}
        className="book-frame"
        src={pageUrl}
        title={`Livre PDF${page ? `, page ${page}` : ""}`}
      />
    </aside>
  );
}
