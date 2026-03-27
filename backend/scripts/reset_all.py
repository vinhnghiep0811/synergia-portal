from app.core.database import SessionLocal
from app.models.paper_record import PaperRecord
from app.models.canonical_document import CanonicalDocument
from app.services.storage_service import StorageService


def clear_minio() -> None:
    storage = StorageService()
    storage.ensure_bucket_exists()

    objects = storage.internal_client.list_objects(storage.bucket_name, recursive=True)
    for obj in objects:
        storage.internal_client.remove_object(storage.bucket_name, obj.object_name)

    print("Cleared MinIO objects")


def clear_db() -> None:
    db = SessionLocal()
    try:
        db.query(PaperRecord).delete()
        db.query(CanonicalDocument).delete()
        db.commit()
        print("Cleared database tables")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    clear_db()
    clear_minio()
    print("Reset completed")


if __name__ == "__main__":
    main()