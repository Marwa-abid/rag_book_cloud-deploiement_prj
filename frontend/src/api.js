const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(
  /\/+$/,
  "",
);

export function getBookUrl(page) {
  const url = `${API_URL}/api/book`;
  return page ? `${url}#page=${page}` : url;
}

export async function fetchBookInfo({ signal } = {}) {
  const response = await fetch(`${API_URL}/api/book/info`, { signal });
  if (!response.ok) throw new Error("Impossible de charger les informations du livre.");
  return response.json();
}

export function createChatPayload(question, messages = []) {
  return {
    question,
    history: messages
      .filter((message) => message.role === "user" || message.role === "assistant")
      .map(({ role, content }) => ({ role, content }))
      .slice(-10),
  };
}

export class SSEParser {
  constructor() {
    this.buffer = "";
  }

  feed(fragment, final = false) {
    this.buffer += fragment;
    const events = [];
    let boundary;

    while ((boundary = this.buffer.search(/\r?\n\r?\n/)) !== -1) {
      const block = this.buffer.slice(0, boundary);
      const delimiter = this.buffer.slice(boundary).match(/^\r?\n\r?\n/)[0];
      this.buffer = this.buffer.slice(boundary + delimiter.length);
      const event = this.#parseBlock(block);
      if (event) events.push(event);
    }

    if (final && this.buffer.trim()) {
      const event = this.#parseBlock(this.buffer);
      if (event) events.push(event);
      this.buffer = "";
    }
    return events;
  }

  #parseBlock(block) {
    let event = "message";
    const data = [];
    for (const line of block.split(/\r?\n/)) {
      if (!line || line.startsWith(":")) continue;
      const separator = line.indexOf(":");
      const field = separator === -1 ? line : line.slice(0, separator);
      let value = separator === -1 ? "" : line.slice(separator + 1);
      if (value.startsWith(" ")) value = value.slice(1);
      if (field === "event") event = value;
      if (field === "data") data.push(value);
    }
    return data.length ? { event, data: data.join("\n") } : null;
  }
}

export async function fetchHealth({ signal } = {}) {
  const response = await fetch(`${API_URL}/api/health`, { signal });
  if (!response.ok) throw new Error("Le service de lecture est indisponible.");
  return response.json();
}

function friendlyHttpError(status, backendMessage = "") {
  if (status === 429) return "Le service est très sollicité. Réessayez dans un instant.";
  if (status === 503) return "Le service est temporairement surchargé. Réessayez bientôt.";
  if (status === 504) return "La réponse prend trop de temps. Vous pouvez réessayer.";
  return backendMessage || "Une erreur est survenue pendant la lecture du livre.";
}

export async function streamChat(question, messages, handlers, { signal } = {}) {
  let response;
  try {
    response = await fetch(`${API_URL}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(createChatPayload(question, messages)),
      signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Impossible de joindre le serveur. Vérifiez qu'il est démarré.");
  }

  if (!response.ok) {
    let backendMessage = "";
    try {
      backendMessage = (await response.json()).detail || "";
    } catch {
      backendMessage = "";
    }
    throw new Error(friendlyHttpError(response.status, backendMessage));
  }
  if (!response.body) {
    throw new Error("Le serveur n'a pas ouvert le flux de réponse.");
  }

  const parser = new SSEParser();
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  try {
    while (true) {
      const { done, value } = await reader.read();
      const fragment = decoder.decode(value || new Uint8Array(), { stream: !done });
      for (const event of parser.feed(fragment, done)) {
        let data;
        try {
          data = JSON.parse(event.data);
        } catch {
          throw new Error("Le serveur a envoyé une réponse de flux invalide.");
        }
        if (event.event === "token") handlers.onToken?.(data.token || "");
        if (event.event === "sources") {
          handlers.onSources?.(Array.isArray(data) ? data : data.sources || []);
        }
        if (event.event === "done") handlers.onDone?.();
        if (event.event === "error") {
          throw new Error(data.message || "Une erreur est survenue pendant le flux.");
        }
      }
      if (done) break;
    }
  } catch (error) {
    if (error.name === "AbortError") throw error;
    if (error instanceof TypeError) {
      throw new Error("La connexion au serveur a été interrompue.");
    }
    throw error;
  } finally {
    reader.releaseLock();
  }
}
