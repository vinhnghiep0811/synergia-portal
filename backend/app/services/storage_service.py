from io import BytesIO
from datetime import timedelta
from minio import Minio
from minio.error import S3Error

from app.core.config import (
    S3_ACCESS_KEY,
    S3_BUCKET,
    S3_ENDPOINT,
    S3_SECRET_KEY,
    S3_SECURE,
    S3_PUBLIC_ENDPOINT,
    S3_PUBLIC_SECURE,
)


class StorageService:
    def __init__(self):
        self.internal_client = Minio(
            endpoint=S3_ENDPOINT,
            access_key=S3_ACCESS_KEY,
            secret_key=S3_SECRET_KEY,
            secure=S3_SECURE,
        )

        self.public_client = Minio(
            endpoint=S3_PUBLIC_ENDPOINT,
            access_key=S3_ACCESS_KEY,
            secret_key=S3_SECRET_KEY,
            secure=S3_PUBLIC_SECURE,
        )
        self.bucket_name = S3_BUCKET

    def ensure_bucket_exists(self) -> None:
        if self.internal_client.bucket_exists(self.bucket_name):
            return

        try:
            self.internal_client.make_bucket(self.bucket_name)
        except S3Error:
            # Có thể request khác vừa tạo bucket xong
            if self.internal_client.bucket_exists(self.bucket_name):
                return
            raise

    def upload_file_bytes(
        self,
        object_name: str,
        content: bytes,
        content_type: str,
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

    def upload_pdf_bytes(
        self,
        object_name: str,
        content: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        return self.upload_file_bytes(
            object_name=object_name,
            content=content,
            content_type=content_type,
        )
    
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