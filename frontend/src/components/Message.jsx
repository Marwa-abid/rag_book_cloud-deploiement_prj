import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import Sources from "./Sources.jsx";

function MarkdownLink({
  href = "",
  children,
  bookAvailable,
  onPageClick,
  ...props
}) {
  const pageCitation = href.match(/^#page-(\d+)$/);
  if (pageCitation) {
    const page = Number(pageCitation[1]);
    if (!bookAvailable) {
      return <span className="citation-pill">{children}</span>;
    }
    return (
      <button
        className="citation-pill citation-button"
        type="button"
        title={`Ouvrir la page ${page}`}
        aria-label={`Ouvrir le livre à la page ${page}`}
        onClick={() => onPageClick(page)}
      >
        {children}
      </button>
    );
  }
  return (
    <a href={href} target="_blank" rel="noreferrer" {...props}>
      {children}
    </a>
  );
}

function withCitationLinks(text) {
  return text.replace(/\[p\.\s*(\d+)\]/gi, "[p. $1](#page-$1)");
}

export default function Message({
  message,
  waiting,
  error,
  onRetry,
  onCopy,
  bookAvailable,
  onPageClick,
}) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";
  const hasContent = Boolean(message.content);

  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
      onCopy?.();
    } catch {
      setCopied(false);
    }
  }

  return (
    <article className={`message-row ${isUser ? "message-user" : "message-assistant"}`}>
      {!isUser && (
        <div className="assistant-avatar" aria-hidden="true">
          <svg viewBox="0 0 28 28">
            <path d="M7 6.5c3.3-.6 5.7.1 7 1.9v12.4c-1.3-1.8-3.7-2.5-7-1.9v-12.4Zm14 0c-3.3-.6-5.7.1-7 1.9v12.4c1.3-1.8 3.7-2.5 7-1.9v-12.4Z" />
          </svg>
        </div>
      )}
      <div className="message-column">
        <div className={`message-bubble ${isUser ? "user-bubble" : "assistant-bubble"}`}>
          {isUser ? (
            <p className="user-text">{message.content}</p>
          ) : (
            <>
              {waiting && !hasContent && (
                <div className="thinking-dots" role="status" aria-label="Préparation de la réponse">
                  <span />
                  <span />
                  <span />
                </div>
              )}
              {hasContent && (
                <div className="markdown-body">
                  <ReactMarkdown
                    components={{
                      a: (props) => (
                        <MarkdownLink
                          {...props}
                          bookAvailable={bookAvailable}
                          onPageClick={onPageClick}
                        />
                      ),
                    }}
                  >
                    {withCitationLinks(message.content)}
                  </ReactMarkdown>
                  {waiting && <span className="stream-cursor" aria-hidden="true" />}
                </div>
              )}
            </>
          )}
        </div>
        {!isUser && hasContent && (
          <div className="message-tools">
            <button
              className="copy-button"
              onClick={copyAnswer}
              aria-label={copied ? "Réponse copiée" : "Copier la réponse"}
            >
              <svg viewBox="0 0 20 20" aria-hidden="true">
                <rect x="7" y="6" width="9" height="11" rx="1.5" />
                <path d="M12.5 6V4.5A1.5 1.5 0 0 0 11 3H5.5A1.5 1.5 0 0 0 4 4.5v7A1.5 1.5 0 0 0 5.5 13H7" />
              </svg>
              {copied ? "Copié" : "Copier"}
            </button>
            <Sources
              sources={message.sources}
              bookAvailable={bookAvailable}
              onPageClick={onPageClick}
            />
          </div>
        )}
        {error && (
          <div className="error-card" role="alert">
            <span className="error-icon" aria-hidden="true">!</span>
            <span>{error}</span>
            <button onClick={onRetry}>Réessayer</button>
          </div>
        )}
      </div>
    </article>
  );
}
