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
