const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-16">
      <h1 className="text-3xl font-semibold">Memora demo storefront</h1>
      <p className="text-neutral-600">
        Scaffold placeholder — catalog, chat widget, recs rail, and Memory Inspector
        land in Phase 3. API base URL: <code>{API_BASE_URL}</code>
      </p>
    </main>
  );
}
