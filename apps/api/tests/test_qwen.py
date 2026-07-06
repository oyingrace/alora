from types import SimpleNamespace

from app.services import qwen


def test_token_usage_accumulates_and_resets() -> None:
    qwen.reset_token_usage()
    assert qwen.get_token_usage() == []

    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    qwen._log_usage("chat", "qwen-turbo", usage, 0.1)
    qwen._log_usage("embed", "text-embedding-v3", usage, 0.05)

    logged = qwen.get_token_usage()
    assert len(logged) == 2
    assert logged[0]["call"] == "chat"
    assert logged[0]["total_tokens"] == 15
    assert logged[1]["call"] == "embed"

    qwen.reset_token_usage()
    assert qwen.get_token_usage() == []
