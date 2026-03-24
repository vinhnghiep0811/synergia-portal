from io import BytesIO
from datetime import timedelta
from minio import Minio
from minio.error import S3Error
from urllib.parse import urlsplit, urlunsplit

from app.core.config import (
    MINIO_ACCESS_KEY,
    MINIO_BUCKET,
    MINIO_ENDPOINT,
    MINIO_SECRET_KEY,
    MINIO_SECURE,
    MINIO_PUBLIC_ENDPOINT,
    MINIO_PUBLIC_SECURE,
)


class StorageService:
    def __init__(self):
        self.internal_client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )

        self.public_client = Minio(
            endpoint=MINIO_PUBLIC_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_PUBLIC_SECURE,
        )
        self.bucket_name = MINIO_BUCKET

    def ensure_bucket_exists(self) -> None:
        found = self.internal_client.bucket_exists(self.bucket_name)
        if not found:
            self.internal_client.make_bucket(self.bucket_name)

    def upload_pdf_bytes(
        self,
        object_name: str,
        content: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        self.ensure_bucket_exists()

        data_stream = BytesIO(content)
        self.internal_client.put_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
            data=data_stream,
            length=len(content),
            content_type=content_type,
        )
        return self.build_s3_uri(object_name)

    def download_object(self, object_name: str) -> bytes:
        response = self.internal_client.get_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def build_s3_uri(self, object_name: str) -> str:
        return f"s3://{self.bucket_name}/{object_name}"
    
    def parse_s3_uri(self, storage_path: str) -> tuple[str, str]:
        prefix = "s3://"
        if not storage_path.startswith(prefix):
            raise ValueError("Invalid storage_path: must start with 's3://'")

        path_without_scheme = storage_path[len(prefix):]
        parts = path_without_scheme.split("/", 1)

        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("Invalid storage_path: expected format s3://bucket/object_name")

        bucket_name, object_name = parts
        return bucket_name, object_name

    def download_by_storage_path(self, storage_path: str) -> bytes:
        bucket_name, object_name = self.parse_s3_uri(storage_path)

        response = self.internal_client.get_object(
            bucket_name=bucket_name,
            object_name=object_name,
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def generate_presigned_get_url(
        self,
        storage_path: str,
        expires_minutes: int = 10,
    ) -> str:
        bucket_name, object_name = self.parse_s3_uri(storage_path)

        return self.public_client.presigned_get_object(
            bucket_name=bucket_name,
            object_name=object_name,
            expires=timedelta(minutes=expires_minutes),
        )