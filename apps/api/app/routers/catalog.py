from fastapi import APIRouter
from sqlalchemy import select

from app import db
from app.models import Product
from app.schemas.catalog import CatalogSyncIn, CatalogSyncOut
from app.services.catalog import embed_product_text, tag_product_image

router = APIRouter(tags=["catalog"])


@router.post("/catalog", response_model=CatalogSyncOut)
async def sync_catalog(payload: CatalogSyncIn) -> CatalogSyncOut:
    """Upserts products from the storefront's catalog reader. Embeds each product for
    similarity search; best-effort qwen-vl-max visual tagging when an image is given.
    """
    async with db.async_session() as session:
        for item in payload.products:
            existing = (
                await session.execute(
                    select(Product).where(
                        Product.store_id == payload.store_id,
                        Product.external_id == item.external_id,
                    )
                )
            ).scalar_one_or_none()

            embedding = await embed_product_text(item.name, item.description, item.category)
            tags: dict = {}
            if item.image_url:
                visual = await tag_product_image(item.image_url)
                if visual:
                    tags = {"visual": visual}

            if existing:
                existing.name = item.name
                existing.description = item.description
                existing.category = item.category
                existing.price = item.price
                existing.currency = item.currency
                existing.image_url = item.image_url
                existing.embedding = embedding
                if tags:
                    existing.tags = tags
            else:
                session.add(
                    Product(
                        store_id=payload.store_id,
                        external_id=item.external_id,
                        name=item.name,
                        description=item.description,
                        category=item.category,
                        price=item.price,
                        currency=item.currency,
                        image_url=item.image_url,
                        tags=tags,
                        embedding=embedding,
                    )
                )
        await session.commit()

    return CatalogSyncOut(synced=len(payload.products))
