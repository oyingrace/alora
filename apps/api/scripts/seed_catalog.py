#!/usr/bin/env python3
"""Seeds a small demo catalog so /chat's catalog_search tool and the bench harness
have real products to work with. Run with a live QWEN_API_KEY (embeds each product).

Usage: python -m scripts.seed_catalog
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app import db
from app.models import Product
from app.services.catalog import embed_product_text

STORE_ID = "demo"

PRODUCTS = [
    {
        "external_id": "bag-001",
        "name": "Full-Grain Leather Tote",
        "description": "Hand-stitched full-grain leather tote with brass hardware. Ages beautifully.",
        "category": "bags",
        "price": 245.00,
    },
    {
        "external_id": "bag-002",
        "name": "Canvas Weekender",
        "description": "Durable canvas weekender bag with vegan leather trim, budget-friendly.",
        "category": "bags",
        "price": 68.00,
    },
    {
        "external_id": "furn-001",
        "name": "Minimalist Oak Side Table",
        "description": "Solid oak side table, clean lines, no ornamentation. Scandinavian minimalist style.",
        "category": "furniture",
        "price": 189.00,
    },
    {
        "external_id": "furn-002",
        "name": "Carved Walnut Accent Chair",
        "description": "Ornate carved walnut accent chair with bold upholstery.",
        "category": "furniture",
        "price": 420.00,
    },
    {
        "external_id": "baby-001",
        "name": "Lightweight Umbrella Stroller",
        "description": "Compact, lightweight umbrella stroller for travel and quick trips.",
        "category": "baby",
        "price": 89.00,
    },
    {
        "external_id": "baby-002",
        "name": "All-Terrain 3-Wheel Stroller",
        "description": "Rugged all-terrain stroller with air-filled tires for jogging and hiking.",
        "category": "baby",
        "price": 349.00,
    },
    {
        "external_id": "shoes-001",
        "name": "Minimalist Leather Sneakers",
        "description": "Clean white leather sneakers, minimalist silhouette, premium materials.",
        "category": "shoes",
        "price": 130.00,
    },
    {
        "external_id": "shoes-002",
        "name": "Budget Canvas Sneakers",
        "description": "Affordable canvas sneakers for everyday wear.",
        "category": "shoes",
        "price": 32.00,
    },
]


async def seed() -> None:
    async with db.async_session() as session:
        for item in PRODUCTS:
            existing = (
                await session.execute(
                    select(Product).where(
                        Product.store_id == STORE_ID, Product.external_id == item["external_id"]
                    )
                )
            ).scalar_one_or_none()

            embedding = await embed_product_text(
                name=item["name"], description=item["description"], category=item["category"]
            )

            if existing:
                for key, value in item.items():
                    setattr(existing, key, value)
                existing.embedding = embedding
            else:
                session.add(
                    Product(
                        store_id=STORE_ID,
                        currency="USD",
                        tags={},
                        embedding=embedding,
                        **item,
                    )
                )
        await session.commit()
    print(f"seeded {len(PRODUCTS)} products for store={STORE_ID}")


if __name__ == "__main__":
    asyncio.run(seed())
