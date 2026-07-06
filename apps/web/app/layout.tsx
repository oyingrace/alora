import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Memora — demo storefront",
  description: "A drop-in shopping agent with inspectable, forgettable memory.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-neutral-900 antialiased">
        {children}
      </body>
    </html>
  );
}
