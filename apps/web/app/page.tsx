import Link from "next/link";

import { PRODUCTS } from "@/lib/products";

export default function HomePage() {
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-16">
      <div>
        <h1 className="text-3xl font-semibold">Memora demo storefront</h1>
        <p className="mt-2 text-neutral-600">
          Browse a bit, chat with the assistant, and open the Memory Inspector (bottom
          right) to see — and edit — what it remembers about you.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 md:grid-cols-4">
        {PRODUCTS.map((product) => (
          <Link
            key={product.slug}
            href={`/products/${product.slug}`}
            className="group flex flex-col gap-2"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={product.imageUrl}
              alt={product.name}
              className="aspect-square w-full rounded-lg object-cover transition group-hover:opacity-80"
            />
            <span className="text-sm font-medium">{product.name}</span>
            <span className="text-sm text-neutral-500">
              {product.currency} {product.price.toFixed(2)}
            </span>
          </Link>
        ))}
      </div>
    </main>
  );
}
