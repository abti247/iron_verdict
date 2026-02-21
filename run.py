#!/usr/bin/env python3
"""
Iron Verdict application runner.
"""
import os
import uvicorn
from iron_verdict.config import settings


if __name__ == "__main__":
    reload = os.getenv("ENV") == "development"
    uvicorn.run(
        "iron_verdict.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=reload
    )
