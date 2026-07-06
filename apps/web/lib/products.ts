// Mirrors apps/api/scripts/seed_catalog.py so the storefront and the backend
// demo the same catalog. Kept here (not fetched from the API) because the
// snippet's catalog reader parses schema.org JSON-LD the storefront itself
// renders — see packages/snippet/src/catalog.ts.
export interface Product {
  slug: string;
  externalId: string;
  name: string;
  description: string;
  category: string;
  price: number;
  currency: string;
  imageUrl: string;
}

export const PRODUCTS: Product[] = [
  {
    slug: "full-grain-leather-tote",
    externalId: "bag-001",
    name: "Full-Grain Leather Tote",
    description: "Hand-stitched full-grain leather tote with brass hardware. Ages beautifully.",
    category: "bags",
    price: 245.0,
    currency: "USD",
    imageUrl: "https://images.unsplash.com/photo-1591561954557-26941169b49e?w=600",
  },
  {
    slug: "canvas-weekender",
    externalId: "bag-002",
    name: "Canvas Weekender",
    description: "Durable canvas weekender bag with vegan leather trim, budget-friendly.",
    category: "bags",
    price: 68.0,
    currency: "USD",
    imageUrl: "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=600",
  },
  {
    slug: "minimalist-oak-side-table",
    externalId: "furn-001",
    name: "Minimalist Oak Side Table",
    description: "Solid oak side table, clean lines, no ornamentation. Scandinavian minimalist style.",
    category: "furniture",
    price: 189.0,
    currency: "USD",
    imageUrl: "https://images.unsplash.com/photo-1554295405-abb8fd54f153?w=600",
  },
  {
    slug: "carved-walnut-accent-chair",
    externalId: "furn-002",
    name: "Carved Walnut Accent Chair",
    description: "Ornate carved walnut accent chair with bold upholstery.",
    category: "furniture",
    price: 420.0,
    currency: "USD",
    imageUrl: "https://images.unsplash.com/photo-1519947486511-46149fa0a254?w=600",
  },
  {
    slug: "lightweight-umbrella-stroller",
    externalId: "baby-001",
    name: "Lightweight Umbrella Stroller",
    description: "Compact, lightweight umbrella stroller for travel and quick trips.",
    category: "baby",
    price: 89.0,
    currency: "USD",
    imageUrl: "https://images.unsplash.com/photo-1591886960571-74d43a9d4166?w=600",
  },
  {
    slug: "all-terrain-3-wheel-stroller",
    externalId: "baby-002",
    name: "All-Terrain 3-Wheel Stroller",
    description: "Rugged all-terrain stroller with air-filled tires for jogging and hiking.",
    category: "baby",
    price: 349.0,
    currency: "USD",
    imageUrl: "https://images.unsplash.com/photo-1591886960571-74d43a9d4166?w=600",
  },
  {
    slug: "minimalist-leather-sneakers",
    externalId: "shoes-001",
    name: "Minimalist Leather Sneakers",
    description: "Clean white leather sneakers, minimalist silhouette, premium materials.",
    category: "shoes",
    price: 130.0,
    currency: "USD",
    imageUrl: "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=600",
  },
  {
    slug: "budget-canvas-sneakers",
    externalId: "shoes-002",
    name: "Budget Canvas Sneakers",
    description: "Affordable canvas sneakers for everyday wear.",
    category: "shoes",
    price: 32.0,
    currency: "USD",
    imageUrl: "https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?w=600",
  },
];

export function getProductBySlug(slug: string): Product | undefined {
  return PRODUCTS.find((p) => p.slug === slug);
}
