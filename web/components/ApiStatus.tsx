"use client";

// Shows whether the backend answers on /api/health.
// "use client" means this runs in the visitor's browser (it needs to call the API from there).

import { useEffect, useState } from "react";

import { checkApiHealth, type ApiStatus as Status } from "@/lib/api";

const LABELS: Record<Status, string> = {
  checking: "API: checking…",
  ok: "API: OK",
  unreachable: "API: not reachable",
};

export default function ApiStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    // AbortController lets us cancel the request if the page is closed before it finishes.
    const controller = new AbortController();
    checkApiHealth(controller.signal).then((result) => {
      if (!controller.signal.aborted) setStatus(result);
    });
    return () => controller.abort();
  }, []);

  const color =
    status === "ok"
      ? "text-green-700 dark:text-green-400"
      : status === "unreachable"
        ? "text-red-700 dark:text-red-400"
        : "text-zinc-600 dark:text-zinc-400";

  return (
    <p role="status" data-testid="api-status" className={`text-lg font-medium ${color}`}>
      {LABELS[status]}
    </p>
  );
}
