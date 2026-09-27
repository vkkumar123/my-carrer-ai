"""Resume file storage: local disk for dev, any S3-compatible bucket (R2, Supabase) in prod."""

from pathlib import Path

from app.config import get_settings


def save_file(key: str, data: bytes, content_type: str) -> None:
    s = get_settings()
    if s.storage_backend == "s3":
        _s3().put_object(Bucket=s.s3_bucket, Key=key, Body=data, ContentType=content_type)
        return
    path = Path(s.storage_local_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def delete_file(key: str) -> None:
    s = get_settings()
    if s.storage_backend == "s3":
        _s3().delete_object(Bucket=s.s3_bucket, Key=key)
        return
    (Path(s.storage_local_dir) / key).unlink(missing_ok=True)


def _s3():
    import boto3

    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint_url or None,
        aws_access_key_id=s.s3_access_key_id,
        aws_secret_access_key=s.s3_secret_access_key,
        region_name=s.s3_region,
    )
