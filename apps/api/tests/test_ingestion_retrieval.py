from pathlib import Path

from app.models import Asset
from app.services.asset_ingestion import ingest_asset, retrieve_relevant_context


class DummyDB:
    def __init__(self):
        self.added = []

    def execute(self, *_args, **_kwargs):
        return None

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        return None


def test_text_asset_ingestion_happy_path(tmp_path: Path):
    asset_file = tmp_path / 'note.txt'
    asset_file.write_text('alpha beta gamma\nretrieval key sentence', encoding='utf-8')

    asset = Asset(
        project_id=1,
        chat_thread_id=1,
        message_id=None,
        source_type='user_upload',
        asset_type='text',
        mime_type='text/plain',
        original_filename='note.txt',
        stored_path=str(asset_file),
        derived_metadata_json={},
    )
    asset.id = 100  # type: ignore[attr-defined]

    db = DummyDB()
    meta = ingest_asset(db, asset)
    assert meta['ingest_status'] in {'text_extracted', 'json_extracted', 'csv_extracted', 'pdf_extracted', 'pdf_fallback_decoded'}
    assert meta['chunk_count'] >= 1


def test_retrieval_context_keyword_match():
    # lightweight shape contract test (integration is covered in execute/orchestration tests)
    # if no chunks exist, retrieval should gracefully return []
    class EmptyDB:
        class Query:
            def join(self, *_args, **_kwargs):
                return self

            def filter(self, *_args, **_kwargs):
                return []

        def query(self, *_args, **_kwargs):
            return EmptyDB.Query()

    hits = retrieve_relevant_context(EmptyDB(), chat_thread_id=1, query='hello world')
    assert hits == []
