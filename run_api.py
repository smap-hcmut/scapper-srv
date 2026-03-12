import uvicorn
from app.main import app
from app.logger import setup_logging
from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    setup_logging(debug=settings.DEBUG)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8105,
        log_config=None,  # This prevents uvicorn from overriding loguru
        root_path="/scraper"
    )
