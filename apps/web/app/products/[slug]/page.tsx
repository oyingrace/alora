import { notFound } from "next/navigation";
import Link from "next/link";

import { PRODUCTS, getProductBySlug } from "@/lib/products";

export function generateStaticParams() {
  return PRODUCTS.map((p) => ({ slug: p.slug }));
}

export default function ProductPage({ params }: { params: { slug: string } }) {
  const product = getProductBySlug(params.slug);
  if (!product) notFound();

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    sku: product.externalId,
    name: product.name,
    description: product.description,
    category: product.category,
    image: product.imageUrl,
    offers: {
      "@type": "Offer",
      price: product.price.toFixed(2),
      priceCurrency: product.currency,
      availability: "https://schema.org/InStock",
    },
  };

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16">
      {/* Parsed by the snippet's catalog reader — packages/snippet/src/catalog.ts */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <Link href="/" className="text-sm text-neutral-500 hover:underline">
        ← Back to all products
      </Link>

      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={product.imageUrl}
        alt={product.name}
        className="aspect-square w-full rounded-lg object-cover"
      />

      <div className="flex flex-col gap-2">
        <span className="text-xs uppercase tracking-wide text-neutral-500">
          {product.category}
        </span>
        <h1 className="text-2xl font-semibold">{product.name}</h1>
        <p className="text-neutral-600">{product.description}</p>
        <p className="text-xl font-medium">
          {product.currency} {product.price.toFixed(2)}
        </p>
      </div>

      {/* Selector the snippet's event capture listens for — packages/snippet/src/events.ts */}
      <button
        data-memora-add-to-cart={product.externalId}
        className="rounded-md bg-neutral-900 px-4 py-2 text-white hover:bg-neutral-700"
      >
        Add to cart
      </button>
    </main>
  );
}
