"""Storage utilities — local file system or MinIO."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

import aioboto3
from loguru import logger

from app.config import get_settings


def get_checksum(data: str) -> str:
    """Calculate SHA256 checksum of a string."""
    return f"sha256:{hashlib.sha256(data.encode()).hexdigest()}"


async def save_result_data(
    task_id: str, platform: str, action: str, result_dict: dict
) -> dict[str, Any]:
    """
    Save result data either to local disk or MinIO based on MODE.
    Returns storage metadata.
    """
    settings = get_settings()
    data_str = json.dumps(result_dict, ensure_ascii=False, indent=2, default=str)
    checksum = get_checksum(data_str)
    
    now = datetime.now(timezone.utc)
    yyyy, mm, dd = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")
    
    # Path following the canonical contract: 
    # crawl-raw/{platform}/{action}/{yyyy}/{mm}/{dd}/{task_id}.json
    storage_path = f"crawl-raw/{platform}/{action}/{yyyy}/{mm}/{dd}/{task_id}.json"
    batch_id = f"raw-{platform}-{action}-{task_id}"

    if settings.MODE == "production":
        # Production: Upload to MinIO
        logger.info(f"Uploading result to MinIO: {settings.MINIO_BUCKET}/{storage_path}")
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=f"{'https' if settings.MINIO_USE_SSL else 'http'}://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name=settings.MINIO_REGION,
        ) as s3:
            # Check if bucket exists, if not create it
            try:
                await s3.head_bucket(Bucket=settings.MINIO_BUCKET)
            except Exception:
                logger.info(f"Bucket {settings.MINIO_BUCKET} not found, creating it...")
                await s3.create_bucket(Bucket=settings.MINIO_BUCKET)

            await s3.put_object(
                Bucket=settings.MINIO_BUCKET,
                Key=storage_path,
                Body=data_str,
                ContentType="application/json",
            )
        
        return {
            "storage_bucket": settings.MINIO_BUCKET,
            "storage_path": storage_path,
            "batch_id": batch_id,
            "checksum": checksum,
            "mode": "production"
        }
    else:
        # Dev: Save to local output/
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        local_filename = f"{platform}_{action}_{task_id[:8]}_{timestamp}.json"
        local_path = os.path.join(settings.OUTPUT_DIR, local_filename)
        
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(data_str)
            
        logger.info(f"Result saved to local file: {local_path}")
        
        return {
            "storage_bucket": "local",
            "storage_path": local_path,
            "batch_id": batch_id,
            "checksum": checksum,
            "mode": "dev"
        }
