import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from core.database import Base, ChatMessage, GalleryImage, Session
from src import session_image_cleanup


def test_cleanup_session_images_deactivates_gallery_rows_and_unlinks_files(tmp_path, monkeypatch):
    image_dir = tmp_path / "generated_images"
    image_dir.mkdir()
    linked_file = image_dir / "aaaaaaaaaaaa.png"
    event_file = image_dir / "bbbbbbbbbbbb.png"
    linked_file.write_bytes(b"linked")
    event_file.write_bytes(b"event")
    monkeypatch.setattr(session_image_cleanup, "GENERATED_IMAGES_DIR", str(image_dir))

    engine = create_engine(
        f"sqlite:///{tmp_path / 'cleanup.db'}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        db.add(Session(id="chat-1", name="Image chat", endpoint_url="http://local", model="image-model", owner="alice"))
        db.add(
            GalleryImage(
                id="img-linked",
                filename=linked_file.name,
                prompt="linked",
                owner="alice",
                session_id="chat-1",
                is_active=True,
            )
        )
        db.add(
            GalleryImage(
                id="img-event",
                filename=event_file.name,
                prompt="event",
                owner="alice",
                is_active=True,
            )
        )
        db.add(
            ChatMessage(
                id="msg-1",
                session_id="chat-1",
                role="assistant",
                content="Generated image",
                meta_data=json.dumps(
                    {
                        "tool_events": [
                            {
                                "image_id": "img-event",
                                "image_url": f"/api/generated-image/{event_file.name}",
                            }
                        ]
                    }
                ),
            )
        )
        db.commit()

        removed = session_image_cleanup.cleanup_session_images("chat-1", db=db)

        assert removed == 2
        assert not linked_file.exists()
        assert not event_file.exists()
        assert db.query(GalleryImage).filter_by(id="img-linked").first().is_active is False
        assert db.query(GalleryImage).filter_by(id="img-event").first().is_active is False
    finally:
        db.close()
