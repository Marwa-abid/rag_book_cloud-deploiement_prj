const CONVERSATIONS_KEY = "rag-book-conversations";
const ACTIVE_CONVERSATION_KEY = "rag-book-active-conversation";
const SIDEBAR_OPEN_KEY = "rag-book-sidebar-open";
const THEME_KEY = "rag-book-theme";
export const MAX_CONVERSATIONS = 50;

function browserStorage() {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

function safeStorage(storage) {
  return storage === undefined ? browserStorage() : storage;
}

function isConversation(value) {
  return (
    value &&
    typeof value.id === "string" &&
    typeof value.title === "string" &&
    Array.isArray(value.messages) &&
    typeof value.createdAt === "string" &&
    typeof value.updatedAt === "string"
  );
}

function sortConversations(conversations) {
  return [...conversations].sort(
    (left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt),
  );
}

export function titleForQuestion(question) {
  const title = question.trim().replace(/\s+/g, " ");
  if (title.length <= 40) return title || "Nouvelle conversation";
  return `${title.slice(0, 39).trimEnd()}…`;
}

export function createConversation(
  question = "",
  now = new Date(),
  id = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
) {
  const timestamp = now.toISOString();
  return {
    id,
    title: titleForQuestion(question),
    messages: [],
    createdAt: timestamp,
    updatedAt: timestamp,
  };
}

export function listConversations(storage) {
  try {
    const raw = safeStorage(storage)?.getItem(CONVERSATIONS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return sortConversations(parsed.filter(isConversation)).slice(
      0,
      MAX_CONVERSATIONS,
    );
  } catch {
    return [];
  }
}

export function saveConversation(conversation, storage) {
  const activeStorage = safeStorage(storage);
  if (!activeStorage || !isConversation(conversation)) return false;
  try {
    const conversations = listConversations(activeStorage);
    const updated = [
      conversation,
      ...conversations.filter((item) => item.id !== conversation.id),
    ];
    activeStorage.setItem(
      CONVERSATIONS_KEY,
      JSON.stringify(sortConversations(updated).slice(0, MAX_CONVERSATIONS)),
    );
    return true;
  } catch {
    return false;
  }
}

export function renameConversation(id, title, storage) {
  const conversations = listConversations(storage);
  const conversation = conversations.find((item) => item.id === id);
  if (!conversation || !title.trim()) return false;
  return saveConversation(
    { ...conversation, title: title.trim(), updatedAt: new Date().toISOString() },
    storage,
  );
}

export function deleteConversation(id, storage) {
  const activeStorage = safeStorage(storage);
  if (!activeStorage) return false;
  try {
    const conversations = listConversations(activeStorage).filter(
      (item) => item.id !== id,
    );
    activeStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations));
    if (getActiveConversationId(activeStorage) === id) {
      activeStorage.removeItem(ACTIVE_CONVERSATION_KEY);
    }
    return true;
  } catch {
    return false;
  }
}

export function clearConversations(storage) {
  const activeStorage = safeStorage(storage);
  if (!activeStorage) return false;
  try {
    activeStorage.removeItem(CONVERSATIONS_KEY);
    activeStorage.removeItem(ACTIVE_CONVERSATION_KEY);
    return true;
  } catch {
    return false;
  }
}

export function getActiveConversationId(storage) {
  try {
    return safeStorage(storage)?.getItem(ACTIVE_CONVERSATION_KEY) || null;
  } catch {
    return null;
  }
}

export function setActiveConversationId(id, storage) {
  const activeStorage = safeStorage(storage);
  if (!activeStorage) return false;
  try {
    if (id) activeStorage.setItem(ACTIVE_CONVERSATION_KEY, id);
    else activeStorage.removeItem(ACTIVE_CONVERSATION_KEY);
    return true;
  } catch {
    return false;
  }
}

export function getSidebarOpen(storage) {
  try {
    return safeStorage(storage)?.getItem(SIDEBAR_OPEN_KEY) === "true";
  } catch {
    return false;
  }
}

export function setSidebarOpen(isOpen, storage) {
  const activeStorage = safeStorage(storage);
  if (!activeStorage) return false;
  try {
    activeStorage.setItem(SIDEBAR_OPEN_KEY, String(isOpen));
    return true;
  } catch {
    return false;
  }
}

export function getThemePreference(storage) {
  try {
    const preference = safeStorage(storage)?.getItem(THEME_KEY);
    return ["light", "dark", "system"].includes(preference) ? preference : "system";
  } catch {
    return "system";
  }
}

export function setThemePreference(preference, storage) {
  const activeStorage = safeStorage(storage);
  if (!activeStorage || !["light", "dark", "system"].includes(preference)) {
    return false;
  }
  try {
    activeStorage.setItem(THEME_KEY, preference);
    return true;
  } catch {
    return false;
  }
}
