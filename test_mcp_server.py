"""End-to-end test for the MCP server ask_persona tool.

Requires:
- ANTHROPIC_API_KEY and OPENAI_API_KEY set in .env
- ChromaDB collections pre-built (run ingestion first)
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.mcp_server import ask_persona


async def test_ask_persona(persona_id: str, query: str):
    """Test a single persona query."""
    print(f"\n--- Testing {persona_id} ---")
    print(f"  Query: {query}")

    try:
        result = await ask_persona(query=query, persona=persona_id)
        assert isinstance(result, str), f"Expected string result, got {type(result)}"
        assert len(result) > 50, f"Response too short: {len(result)} chars"
        print(f"  Response length: {len(result)} chars")
        print(f"  Preview: {result[:200]}...")
        print(f"  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


async def run_tests():
    """Run end-to-end tests for all personas."""
    print("=" * 60)
    print("MCP SERVER END-TO-END TESTS")
    print("=" * 60)

    test_cases = [
        ("eminescu", "Ce reprezinta Luceafarul in opera ta?"),
        ("bratianu", "Care este viziunea ta despre Romania moderna?"),
        ("caragiale", "Ce crezi despre politicienii romani?"),
        ("eliade", "Ce inseamna sacrul in viata omului modern?"),
        ("cioran", "De ce consideri ca suferinta este esentiala existentei?"),
    ]

    results = []
    for persona_id, query in test_cases:
        passed = await test_ask_persona(persona_id, query)
        results.append((persona_id, passed))

    # Test invalid persona
    print("\n--- Testing invalid persona ---")
    try:
        await ask_persona(query="test", persona="nonexistent")
        print("  FAIL: Should have raised an error")
        results.append(("invalid_persona", False))
    except (ValueError, Exception):
        print("  PASS: Invalid persona correctly rejected")
        results.append(("invalid_persona", True))

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    passed = sum(1 for _, p in results if p)
    total = len(results)
    for name, p in results:
        status = "PASS" if p else "FAIL"
        print(f"  {status}: {name}")
    print(f"\n{passed}/{total} tests passed")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_tests())
