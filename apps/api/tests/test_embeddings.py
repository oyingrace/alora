import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.embeddings import embed_cached


@pytest.mark.asyncio
async def test_embed_cached_calls_qwen_once_for_repeated_text() -> None:
    text = f"unique test string {uuid.uuid4().hex}"
    with patch(
        "app.services.embeddings.qwen.embed", new=AsyncMock(return_value=[[0.1, 0.2]])
    ) as mock_embed:
        first = await embed_cached(text)
        second = await embed_cached(text)

    assert first == [0.1, 0.2]
    assert second == [0.1, 0.2]
    mock_embed.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_cached_calls_qwen_again_for_different_text() -> None:
    text_a = f"distinct string a {uuid.uuid4().hex}"
    text_b = f"distinct string b {uuid.uuid4().hex}"
    with patch(
        "app.services.embeddings.qwen.embed",
        new=AsyncMock(side_effect=[[[0.1, 0.2]], [[0.3, 0.4]]]),
    ) as mock_embed:
        first = await embed_cached(text_a)
        second = await embed_cached(text_b)

    assert first == [0.1, 0.2]
    assert second == [0.3, 0.4]
    assert mock_embed.await_count == 2
