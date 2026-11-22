import { useCallback, useEffect, useRef, useState } from "react";
import { createChatPayload, fetchHealth, streamChat } from "../api.js";
import {
  clearConversations as clearStoredConversations,
  createConversation,
  deleteConversation as deleteStoredConversation,
  getActiveConversationId,
  listConversations,
  renameConversation as renameStoredConversation,
  saveConversation,
  setActiveConversationId,
  titleForQuestion,
} from "../storage.js";

function initialChatState() {
  const conversations = listConversations();
  const storedId = getActiveConversationId();
  const active =
    conversations.find((conversation) => conversation.id === storedId) ||
    conversations[0] ||
    null;
  if (active) setActiveConversationId(active.id);
  return {
    conversations,
    activeConversationId: active?.id || null,
    messages: active?.messages || [],
  };
}

function messageId() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
}

export function useChat() {
  const [initial] = useState(initialChatState);
  const [messages, setMessages] = useState(initial.messages);
  const [conversations, setConversations] = useState(initial.conversations);
  const [activeConversationId, setActiveConversationIdState] = useState(
    initial.activeConversationId,
  );
  const [isGenerating, setIsGenerating] = useState(false);
  const [waitingForToken, setWaitingForToken] = useState(false);
  const [error, setError] = useState(null);
  const [storageWarning, setStorageWarning] = useState(false);
  const [health, setHealth] = useState({ status: "checking" });
  const messagesRef = useRef(initial.messages);
  const activeConversationIdRef = useRef(initial.activeConversationId);
  const controllerRef = useRef(null);
  const generationRef = useRef(null);
  const retryContextRef = useRef(null);
  const activeAssistantIdRef = useRef(null);

  const updateMessages = useCallback((updater) => {
    const next =
      typeof updater === "function" ? updater(messagesRef.current) : updater;
    messagesRef.current = next;
    setMessages(next);
    return next;
  }, []);

  const refreshHealth = useCallback(async (signal) => {
    try {
      const result = await fetchHealth({ signal });
      setHealth({ ...result, status: "online" });
    } catch (requestError) {
      if (requestError.name !== "AbortError") setHealth({ status: "offline" });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    refreshHealth(controller.signal);
    const intervalId = window.setInterval(
      () => refreshHealth(controller.signal),
      30_000,
    );
    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, [refreshHealth]);

  const persistConversation = useCallback((conversationId, currentMessages) => {
    if (!conversationId || currentMessages.length === 0) return true;
    const existing = listConversations().find(
      (conversation) => conversation.id === conversationId,
    );
    const firstQuestion =
      currentMessages.find((message) => message.role === "user")?.content || "";
    const base =
      existing ||
      createConversation(firstQuestion, new Date(), conversationId);
    const conversation = {
      ...base,
      title: existing?.title || titleForQuestion(firstQuestion),
      messages: currentMessages,
      updatedAt: new Date().toISOString(),
    };
    const saved = saveConversation(conversation);
    setStorageWarning(!saved);
    if (saved) setConversations(listConversations());
    return saved;
  }, []);

  const finishGeneration = useCallback(
    (context) => {
      if (context.persisted) return;
      context.persisted = true;
      persistConversation(context.conversationId, messagesRef.current);
    },
    [persistConversation],
  );

  const stop = useCallback(() => {
    const context = generationRef.current;
    controllerRef.current?.abort();
    controllerRef.current = null;
    if (context) finishGeneration(context);
    generationRef.current = null;
    activeAssistantIdRef.current = null;
    retryContextRef.current = null;
    setIsGenerating(false);
    setWaitingForToken(false);
  }, [finishGeneration]);

  const executeQuestion = useCallback(
    async (rawQuestion, retryContext = null) => {
      const question = rawQuestion.trim();
      if (!question || controllerRef.current) return;

      const history = retryContext?.history || messagesRef.current;
      const userId = retryContext?.userId || messageId();
      const assistantId = retryContext?.assistantId || messageId();
      const conversationId =
        retryContext?.conversationId || activeConversationIdRef.current || messageId();
      const context = {
        question,
        history,
        userId,
        assistantId,
        conversationId,
        persisted: false,
      };
      generationRef.current = context;
      retryContextRef.current = context;
      activeAssistantIdRef.current = assistantId;
      if (!activeConversationIdRef.current) {
        activeConversationIdRef.current = conversationId;
        setActiveConversationIdState(conversationId);
        setStorageWarning(!setActiveConversationId(conversationId));
      }

      setError(null);
      setIsGenerating(true);
      setWaitingForToken(true);
      updateMessages((current) => {
        const userMessage = { id: userId, role: "user", content: question };
        const assistantMessage = {
          id: assistantId,
          role: "assistant",
          content: "",
          sources: [],
        };
        if (retryContext) {
          return current.map((message) => {
            if (message.id === userId) return userMessage;
            if (message.id === assistantId) return assistantMessage;
            return message;
          });
        }
        return [...current, userMessage, assistantMessage];
      });

      const controller = new AbortController();
      controllerRef.current = controller;
      try {
        await streamChat(
          question,
          createChatPayload(question, history).history,
          {
            onToken: (token) => {
              setWaitingForToken(false);
              updateMessages((current) =>
                current.map((message) =>
                  message.id === assistantId
                    ? { ...message, content: message.content + token }
                    : message,
                ),
              );
            },
            onSources: (sources) => {
              updateMessages((current) =>
                current.map((message) =>
                  message.id === assistantId ? { ...message, sources } : message,
                ),
              );
            },
          },
          { signal: controller.signal },
        );
        retryContextRef.current = null;
      } catch (requestError) {
        if (requestError.name !== "AbortError") {
          setError({ message: requestError.message, assistantId });
        }
      } finally {
        if (controllerRef.current === controller) controllerRef.current = null;
        if (generationRef.current === context) {
          finishGeneration(context);
          generationRef.current = null;
          activeAssistantIdRef.current = null;
          setIsGenerating(false);
          setWaitingForToken(false);
        }
      }
    },
    [finishGeneration, updateMessages],
  );

  const sendQuestion = useCallback(
    (question) => executeQuestion(question),
    [executeQuestion],
  );

  const retry = useCallback(() => {
    const context = retryContextRef.current;
    if (context) executeQuestion(context.question, context);
  }, [executeQuestion]);

  const newConversation = useCallback(() => {
    stop();
    const conversation = createConversation();
    activeConversationIdRef.current = conversation.id;
    setActiveConversationIdState(conversation.id);
    setStorageWarning(!setActiveConversationId(conversation.id));
    updateMessages([]);
    setError(null);
  }, [stop, updateMessages]);

  const selectConversation = useCallback(
    (conversationId) => {
      stop();
      const availableConversations = listConversations();
      const selected = availableConversations.find(
        (conversation) => conversation.id === conversationId,
      );
      if (!selected) return;
      activeConversationIdRef.current = selected.id;
      setActiveConversationIdState(selected.id);
      setStorageWarning(!setActiveConversationId(selected.id));
      setConversations(availableConversations);
      updateMessages(selected.messages);
      setError(null);
    },
    [stop, updateMessages],
  );

  const rename = useCallback((conversationId, title) => {
    const renamed = renameStoredConversation(conversationId, title);
    setStorageWarning(!renamed);
    if (renamed) setConversations(listConversations());
  }, []);

  const removeConversation = useCallback(
    (conversationId) => {
      if (activeConversationIdRef.current === conversationId) stop();
      const removed = deleteStoredConversation(conversationId);
      setStorageWarning(!removed);
      if (!removed) return;
      const updated = listConversations();
      setConversations(updated);
      if (activeConversationIdRef.current === conversationId) {
        const next = updated[0] || null;
        activeConversationIdRef.current = next?.id || null;
        setActiveConversationIdState(next?.id || null);
        setActiveConversationId(next?.id || null);
        updateMessages(next?.messages || []);
      }
    },
    [stop, updateMessages],
  );

  const clearAllConversations = useCallback(() => {
    stop();
    const cleared = clearStoredConversations();
    setStorageWarning(!cleared);
    if (!cleared) return;
    setConversations([]);
    const conversation = createConversation();
    activeConversationIdRef.current = conversation.id;
    setActiveConversationIdState(conversation.id);
    setActiveConversationId(conversation.id);
    updateMessages([]);
    setError(null);
  }, [stop, updateMessages]);

  return {
    messages,
    conversations,
    activeConversationId,
    isGenerating,
    waitingForToken,
    activeAssistantId: activeAssistantIdRef.current,
    error,
    storageWarning,
    health,
    sendQuestion,
    retry,
    stop,
    newConversation,
    selectConversation,
    renameConversation: rename,
    deleteConversation: removeConversation,
    clearAllConversations,
  };
}
