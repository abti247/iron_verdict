def pytest_collection_modifyitems(config, items):
    # Why: pytest-playwright's session-scoped fixture leaves an asyncio loop
    # running on the main thread for the rest of the session, which makes
    # pytest-asyncio's per-test Runner refuse to start. Running backend tests
    # before any e2e test keeps that loop out of their way so a single
    # `pytest` invocation can execute both suites.
    items.sort(key=lambda item: 1 if "/e2e/" in item.nodeid.replace("\\", "/") else 0)
