import React from "react";
import Message from "./Message.jsx";

export default function MessageList({
  messages,
  activeAssistantId,
  waitingForToken,
  error,
  onRetry,
  scrollRef,
  onScroll,
  bookAvailable,
  onPageClick,
}) {
  return (
    <div className="conversation-scroll" ref={scrollRef} onScroll={onScroll}>
      <div className="conversation-inner">
        {messages.map((message) => (
          <Message
            key={message.id}
            message={message}
            waiting={waitingForToken && message.id === activeAssistantId}
            error={error?.assistantId === message.id ? error.message : null}
            onRetry={onRetry}
            bookAvailable={bookAvailable}
            onPageClick={onPageClick}
          />
        ))}
      </div>
    </div>
  );
}
