#!/usr/bin/env python3
"""
JudgeMe application runner.
"""
import os
import uvicorn
from judgeme.config import settings


if __name__ == "__main__":
    reload = os.getenv("ENV") == "development"
    uvicorn.run(
        "judgeme.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=reload
    )
