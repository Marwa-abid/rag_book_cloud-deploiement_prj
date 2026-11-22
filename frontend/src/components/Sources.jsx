import React from "react";

export default function Sources({
  sources = [],
  bookAvailable,
  onPageClick,
}) {
  if (!sources.length) return null;

  return (
    <details className="sources">
      <summary>
        <span className="sources-summary-label">
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <path d="M5 3.5h7l3 3v10H5v-13Zm7 0v3h3M7.5 10h5m-5 3h5" />
          </svg>
          Sources <span className="source-count">{sources.length}</span>
        </span>
        <svg className="chevron" viewBox="0 0 20 20" aria-hidden="true">
          <path d="m5 7.5 5 5 5-5" />
        </svg>
      </summary>
      <div className="source-list">
        {sources.map((source, index) => {
          const percentage = Math.max(0, Math.min(100, source.score * 100));
          return (
            <article className="source-card" key={`${source.page}-${index}`}>
              <div className="source-card-top">
                {bookAvailable ? (
                  <button
                    className="source-page source-page-button"
                    type="button"
                    onClick={() => onPageClick(source.page)}
                    aria-label={`Ouvrir le livre à la page ${source.page}`}
                  >
                    PAGE {source.page}
                  </button>
                ) : (
                  <span className="source-page">PAGE {source.page}</span>
                )}
                <span className="source-score">{Math.round(percentage)}% match</span>
              </div>
              <div
                className="source-progress"
                role="meter"
                aria-label={`Pertinence ${Math.round(percentage)} %`}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(percentage)}
              >
                <span style={{ width: `${percentage}%` }} />
              </div>
              <p>{source.excerpt}</p>
            </article>
          );
        })}
      </div>
    </details>
  );
}
