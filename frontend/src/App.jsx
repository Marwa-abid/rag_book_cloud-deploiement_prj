import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import Composer from "./components/Composer.jsx";
import Header from "./components/Header.jsx";
import MessageList from "./components/MessageList.jsx";
import Welcome from "./components/Welcome.jsx";
import BookPanel from "./components/BookPanel.jsx";
import ConversationSidebar from "./components/ConversationSidebar.jsx";
import { fetchBookInfo } from "./api.js";
import { useChat } from "./hooks/useChat.js";
import {
  getSidebarOpen,
  getThemePreference,
  setSidebarOpen as saveSidebarOpen,
  setThemePreference as saveThemePreference,
} from "./storage.js";

function getSystemTheme() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export default function App() {
  const {
    messages,
    conversations,
    activeConversationId,
    isGenerating,
    waitingForToken,
    activeAssistantId,
    error,
    health,
    sendQuestion,
    retry,
    stop,
    newConversation,
    selectConversation,
    renameConversation,
    deleteConversation,
    clearAllConversations,
    storageWarning,
  } = useChat();
  const [input, setInput] = useState("");
  const [themePreference, setThemePreference] = useState(getThemePreference);
  const [systemTheme, setSystemTheme] = useState(getSystemTheme);
  const [bookInfo, setBookInfo] = useState(null);
  const [bookPage, setBookPage] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(getSidebarOpen);
  const scrollRef = useRef(null);
  const shouldAutoScrollRef = useRef(true);
  const theme = themePreference === "system" ? systemTheme : themePreference;

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const updateSystemTheme = (event) =>
      setSystemTheme(event.matches ? "dark" : "light");
    mediaQuery.addEventListener?.("change", updateSystemTheme);
    return () => mediaQuery.removeEventListener?.("change", updateSystemTheme);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchBookInfo({ signal: controller.signal })
      .then(setBookInfo)
      .catch((error) => {
        if (error.name !== "AbortError") setBookInfo({ available: false });
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (bookPage === null) return undefined;
    function closeOnEscape(event) {
      if (event.key === "Escape") setBookPage(null);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [bookPage]);

  useEffect(() => {
    function closeOnePanelOnNarrowViewport() {
      if (window.innerWidth < 1100 && sidebarOpen && bookPage !== null) {
        setSidebarOpen(false);
        saveSidebarOpen(false);
      }
    }
    window.addEventListener("resize", closeOnePanelOnNarrowViewport);
    return () => window.removeEventListener("resize", closeOnePanelOnNarrowViewport);
  }, [bookPage, sidebarOpen]);

  useEffect(() => {
    if (!sidebarOpen) return undefined;
    function closeOnEscape(event) {
      if (event.key === "Escape") setSidebarOpen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [sidebarOpen]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute(
      "content",
      theme === "dark" ? "#10111a" : "#f5f7fb",
    );
  }, [theme]);

  useLayoutEffect(() => {
    if (!shouldAutoScrollRef.current) return;
    const element = scrollRef.current;
    if (element) {
      element.scrollTo({
        top: element.scrollHeight,
        behavior: isGenerating ? "auto" : "smooth",
      });
    }
  }, [messages, isGenerating, waitingForToken]);

  function handleScroll() {
    const element = scrollRef.current;
    if (!element) return;
    const distanceToBottom =
      element.scrollHeight - element.scrollTop - element.clientHeight;
    shouldAutoScrollRef.current = distanceToBottom < 140;
  }

  function submitQuestion(question = input) {
    if (isGenerating || !question.trim()) return;
    shouldAutoScrollRef.current = true;
    sendQuestion(question);
    setInput("");
  }

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setThemePreference(nextTheme);
    saveThemePreference(nextTheme);
  }

  function resetConversation() {
    newConversation();
    setInput("");
    shouldAutoScrollRef.current = true;
  }

  function toggleSidebar() {
    setSidebarOpen((current) => {
      const next = !current;
      if (next && window.innerWidth < 1100) setBookPage(null);
      saveSidebarOpen(next);
      return next;
    });
  }

  function openBook(page) {
    if (window.innerWidth < 1100) {
      setSidebarOpen(false);
      saveSidebarOpen(false);
    }
    setBookPage(page);
  }

  function openConversation(conversationId) {
    selectConversation(conversationId);
    setInput("");
    shouldAutoScrollRef.current = true;
  }

  return (
    <div className="app-shell">
      <div className="aurora aurora-one" aria-hidden="true" />
      <div className="aurora aurora-two" aria-hidden="true" />
      <div className="aurora aurora-three" aria-hidden="true" />
      <Header
        health={health}
        theme={theme}
        onToggleTheme={toggleTheme}
        onNewConversation={resetConversation}
        bookAvailable={bookInfo?.available === true}
        onOpenBook={() => openBook(1)}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={toggleSidebar}
      />

      <div className={`workspace ${bookPage !== null ? "has-book-panel" : ""}`}>
        <ConversationSidebar
          open={sidebarOpen}
          conversations={conversations}
          activeConversationId={activeConversationId}
          bookTitle={bookInfo?.title}
          storageWarning={storageWarning}
          onClose={() => {
            setSidebarOpen(false);
            saveSidebarOpen(false);
          }}
          onNewConversation={resetConversation}
          onSelectConversation={openConversation}
          onRenameConversation={renameConversation}
          onDeleteConversation={deleteConversation}
          onClearAll={clearAllConversations}
        />
        <main className="main-stage">
          {messages.length === 0 ? (
            <div className="welcome-scroll">
              <Welcome onAsk={submitQuestion} />
            </div>
          ) : (
            <MessageList
              messages={messages}
              activeAssistantId={activeAssistantId}
              waitingForToken={waitingForToken}
              error={error}
              onRetry={retry}
              scrollRef={scrollRef}
              onScroll={handleScroll}
              bookAvailable={bookInfo?.available === true}
              onPageClick={openBook}
            />
          )}

          <Composer
            value={input}
            onChange={setInput}
            onSubmit={() => submitQuestion()}
            onStop={stop}
            isGenerating={isGenerating}
          />
        </main>
        {bookPage !== null && (
          <BookPanel
            page={bookPage}
            title={bookInfo?.title}
            onClose={() => setBookPage(null)}
          />
        )}
      </div>
    </div>
  );
}
