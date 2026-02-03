#!/usr/bin/env python3
"""
JudgeMe application runner.
"""
import uvicorn
from judgeme.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "judgeme.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
