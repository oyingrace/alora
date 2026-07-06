def test_tools_registered() -> None:
    """Phase 0 smoke test: the four required tools are registered on the MCP server."""
    from mcp_memory.server import mcp

    import asyncio

    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == {"recall", "write_episode", "revise_belief", "forget"}
