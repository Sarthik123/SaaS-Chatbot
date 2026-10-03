"use client";

/**
 * ChatWidget — the floating chat bubble and message panel.
 *
 * Features (from AGENTS.md):
 *   - Citations as clickable chips that show the source quote
 *   - Thumbs up / thumbs down feedback
 *   - "Talk to a human" button that opens a handoff form
 *   - Typing indicator while the backend is thinking
 *   - Clear error state when the request fails
 *   - Notice that AI answers can be wrong
 */

import { useEffect, useRef, useState } from "react";
import { type ChatResponse, type Citation, sendMessage, submitFeedback, submitHandoff } from "@/lib/api";

// ---------- types ----------

interface Message {
  id: string; // the backend message_id (empty for user messages)
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  abstained: boolean;
  handoffOffered: boolean;
  feedback?: "up" | "down"; // what the visitor clicked
  error?: string; // if this message failed
}

// ---------- small sub-components ----------

function CitationChip({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="inline-block">
      <button
        onClick={() => setOpen((o) => !o)}
        className="ml-1 rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-800 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-200 dark:hover:bg-blue-800"
        title={citation.title}
      >
        {citation.title}
      </button>
      {open && (
        <span className="mt-1 block rounded border border-zinc-200 bg-white p-2 text-xs text-zinc-700 shadow dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
          &ldquo;{citation.quote}&rdquo;
          {citation.url && (
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 underline text-blue-600 dark:text-blue-400"
            >
              source ↗
            </a>
          )}
        </span>
      )}
    </span>
  );
}

function FeedbackButtons({
  messageId,
  current,
  onFeedback,
}: {
  messageId: string;
  current?: "up" | "down";
  onFeedback: (messageId: string, rating: "up" | "down") => void;
}) {
  return (
    <div className="mt-1 flex gap-2">
      <button
        onClick={() => onFeedback(messageId, "up")}
        aria-label="Helpful"
        className={`rounded p-1 text-sm transition ${
          current === "up"
            ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
            : "text-zinc-400 hover:text-green-600"
        }`}
      >
        👍
      </button>
      <button
        onClick={() => onFeedback(messageId, "down")}
        aria-label="Not helpful"
        className={`rounded p-1 text-sm transition ${
          current === "down"
            ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
            : "text-zinc-400 hover:text-red-600"
        }`}
      >
        👎
      </button>
    </div>
  );
}

// ---------- handoff form ----------

function HandoffForm({
  conversationId,
  onClose,
}: {
  conversationId?: string;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await submitHandoff({ conversationId, name, email, message });
      setDone(true);
    } catch {
      setError("Could not send your request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="rounded-lg bg-green-50 p-4 text-sm text-green-800 dark:bg-green-950 dark:text-green-200">
        ✓ Your message was sent. Our support team will get back to you by email.
        <button onClick={onClose} className="ml-2 underline">
          Close
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
      <p className="text-sm font-medium">Talk to a human</p>
      <input
        required
        placeholder="Your name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="w-full rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800"
      />
      <input
        required
        type="email"
        placeholder="Your email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="w-full rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800"
      />
      <textarea
        required
        placeholder="Briefly describe your issue"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        rows={3}
        className="w-full rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800"
      />
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? "Sending…" : "Send"}
        </button>
        <button type="button" onClick={onClose} className="text-sm text-zinc-500 hover:underline">
          Cancel
        </button>
      </div>
    </form>
  );
}

// ---------- main widget ----------

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [showHandoff, setShowHandoff] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open, typing]);

  async function handleSend() {
    const text = input.trim();
    if (!text || typing) return;
    setInput("");
    setTyping(true);

    const userMsg: Message = {
      id: "",
      role: "user",
      content: text,
      citations: [],
      abstained: false,
      handoffOffered: false,
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const data: ChatResponse = await sendMessage(text, conversationId);
      setConversationId(data.conversation_id);
      const assistantMsg: Message = {
        id: data.message_id,
        role: "assistant",
        content: data.answer,
        citations: data.citations,
        abstained: data.abstained,
        handoffOffered: data.handoff_offered,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errMsg: Message = {
        id: "",
        role: "assistant",
        content: "Something went wrong. Please try again.",
        citations: [],
        abstained: true,
        handoffOffered: true,
        error: String(err),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setTyping(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  async function handleFeedback(messageId: string, rating: "up" | "down") {
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, feedback: rating } : m)),
    );
    await submitFeedback(messageId, rating).catch(() => {
      // Non-critical; fail silently
    });
  }

  return (
    <>
      {/* Bubble button */}
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close chat" : "Open support chat"}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {open ? (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
        )}
      </button>

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-24 right-6 z-50 flex w-80 flex-col rounded-2xl border border-zinc-200 bg-white shadow-2xl dark:border-zinc-700 dark:bg-zinc-900 sm:w-96">
          {/* Header */}
          <div className="flex items-center gap-2 rounded-t-2xl bg-blue-600 px-4 py-3">
            <div className="h-2 w-2 rounded-full bg-green-400" />
            <p className="font-medium text-white">Acme Invoicing Support</p>
          </div>

          {/* AI disclaimer */}
          <div className="bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-200">
            ⚠️ AI answers can be wrong. Always check the linked article.
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ maxHeight: "60vh" }}>
            {messages.length === 0 && (
              <p className="text-center text-sm text-zinc-400">
                Hi! Ask me anything about Acme Invoicing.
              </p>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white"
                      : msg.error
                      ? "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200"
                      : "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>

                  {/* Citations */}
                  {msg.citations.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      <span className="text-xs text-zinc-500 dark:text-zinc-400">Sources:</span>
                      {msg.citations.map((c) => (
                        <CitationChip key={c.chunk_id} citation={c} />
                      ))}
                    </div>
                  )}

                  {/* Feedback */}
                  {msg.role === "assistant" && msg.id && !msg.error && (
                    <FeedbackButtons
                      messageId={msg.id}
                      current={msg.feedback}
                      onFeedback={handleFeedback}
                    />
                  )}

                  {/* Handoff offer */}
                  {msg.handoffOffered && !showHandoff && (
                    <button
                      onClick={() => setShowHandoff(true)}
                      className="mt-2 block text-xs text-blue-600 underline dark:text-blue-400"
                    >
                      Talk to a human →
                    </button>
                  )}
                </div>
              </div>
            ))}

            {/* Typing indicator */}
            {typing && (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-zinc-100 px-3 py-2 dark:bg-zinc-800">
                  <span className="inline-flex gap-1">
                    {[0, 1, 2].map((n) => (
                      <span
                        key={n}
                        className="h-2 w-2 rounded-full bg-zinc-400 animate-bounce"
                        style={{ animationDelay: `${n * 0.15}s` }}
                      />
                    ))}
                  </span>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Handoff form */}
          {showHandoff && (
            <div className="border-t border-zinc-200 p-4 dark:border-zinc-700">
              <HandoffForm
                conversationId={conversationId}
                onClose={() => setShowHandoff(false)}
              />
            </div>
          )}

          {/* Input area */}
          <div className="border-t border-zinc-200 p-3 dark:border-zinc-700">
            <div className="flex gap-2">
              <textarea
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a message…"
                className="flex-1 resize-none rounded-xl border border-zinc-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-800 dark:text-white"
                disabled={typing}
              />
              <button
                onClick={handleSend}
                disabled={typing || !input.trim()}
                className="rounded-xl bg-blue-600 px-3 py-2 text-white hover:bg-blue-700 disabled:opacity-40"
                aria-label="Send message"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
