"use client";

/**
 * /admin — password-protected admin panel.
 *
 * Tabs (from AGENTS.md):
 *   Articles   — list, upload, delete, reindex
 *   Conversations — recent chats
 *   Unanswered — abstained assistant messages
 *   Tickets    — handoff requests
 *   Stats      — aggregate numbers
 */

import { useEffect, useState } from "react";
import { adminDelete, adminFetch, adminLogin, adminPost } from "@/lib/api";

// ---------- types ----------

interface Article { id: number; title: string; slug: string; source_url: string; updated_at: string }
interface Conversation { id: string; created_at: string }
interface Unanswered { message_id: string; conversation_id: string; content: string; created_at: string }
interface Ticket { id: number; conversation_id: string | null; name: string; email: string; message: string; status: string; created_at: string }
interface Stats {
  total_conversations: number;
  total_messages: number;
  abstain_rate: number;
  thumbs_up: number;
  thumbs_down: number;
  thumbs_ratio: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  avg_input_tokens: number | null;
  avg_output_tokens: number | null;
  total_open_tickets: number;
}

// ---------- login screen ----------

function LoginForm({ onLogin }: { onLogin: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const ok = await adminLogin(password);
    setLoading(false);
    if (ok) {
      onLogin();
    } else {
      setError("Wrong password.");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-2xl border border-zinc-200 bg-white p-8 shadow dark:border-zinc-700 dark:bg-zinc-900"
      >
        <h1 className="mb-6 text-xl font-bold text-zinc-900 dark:text-white">Admin login</h1>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          required
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-800 dark:text-white"
        />
        {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="mt-4 w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Logging in…" : "Log in"}
        </button>
      </form>
    </main>
  );
}

// ---------- shared helpers ----------

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold text-zinc-900 dark:text-white">{title}</h2>
      {children}
    </div>
  );
}

function Loading() {
  return <p className="text-sm text-zinc-400">Loading…</p>;
}

function Empty({ text }: { text: string }) {
  return <p className="text-sm text-zinc-400">{text}</p>;
}

// ---------- Articles tab ----------

function ArticlesTab() {
  const [articles, setArticles] = useState<Article[] | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [body, setBody] = useState("");
  const [uploadError, setUploadError] = useState("");

  async function load() {
    const data = await adminFetch("/api/admin/articles");
    setArticles(data as Article[]);
  }

  useEffect(() => { void load(); }, []);

  async function handleDelete(id: number) {
    if (!confirm("Delete this article and all its chunks?")) return;
    await adminDelete(`/api/admin/articles/${id}`);
    void load();
  }

  async function handleReindex() {
    setReindexing(true);
    try {
      const result = await adminPost("/api/admin/reindex", {}) as { reindexed: number };
      alert(`Reindexed ${result.reindexed} articles.`);
    } finally {
      setReindexing(false);
    }
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    setUploading(true);
    setUploadError("");
    try {
      await adminPost("/api/admin/articles", { title, slug, source_url: "", body });
      setTitle(""); setSlug(""); setBody("");
      void load();
    } catch {
      setUploadError("Upload failed. Check that the slug uses only lowercase letters, numbers and hyphens.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-8">
      {/* List */}
      <Section title="Articles">
        <div className="mb-2 flex justify-end">
          <button
            onClick={handleReindex}
            disabled={reindexing}
            className="rounded bg-zinc-100 px-3 py-1.5 text-sm hover:bg-zinc-200 disabled:opacity-50 dark:bg-zinc-800 dark:hover:bg-zinc-700"
          >
            {reindexing ? "Reindexing…" : "Re-embed all"}
          </button>
        </div>
        {articles === null ? <Loading /> : articles.length === 0 ? <Empty text="No articles yet." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-left dark:border-zinc-700">
                  <th className="pb-2 font-medium">Title</th>
                  <th className="pb-2 font-medium">Slug</th>
                  <th className="pb-2 font-medium">Updated</th>
                  <th className="pb-2" />
                </tr>
              </thead>
              <tbody>
                {articles.map((a) => (
                  <tr key={a.id} className="border-b border-zinc-100 dark:border-zinc-800">
                    <td className="py-2">{a.title}</td>
                    <td className="py-2 font-mono text-xs">{a.slug}</td>
                    <td className="py-2 text-xs text-zinc-500">{new Date(a.updated_at).toLocaleDateString()}</td>
                    <td className="py-2">
                      <button
                        onClick={() => handleDelete(a.id)}
                        className="text-xs text-red-600 hover:underline dark:text-red-400"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {/* Upload */}
      <Section title="Upload article">
        <form onSubmit={handleUpload} className="space-y-3">
          <input required placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800" />
          <input required placeholder="slug (lowercase, hyphens only)" value={slug}
            onChange={(e) => setSlug(e.target.value)}
            pattern="[a-z0-9-]+"
            className="w-full rounded border border-zinc-300 px-3 py-1.5 text-sm font-mono dark:border-zinc-600 dark:bg-zinc-800" />
          <textarea required placeholder="Article body (Markdown)" value={body}
            onChange={(e) => setBody(e.target.value)} rows={6}
            className="w-full rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800" />
          {uploadError && <p className="text-xs text-red-600">{uploadError}</p>}
          <button type="submit" disabled={uploading}
            className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50">
            {uploading ? "Uploading…" : "Upload & save"}
          </button>
          <p className="text-xs text-zinc-500">After uploading, click &quot;Re-embed all&quot; to make it searchable.</p>
        </form>
      </Section>
    </div>
  );
}

// ---------- Conversations tab ----------

function ConversationsTab() {
  const [convs, setConvs] = useState<Conversation[] | null>(null);

  useEffect(() => {
    adminFetch("/api/admin/conversations").then((d) => setConvs(d as Conversation[]));
  }, []);

  if (convs === null) return <Loading />;
  if (convs.length === 0) return <Empty text="No conversations yet." />;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-200 text-left dark:border-zinc-700">
            <th className="pb-2 font-medium">ID</th>
            <th className="pb-2 font-medium">Started</th>
          </tr>
        </thead>
        <tbody>
          {convs.map((c) => (
            <tr key={c.id} className="border-b border-zinc-100 dark:border-zinc-800">
              <td className="py-2 font-mono text-xs">{c.id}</td>
              <td className="py-2 text-xs text-zinc-500">{new Date(c.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------- Unanswered tab ----------

function UnansweredTab() {
  const [msgs, setMsgs] = useState<Unanswered[] | null>(null);

  useEffect(() => {
    adminFetch("/api/admin/unanswered").then((d) => setMsgs(d as Unanswered[]));
  }, []);

  if (msgs === null) return <Loading />;
  if (msgs.length === 0) return <Empty text="No unanswered questions yet." />;

  return (
    <ul className="space-y-2">
      {msgs.map((m) => (
        <li key={m.message_id} className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-700">
          <p className="text-zinc-900 dark:text-white">{m.content}</p>
          <p className="mt-1 text-xs text-zinc-500">
            {new Date(m.created_at).toLocaleString()} · conversation {m.conversation_id.slice(0, 8)}…
          </p>
        </li>
      ))}
    </ul>
  );
}

// ---------- Tickets tab ----------

function TicketsTab() {
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [filter, setFilter] = useState<"" | "open" | "closed">("");

  async function load() {
    const url = filter ? `/api/admin/tickets?status=${filter}` : "/api/admin/tickets";
    const data = await adminFetch(url);
    setTickets(data as Ticket[]);
  }

  useEffect(() => { void load(); }, [filter]);

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {(["", "open", "closed"] as const).map((s) => (
          <button
            key={s || "all"}
            onClick={() => setFilter(s)}
            className={`rounded px-3 py-1 text-sm ${filter === s ? "bg-blue-600 text-white" : "bg-zinc-100 dark:bg-zinc-800"}`}
          >
            {s || "All"}
          </button>
        ))}
      </div>
      {tickets === null ? <Loading /> : tickets.length === 0 ? <Empty text="No tickets." /> : (
        <ul className="space-y-3">
          {tickets.map((t) => (
            <li key={t.id} className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-700">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-zinc-900 dark:text-white">{t.name}</p>
                  <p className="text-xs text-zinc-500">{t.email}</p>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  t.status === "open" ? "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"
                  : "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                }`}>
                  {t.status}
                </span>
              </div>
              <p className="mt-2 text-zinc-700 dark:text-zinc-300">{t.message}</p>
              <p className="mt-1 text-xs text-zinc-400">{new Date(t.created_at).toLocaleString()}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------- Stats tab ----------

function StatsTab() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    adminFetch("/api/admin/stats").then((d) => setStats(d as Stats));
  }, []);

  if (stats === null) return <Loading />;

  const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
  const num = (n: number | null, unit = "") => n == null ? "—" : `${n.toFixed(0)}${unit}`;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {[
        { label: "Conversations", value: String(stats.total_conversations) },
        { label: "Messages", value: String(stats.total_messages) },
        { label: "Abstain rate", value: pct(stats.abstain_rate) },
        { label: "Thumbs up", value: String(stats.thumbs_up) },
        { label: "Thumbs down", value: String(stats.thumbs_down) },
        { label: "Satisfaction", value: stats.thumbs_ratio == null ? "—" : pct(stats.thumbs_ratio) },
        { label: "p50 latency", value: num(stats.p50_latency_ms, " ms") },
        { label: "p95 latency", value: num(stats.p95_latency_ms, " ms") },
        { label: "Avg input tokens", value: num(stats.avg_input_tokens) },
        { label: "Avg output tokens", value: num(stats.avg_output_tokens) },
        { label: "Open tickets", value: String(stats.total_open_tickets) },
      ].map((s) => (
        <div key={s.label} className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-800">
          <p className="text-xs text-zinc-500 dark:text-zinc-400">{s.label}</p>
          <p className="mt-1 text-2xl font-bold text-zinc-900 dark:text-white">{s.value}</p>
        </div>
      ))}
    </div>
  );
}

// ---------- main admin page ----------

type Tab = "articles" | "conversations" | "unanswered" | "tickets" | "stats";

export default function AdminPage() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [tab, setTab] = useState<Tab>("articles");

  if (!loggedIn) {
    return <LoginForm onLogin={() => setLoggedIn(true)} />;
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "articles", label: "Articles" },
    { id: "conversations", label: "Conversations" },
    { id: "unanswered", label: "Unanswered" },
    { id: "tickets", label: "Tickets" },
    { id: "stats", label: "Stats" },
  ];

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <span className="font-bold text-zinc-900 dark:text-white">Admin</span>
          <span className="text-sm text-zinc-500">Acme Invoicing Support</span>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-6 py-8">
        {/* Tab bar */}
        <div className="mb-6 flex gap-1 overflow-x-auto border-b border-zinc-200 dark:border-zinc-700">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`shrink-0 border-b-2 px-4 py-2 text-sm font-medium transition ${
                tab === t.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-zinc-500 hover:text-zinc-900 dark:hover:text-white"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {tab === "articles" && <ArticlesTab />}
        {tab === "conversations" && <ConversationsTab />}
        {tab === "unanswered" && <UnansweredTab />}
        {tab === "tickets" && <TicketsTab />}
        {tab === "stats" && <StatsTab />}
      </div>
    </main>
  );
}
