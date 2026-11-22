import { describe, expect, it } from "vitest";
import {
  clearConversations,
  createConversation,
  deleteConversation,
  getThemePreference,
  listConversations,
  MAX_CONVERSATIONS,
  renameConversation,
  saveConversation,
  setThemePreference,
  titleForQuestion,
} from "./storage.js";

class MemoryStorage {
  values = new Map();

  getItem(key) {
    return this.values.get(key) ?? null;
  }

  setItem(key, value) {
    this.values.set(key, String(value));
  }

  removeItem(key) {
    this.values.delete(key);
  }
}

describe("conversation storage", () => {
  it("creates and stores a conversation with a title from its first question", () => {
    const storage = new MemoryStorage();
    const created = createConversation(
      "Comment les abeilles vivent-elles ?",
      new Date("2026-11-22T10:00:00.000Z"),
      "conversation-1",
    );

    expect(saveConversation(created, storage)).toBe(true);
    expect(listConversations(storage)).toEqual([created]);
  });

  it("renames and deletes a conversation", () => {
    const storage = new MemoryStorage();
    const conversation = createConversation("Question initiale", new Date(), "one");
    saveConversation(conversation, storage);

    expect(renameConversation("one", "Titre modifié", storage)).toBe(true);
    expect(listConversations(storage)[0].title).toBe("Titre modifié");
    expect(deleteConversation("one", storage)).toBe(true);
    expect(listConversations(storage)).toEqual([]);
  });

  it("keeps only the 50 most recently updated conversations", () => {
    const storage = new MemoryStorage();
    for (let index = 0; index <= MAX_CONVERSATIONS; index += 1) {
      saveConversation(
        createConversation(
          `Question ${index}`,
          new Date(Date.UTC(2026, 0, 1, 0, index)),
          `conversation-${index}`,
        ),
        storage,
      );
    }

    const conversations = listConversations(storage);
    expect(conversations).toHaveLength(MAX_CONVERSATIONS);
    expect(conversations[0].id).toBe(`conversation-${MAX_CONVERSATIONS}`);
    expect(conversations.some((item) => item.id === "conversation-0")).toBe(false);
  });

  it("returns an empty list when the stored JSON is corrupted", () => {
    const storage = new MemoryStorage();
    storage.setItem("rag-book-conversations", "{invalid");

    expect(listConversations(storage)).toEqual([]);
  });

  it("limits automatically generated titles to 40 characters", () => {
    expect(titleForQuestion("a".repeat(60))).toHaveLength(40);
  });

  it("fails safely when local storage is full", () => {
    const storage = new MemoryStorage();
    storage.setItem = () => {
      throw new Error("QuotaExceededError");
    };

    expect(
      saveConversation(createConversation("Question", new Date(), "full"), storage),
    ).toBe(false);
    expect(clearConversations(storage)).toBe(true);
  });

  it("falls back to the system theme if reading or writing storage fails", () => {
    const storage = new MemoryStorage();
    storage.getItem = () => {
      throw new Error("Storage unavailable");
    };
    storage.setItem = () => {
      throw new Error("Storage unavailable");
    };

    expect(getThemePreference(storage)).toBe("system");
    expect(setThemePreference("dark", storage)).toBe(false);
  });
});
