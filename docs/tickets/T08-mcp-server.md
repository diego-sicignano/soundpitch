# T08. MCP server (optional)

**Depends on:** T03  **Acceptance:** S17  **Spec:** §16  **Judging:** criterion 2 (MCP integration)

## Goal

The match is available as read-only MCP tools, and the describer agent can use them.

## Steps

1. **Context7 first:** the official MCP Python SDK (FastMCP) and the way Agent Framework consumes MCP tools. Check the installed version.
2. **Test first (S17)** in `backend/tests/test_mcp.py`: tools return valid contract objects as JSON; an unknown preset is a tool error with code `preset_not_found`.
3. Implement `backend/app/mcp_server.py`; add the package to `requirements-agents.txt`.
4. Optional: let the `Describer` agent fetch moments through the tool instead of the prompt, and show in a test that the verifier accepts the same descriptions.

## Out of scope

Write tools, authentication, remote hosting of the MCP server.
