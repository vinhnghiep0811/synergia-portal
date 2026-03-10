from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.core.config import (
    MINIO_ACCESS_KEY,
    MINIO_BUCKET,
    MINIO_ENDPOINT,
    MINIO_SECRET_KEY,
    MINIO_SECURE,
)


class StorageService:
    def __init__(self):
        self.client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        self.bucket_name = MINIO_BUCKET

    def ensure_bucket_exists(self) -> None:
        found = self.client.bucket_exists(self.bucket_name)
        if not found:
            self.client.make_bucket(self.bucket_name)

    def upload_pdf_bytes(
        self,
        object_name: str,
        content: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        self.ensure_bucket_exists()

        data_stream = BytesIO(content)
        self.client.put_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
            data=data_stream,
            length=len(content),
            content_type=content_type,
        )
        return f"s3://{self.bucket_name}/{object_name}"