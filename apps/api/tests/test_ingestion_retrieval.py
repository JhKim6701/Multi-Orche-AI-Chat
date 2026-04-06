from pathlib import Path

from app.models import Asset, AssetChunk
import app.services.asset_ingestion as asset_ingestion
from app.services.asset_ingestion import ingest_asset, retrieve_relevant_context


class DummyDB:
    def __init__(self):
        self.added = []
        self.scalar_value = None

    def execute(self, *_args, **_kwargs):
        return None

    def add(self, obj):
        if isinstance(obj, AssetChunk) and not getattr(obj, "id", None):
            obj.id = len([x for x in self.added if isinstance(x, AssetChunk)]) + 1  # type: ignore[attr-defined]
        self.added.append(obj)

    def flush(self):
        return None

    def scalar(self, *_args, **_kwargs):
        return self.scalar_value

    def get(self, *_args, **_kwargs):
        return None

    class _Query:
        def __init__(self, rows):
            self.rows = rows

        def join(self, *_args, **_kwargs):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return self.rows

    def query(self, *_args, **_kwargs):
        rows = []
        chunks = [x for x in self.added if isinstance(x, AssetChunk)]
        for ch in chunks:
            asset = next((a for a in self.added if isinstance(a, Asset) and a.id == ch.asset_id), None)
            if asset:
                rows.append((ch, asset))
        return DummyDB._Query(rows)


def _mk_asset(path: Path, mime: str, name: str) -> Asset:
    asset = Asset(
        project_id=1,
        chat_thread_id=1,
        message_id=None,
        source_type='user_upload',
        asset_type='text',
        mime_type=mime,
        original_filename=name,
        stored_path=str(path),
        derived_metadata_json={},
    )
    asset.id = hash(name) % 100000 + 1  # type: ignore[attr-defined]
    return asset


def test_ingestion_happy_paths_txt_md_json_csv_pdf(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(asset_ingestion.EmbeddingProvider, 'embed_text', lambda self, t: ([0.1, 0.2, 0.3], {'mode': 'mock'}))
    monkeypatch.setattr(asset_ingestion.QdrantStore, 'ensure_collection', lambda self, vector_size: {'ok': True})
    monkeypatch.setattr(asset_ingestion.QdrantStore, 'upsert_points', lambda self, points: {'ok': True, 'count': len(points)})

    txt = tmp_path / 'a.txt'; txt.write_text('alpha beta gamma', encoding='utf-8')
    md = tmp_path / 'a.md'; md.write_text('# title\nsemantic retrieval', encoding='utf-8')
    js = tmp_path / 'a.json'; js.write_text('{"x":1,"y":"retrieval"}', encoding='utf-8')
    csvf = tmp_path / 'a.csv'; csvf.write_text('c1,c2\nfoo,bar', encoding='utf-8')
    pdf = tmp_path / 'a.pdf'; pdf.write_bytes(b'%PDF-1.4 fallback pdf content retrieval text')

    db = DummyDB()
    metas = []
    for path, mime in [
        (txt, 'text/plain'),
        (md, 'text/markdown'),
        (js, 'application/json'),
        (csvf, 'text/csv'),
        (pdf, 'application/pdf'),
    ]:
        asset = _mk_asset(path, mime, path.name)
        db.add(asset)
        metas.append(ingest_asset(db, asset))

    assert all('ingest_status' in m for m in metas)
    assert all('ingest_pipeline' in m for m in metas)
    assert any(m['ingest_pipeline']['indexed'] for m in metas)


def test_embedding_generation_and_qdrant_upsert_happy_path(monkeypatch, tmp_path: Path):
    txt = tmp_path / 'vec.txt'
    txt.write_text('vector index me please', encoding='utf-8')
    called = {'embed': 0, 'upsert': 0}

    def _embed(self, text):
        called['embed'] += 1
        return [0.3, 0.2, 0.1], {'mode': 'mock'}

    def _upsert(self, points):
        called['upsert'] += len(points)
        return {'ok': True, 'count': len(points)}

    monkeypatch.setattr(asset_ingestion.EmbeddingProvider, 'embed_text', _embed)
    monkeypatch.setattr(asset_ingestion.QdrantStore, 'ensure_collection', lambda self, vector_size: {'ok': True})
    monkeypatch.setattr(asset_ingestion.QdrantStore, 'upsert_points', _upsert)

    db = DummyDB()
    asset = _mk_asset(txt, 'text/plain', 'vec.txt')
    ingest_asset(db, asset)

    assert called['embed'] >= 1
    assert called['upsert'] >= 1


def test_retrieval_returns_relevant_chunks(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(asset_ingestion.EmbeddingProvider, 'embed_text', lambda self, t: ([0.8, 0.2, 0.1], {'mode': 'mock'}))
    monkeypatch.setattr(asset_ingestion.QdrantStore, 'search', lambda self, vector, limit, filter_payload=None: [])

    db = DummyDB()
    path = tmp_path / 'ctx.txt'
    path.write_text('project onboarding checklist and deployment runbook', encoding='utf-8')
    asset = _mk_asset(path, 'text/plain', 'ctx.txt')
    db.add(asset)
    ingest_asset(db, asset)

    hits = retrieve_relevant_context(db, chat_thread_id=1, project_id=1, query='deployment checklist', limit=3)
    assert len(hits) >= 1
    assert 'checklist' in hits[0]['snippet']


def test_ocr_fallback_metadata_path(monkeypatch, tmp_path: Path):
    img = tmp_path / 'x.png'
    img.write_bytes(b'fake image bytes')

    monkeypatch.setattr(asset_ingestion, '_try_ocr', lambda path, mime: ('recognized text', 'ocr_image_success'))
    monkeypatch.setattr(asset_ingestion.EmbeddingProvider, 'embed_text', lambda self, t: ([0.1, 0.2, 0.3], {'mode': 'mock'}))
    monkeypatch.setattr(asset_ingestion.QdrantStore, 'ensure_collection', lambda self, vector_size: {'ok': True})
    monkeypatch.setattr(asset_ingestion.QdrantStore, 'upsert_points', lambda self, points: {'ok': True, 'count': len(points)})

    db = DummyDB()
    asset = _mk_asset(img, 'image/png', 'x.png')
    meta = ingest_asset(db, asset)
    assert meta['ocr_fallback_used'] is True


def test_scope_aware_retrieval_prefers_active_segment(monkeypatch):
    monkeypatch.setattr(asset_ingestion.EmbeddingProvider, 'embed_text', lambda self, t: ([1.0, 0.0, 0.0], {'mode': 'mock'}))
    monkeypatch.setattr(asset_ingestion.QdrantStore, 'search', lambda self, vector, limit, filter_payload=None: [])

    db = DummyDB()
    a1 = Asset(project_id=1, chat_thread_id=1, message_id=None, source_type='user_upload', asset_type='text', mime_type='text/plain', original_filename='s1.txt', stored_path='/tmp/s1', derived_metadata_json={}); a1.id = 10  # type: ignore[attr-defined]
    a2 = Asset(project_id=1, chat_thread_id=1, message_id=None, source_type='user_upload', asset_type='text', mime_type='text/plain', original_filename='s2.txt', stored_path='/tmp/s2', derived_metadata_json={}); a2.id = 11  # type: ignore[attr-defined]
    db.add(a1); db.add(a2)
    c1 = AssetChunk(asset_id=10, project_id=1, chat_thread_id=1, segment_id=7, chunk_index=0, content_text='deployment checklist for release', char_count=32, token_count=4, vector_id='v1', embedding_model='m', embedding_vector_json=[1.0, 0.0, 0.0], chunk_metadata_json={}); c1.id = 101  # type: ignore[attr-defined]
    c2 = AssetChunk(asset_id=11, project_id=1, chat_thread_id=1, segment_id=8, chunk_index=0, content_text='deployment checklist generic', char_count=25, token_count=3, vector_id='v2', embedding_model='m', embedding_vector_json=[1.0, 0.0, 0.0], chunk_metadata_json={}); c2.id = 102  # type: ignore[attr-defined]
    db.add(c1); db.add(c2)

    hits = retrieve_relevant_context(db, chat_thread_id=1, project_id=1, segment_id=7, query='deployment checklist', limit=2)
    assert hits
    assert hits[0]['segment_id'] == 7
