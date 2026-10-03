import ApiStatus from "@/components/ApiStatus";

// Phase 0 home page: proves the website can talk to the backend.
// The real customer experience (/demo) arrives in Phase 3, the admin area (/admin) in Phase 4.
export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-24 text-center">
      <h1 className="text-4xl font-semibold tracking-tight">Support Agent</h1>
      <p className="max-w-md text-zinc-600 dark:text-zinc-400">
        A customer-support chatbot that answers only from a company&apos;s own help articles.
      </p>
      <ApiStatus />
    </main>
  );
}
