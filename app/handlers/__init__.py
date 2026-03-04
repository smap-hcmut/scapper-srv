"""Central dispatch registry: queue name → action → handler function."""

from app.handlers import tiktok, facebook, youtube

# Queue name → { action_name: async handler_fn(client, params) }
QUEUE_HANDLERS: dict[str, dict] = {
    "tiktok_tasks": tiktok.HANDLERS,
    "facebook_tasks": facebook.HANDLERS,
    "youtube_tasks": youtube.HANDLERS,
}

# Queue name → platform label (for CLI filtering & logging)
QUEUE_PLATFORMS = {
    "tiktok_tasks": "tiktok",
    "facebook_tasks": "facebook",
    "youtube_tasks": "youtube",
}
