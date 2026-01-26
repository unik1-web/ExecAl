import os
from io import BytesIO

from minio import Minio
from minio.error import S3Error


def _minio_client() -> Minio:
    endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "minio")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "minio12345")
    secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"
    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)


def _bucket() -> str:
    return os.environ.get("MINIO_BUCKET", "documents")


def ensure_bucket() -> None:
    client = _minio_client()
    bucket = _bucket()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def put_object(object_name: str, content: bytes, content_type: str | None = None) -> str:
    ensure_bucket()
    client = _minio_client()
    bucket = _bucket()
    bio = BytesIO(content)
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=bio,
        length=len(content),
        content_type=content_type or "application/octet-stream",
    )
    return object_name


def get_object_bytes(object_name: str) -> bytes:
    client = _minio_client()
    bucket = _bucket()
    resp = None
    try:
        resp = client.get_object(bucket, object_name)
        return resp.read()
    except S3Error as e:
        raise FileNotFoundError(object_name) from e
    finally:
        if resp is not None:
            try:
                resp.close()  # type: ignore[misc]
                resp.release_conn()  # type: ignore[misc]
            except Exception:
                pass

