import type { Metadata } from "next";
import Script from "next/script";

import "./globals.css";

export const metadata: Metadata = {
  title: "Memora — demo storefront",
  description: "A drop-in shopping agent with inspectable, forgettable memory.",
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-neutral-900 antialiased">
        {children}
        {/* The one-line install: packages/snippet built to dist/agent.js, copied to
            public/agent.js by `make snippet` — see packages/snippet/README. */}
        <Script
          src="/agent.js"
          data-store-id="demo"
          data-api-base={API_BASE_URL}
          strategy="afterInteractive"
        />
      </body>
    </html>
  );
}
