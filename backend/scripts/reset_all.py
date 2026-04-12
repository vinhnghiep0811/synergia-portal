from sqlalchemy import text

from app.core.database import SessionLocal
from app.services.storage_service import StorageService


def clear_db() -> None:
    db = SessionLocal()
    try:
        print("Clearing database...")

        # ⚠️ Thứ tự không quan trọng vì đã dùng CASCADE
        db.execute(text("""
            TRUNCATE TABLE
                activity_logs,
                extraction_runs,
                paper_records,
                canonical_documents
            CASCADE
        """))

        db.commit()
        print("✅ Database cleared")

    except Exception as e:
        db.rollback()
        print("❌ Failed to clear DB:", str(e))
        raise

    finally:
        db.close()


def clear_minio() -> None:
    storage = StorageService()
    storage.ensure_bucket_exists()

    print("Clearing MinIO objects...")

    try:
        objects = storage.internal_client.list_objects(
            storage.bucket_name,
            recursive=True
        )

        count = 0
        for obj in objects:
            storage.internal_client.remove_object(
                storage.bucket_name,
                obj.object_name
            )
            count += 1

        print(f"✅ MinIO cleared ({count} objects deleted)")

    except Exception as e:
        print("❌ Failed to clear MinIO:", str(e))
        raise


def main() -> None:
    print("=== RESET START ===")

    clear_db()
    clear_minio()

    print("=== RESET COMPLETED ===")


if __name__ == "__main__":
    main()