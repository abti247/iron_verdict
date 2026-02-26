#!/usr/bin/env python3
"""
Iron Verdict application runner.
"""
import os
import uvicorn
from iron_verdict.config import settings


if __name__ == "__main__":
    reload = os.getenv("ENV") == "development"
    if reload:
        uvicorn.run(
            "iron_verdict.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=True,
        )
    else:
        import asyncio
        from iron_verdict.main import app
        config = uvicorn.Config(
            app,
            host=settings.HOST,
            port=settings.PORT,
        )
        server = uvicorn.Server(config)
        app.state.uvicorn_server = server
        asyncio.run(server.serve())
