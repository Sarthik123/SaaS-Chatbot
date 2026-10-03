/**
 * /demo — a fake Acme Invoicing product page with the chat support widget.
 *
 * The page looks like a real SaaS landing page so portfolio reviewers can see
 * the chatbot in a realistic context. All company details are invented.
 */

import ChatWidget from "@/components/ChatWidget";

export const metadata = {
  title: "Acme Invoicing — Demo",
  description: "See the AI support chatbot in action on a fake invoicing product page.",
};

export default function DemoPage() {
  return (
    <div className="min-h-screen bg-white dark:bg-zinc-950">
      {/* Nav */}
      <header className="border-b border-zinc-200 dark:border-zinc-800">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <span className="text-lg font-bold text-blue-600">Acme Invoicing</span>
          <nav className="hidden gap-6 text-sm text-zinc-600 sm:flex dark:text-zinc-400">
            <a href="#features" className="hover:text-zinc-900 dark:hover:text-white">Features</a>
            <a href="#pricing" className="hover:text-zinc-900 dark:hover:text-white">Pricing</a>
            <a href="#" className="hover:text-zinc-900 dark:hover:text-white">Docs</a>
          </nav>
          <a href="#" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
            Get started free
          </a>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-5xl px-6 py-20 text-center">
        <span className="mb-4 inline-block rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 dark:bg-blue-950 dark:text-blue-300">
          Demo — AI support widget
        </span>
        <h1 className="text-4xl font-bold tracking-tight text-zinc-900 dark:text-white sm:text-5xl">
          Invoicing that just works
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-lg text-zinc-600 dark:text-zinc-400">
          Send invoices, collect payments, and track expenses — all in one place.
          Questions? Ask our AI support bot (bottom right).
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <a href="#" className="rounded-lg bg-blue-600 px-6 py-3 font-medium text-white hover:bg-blue-700">
            Start free trial
          </a>
          <a href="#features" className="rounded-lg border border-zinc-300 px-6 py-3 font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900">
            See features
          </a>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="bg-zinc-50 py-20 dark:bg-zinc-900">
        <div className="mx-auto max-w-5xl px-6">
          <h2 className="mb-10 text-center text-2xl font-bold text-zinc-900 dark:text-white">
            Everything you need to get paid faster
          </h2>
          <div className="grid gap-6 sm:grid-cols-3">
            {[
              { title: "Smart invoices", desc: "Auto-fill client details, add line items, and send in seconds." },
              { title: "Instant payments", desc: "Accept cards and bank transfers. Funds arrive in 1–2 business days." },
              { title: "Expense tracking", desc: "Snap a receipt on your phone. Acme files it for you." },
            ].map((f) => (
              <div key={f.title} className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-700 dark:bg-zinc-800">
                <h3 className="font-semibold text-zinc-900 dark:text-white">{f.title}</h3>
                <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="mx-auto max-w-5xl px-6 py-20">
        <h2 className="mb-10 text-center text-2xl font-bold text-zinc-900 dark:text-white">Pricing</h2>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { name: "Free", price: "$0", desc: "Up to 3 clients, 5 invoices per month.", highlight: false },
            { name: "Pro", price: "$19/mo", desc: "Unlimited clients and invoices, payment tracking.", highlight: true },
            { name: "Team", price: "$49/mo", desc: "Everything in Pro plus team accounts and roles.", highlight: false },
          ].map((p) => (
            <div
              key={p.name}
              className={`rounded-xl border p-6 ${
                p.highlight
                  ? "border-blue-600 bg-blue-50 dark:bg-blue-950"
                  : "border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-800"
              }`}
            >
              <p className="font-semibold text-zinc-900 dark:text-white">{p.name}</p>
              <p className="mt-1 text-2xl font-bold text-zinc-900 dark:text-white">{p.price}</p>
              <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{p.desc}</p>
              <a href="#" className={`mt-4 block rounded-lg px-4 py-2 text-center text-sm font-medium ${
                p.highlight ? "bg-blue-600 text-white hover:bg-blue-700" : "border border-zinc-300 text-zinc-700 hover:bg-zinc-50 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-700"
              }`}>
                Get started
              </a>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-zinc-200 px-6 py-8 text-center text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-600">
        Acme Invoicing is a fake company used in a portfolio demo. No real services here.
      </footer>

      {/* Chat widget floats above everything */}
      <ChatWidget />
    </div>
  );
}
