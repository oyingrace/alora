from fastapi import APIRouter

from app.schemas.recs import RecOut, RecsOut
from app.services.recs import get_recommendations

router = APIRouter(tags=["recs"])


@router.get("/recs", response_model=RecsOut)
async def recs(
    store_id: str,
    shopper_id: str,
    query: str = "",
    category: str | None = None,
    max_price: float | None = None,
) -> RecsOut:
    results, degraded = await get_recommendations(
        store_id, shopper_id, query=query, category=category, max_price=max_price
    )
    return RecsOut(
        recommendations=[
            RecOut(name=r.name, category=r.category, price=r.price, currency=r.currency)
            for r in results
        ],
        degraded=degraded,
    )
