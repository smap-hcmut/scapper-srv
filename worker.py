"""
Standalone worker CLI — run without FastAPI server.

Usage:
    python worker.py                    # all queues
    python worker.py tiktok             # only tiktok
    python worker.py facebook youtube   # facebook + youtube
"""

import asyncio
import sys

from loguru import logger
from app.logger import setup_logging
from app.config import get_settings

async def main():
    from app.worker import Worker
    
    settings = get_settings()
    setup_logging(debug=settings.DEBUG)

    platforms = sys.argv[1:] if len(sys.argv) > 1 else None
    worker = Worker(queues=platforms)
    await worker.start()

    try:
        # Keep running until interrupted
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await worker.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by KeyboardInterrupt.")
