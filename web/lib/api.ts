// Where the backend lives.
//
// NEXT_PUBLIC_API_URL is read when the website is BUILT (Next.js copies NEXT_PUBLIC_
// values into the browser code). Locally the default below is right. On Vercel, set
// NEXT_PUBLIC_API_URL to your Render address before deploying.
const DEFAULT_API_URL = "http://localhost:8000";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL).replace(
  /\/+$/,
  "",
);

export type ApiStatus = "checking" | "ok" | "unreachable";

// Asks the backend "are you alive?". Never throws: any problem means "unreachable".
export async function checkApiHealth(signal?: AbortSignal): Promise<ApiStatus> {
  try {
    const response = await fetch(`${API_URL}/api/health`, { signal, cache: "no-store" });
    if (!response.ok) return "unreachable";
    const body: unknown = await response.json();
    const isOk =
      typeof body === "object" && body !== null && (body as { status?: unknown }).status === "ok";
    return isOk ? "ok" : "unreachable";
  } catch {
    return "unreachable";
  }
}

// ---------- chat ----------

export interface Citation {
  article_id: number;
  title: string;
  url: string;
  chunk_id: number;
  quote: string;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  citations: Citation[];
  abstained: boolean;
  handoff_offered: boolean;
}

export async function sendMessage(
  message: string,
  conversationId?: string,
): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId ?? null }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `HTTP ${response.status}`);
  }
  return response.json() as Promise<ChatResponse>;
}

// ---------- feedback ----------

export async function submitFeedback(
  messageId: string,
  rating: "up" | "down",
  comment?: string,
): Promise<void> {
  await fetch(`${API_URL}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message_id: messageId, rating, comment }),
  });
}

// ---------- handoff ----------

export interface HandoffData {
  conversationId?: string;
  name: string;
  email: string;
  message: string;
}

export async function submitHandoff(data: HandoffData): Promise<{ ticket_id: number }> {
  const response = await fetch(`${API_URL}/api/handoff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: data.conversationId ?? null,
      name: data.name,
      email: data.email,
      message: data.message,
    }),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<{ ticket_id: number }>;
}

// ---------- admin ----------

export async function adminLogin(password: string): Promise<boolean> {
  const response = await fetch(`${API_URL}/api/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ password }),
  });
  return response.ok;
}

export async function adminFetch(path: string): Promise<unknown> {
  const response = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export async function adminPost(path: string, body: unknown): Promise<unknown> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export async function adminDelete(path: string): Promise<boolean> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "DELETE",
    credentials: "include",
  });
  return response.ok;
}
