import { describe, expect, it } from "vitest";
import { createChatPayload, SSEParser } from "./api.js";

describe("SSEParser", () => {
  it("reconstruit les événements découpés sur plusieurs fragments", () => {
    const parser = new SSEParser();
    const events = [
      ...parser.feed('event: token\r\ndata: {"tok'),
      ...parser.feed('en":"Bonjour"}\r\n\r\nevent: sources\ndata: [{"page":'),
      ...parser.feed('1}]\n\nevent: done\ndata: {}\n\n'),
    ];

    expect(events).toEqual([
      { event: "token", data: '{"token":"Bonjour"}' },
      { event: "sources", data: '[{"page":1}]' },
      { event: "done", data: "{}" },
    ]);
  });
});

describe("createChatPayload", () => {
  it("envoie uniquement les dix derniers messages d'historique", () => {
    const messages = Array.from({ length: 14 }, (_, index) => ({
      role: index % 2 === 0 ? "user" : "assistant",
      content: `message-${index}`,
    }));

    const payload = createChatPayload("Nouvelle question", messages);

    expect(payload.question).toBe("Nouvelle question");
    expect(payload.history).toHaveLength(10);
    expect(payload.history[0].content).toBe("message-4");
    expect(payload.history[9].content).toBe("message-13");
  });
});
