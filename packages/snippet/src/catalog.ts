export interface CatalogProduct {
  id: string;
  name: string;
  price?: string;
  currency?: string;
  imageUrl?: string;
}

/** Parses schema.org Product JSON-LD blocks present on the page on load. */
export function readCatalog(doc: Document = document): CatalogProduct[] {
  const blocks = Array.from(
    doc.querySelectorAll<HTMLScriptElement>('script[type="application/ld+json"]')
  );
  const products: CatalogProduct[] = [];

  for (const block of blocks) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(block.textContent ?? "");
    } catch {
      continue;
    }

    for (const entry of Array.isArray(parsed) ? parsed : [parsed]) {
      if (isProduct(entry)) {
        products.push(toCatalogProduct(entry));
      }
    }
  }

  return products;
}

interface JsonLdProduct {
  "@type": string;
  sku?: string;
  name?: string;
  image?: string | string[];
  offers?: { price?: string; priceCurrency?: string } | { price?: string; priceCurrency?: string }[];
}

function isProduct(entry: unknown): entry is JsonLdProduct {
  return (
    typeof entry === "object" &&
    entry !== null &&
    "@type" in entry &&
    (entry as { "@type": unknown })["@type"] === "Product"
  );
}

function toCatalogProduct(entry: JsonLdProduct): CatalogProduct {
  const offer = Array.isArray(entry.offers) ? entry.offers[0] : entry.offers;
  const image = Array.isArray(entry.image) ? entry.image[0] : entry.image;
  return {
    id: entry.sku ?? entry.name ?? crypto.randomUUID(),
    name: entry.name ?? "Untitled product",
    price: offer?.price,
    currency: offer?.priceCurrency,
    imageUrl: image,
  };
}
