"""Manufacturer recovery, image fetch safety, and Seiko demo publication."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://shelfready:shelfready@localhost:55433/shelfready"
)
os.environ.setdefault("SHELFREADY_API_TOKEN", "dev-token-change-me")
os.environ.setdefault("AGENT_MODE", "replay")
os.environ.setdefault("LOOKUP_PROVIDER", "replay")
os.environ.setdefault("FIXTURES_ROOT", str(ROOT / "fixtures"))
os.environ.setdefault("STORAGE_ROOT", str(ROOT / "storage"))

from app.agent.evidence import EvidenceValidationError, validate_assessment
from app.agent.runner import execute_job
from app.agent.schemas import IdentityMatchStatus, MatchOutcomeLabel, ProductAssessment
from app.api.routes import import_fixture_batch, start_process, start_publish
from app.api.schemas import PublishRequest
from app.config import get_settings
from app.db.models import (
    BatchKind,
    Decision,
    DecisionKind,
    DecisionStatus,
    FieldEvidence,
    Job,
    JobStatus,
    Product,
    ProductImage,
    StoreProduct,
)
from app.db.session import SessionLocal
from app.main import app
from app.policy.readiness import refresh_product_readiness
from app.policy.safe_fetch import FetchError, assert_safe_url, resolve_redirect
from app.policy.watch_specs import model_token_in_asset
from app.services.bootstrap_storefront import _accept_safe_decisions, ready_public_demo_ids
from app.services.catalog import process_product
from app.services.demo_catalog import PUBLIC_FEATURED_SKUS
from app.services.manufacturer_recovery import retrieve_manufacturer_record

get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_private_fetch_destinations_rejected():
    with pytest.raises(FetchError, match="host_not_allowed"):
        assert_safe_url("https://example.com/x")
    with pytest.raises(FetchError, match="unsafe_scheme"):
        assert_safe_url("http://www.seikowatches.com/x")
    with pytest.raises(FetchError, match="host_not_allowed"):
        assert_safe_url("https://127.0.0.1/x")
    with pytest.raises(FetchError, match="host_not_allowed"):
        resolve_redirect(
            "https://www.seikowatches.com/us-en/products/5sports/srpd55",
            "https://127.0.0.1/secret",
        )


def test_model_token_does_not_match_shorter_prefix():
    assert model_token_in_asset("SRPD55", "SRPD55K1.png")
    assert not model_token_in_asset("SRPD55", "SRPD51K1.png")
    assert not model_token_in_asset("SRPD5", "SRPD55K1.png")


def test_color_families_not_lost_when_color_label_exists():
    from app.policy.normalize import normalize_colors

    result = normalize_colors("BLK/GLD")
    assert result.original == "BLK/GLD"
    assert result.normalized == ["Black", "Gold"]


def _clear_jobs(db):
    for job in db.scalars(select(Job).where(Job.status.in_([JobStatus.pending, JobStatus.running]))).all():
        job.status = JobStatus.failed
        job.error = "cleared_for_seiko_test"
    db.commit()


def test_missing_image_hero_obtains_asset_through_service():
    db = SessionLocal()
    try:
        _clear_jobs(db)
        batch = import_fixture_batch(
            db,
            csv_name="seiko_demo_catalog.csv",
            batch_name=f"Seiko recovery test {uuid.uuid4()}",
            supplier_name="Pacific Watch Distributors",
            batch_kind=BatchKind.demo,
        )
        job = start_process(batch.id, db)
        execute_job(db, str(job.id))
        hero = db.scalar(select(Product).where(Product.batch_id == batch.id, Product.sku == "SK-SRPD55-01"))
        assert hero is not None
        version = hero.versions[0]
        assert not version.original.get("image_filename")
        assert hero.images, "Runtime recovery should attach a stored asset"
        img = hero.images[0]
        assert img.checksum_sha256
        assert img.source_kind == "manufacturer_product_page"
        ev = db.scalars(select(FieldEvidence).where(FieldEvidence.product_id == hero.id, FieldEvidence.field_name == "primary_image")).first()
        assert ev is not None
        assert ev.source_provider == "seiko_manufacturer"
        assert ev.is_replay is True
        again = retrieve_manufacturer_record(db, hero)
        assert again.get("ok")
        assert len(hero.images) == 1
        amb = db.scalar(select(Product).where(Product.batch_id == batch.id, Product.sku == "SK-SEIKO5-AMB"))
        assert amb is not None
        assert not amb.images
        wrong = db.scalar(select(Product).where(Product.batch_id == batch.id, Product.sku == "SK-SRPD53-01"))
        assert wrong is not None
        pending = list(
            db.scalars(
                select(Decision).where(
                    Decision.product_id == wrong.id,
                    Decision.status == DecisionStatus.pending,
                    Decision.kind == DecisionKind.conflicting_variant,
                )
            )
        )
        assert pending
        _accept_safe_decisions(db, batch.id)
        for product in db.scalars(select(Product).where(Product.batch_id == batch.id)).all():
            refresh_product_readiness(db, product)
        db.commit()
        ready_ids = ready_public_demo_ids(db, batch.id)
        assert ready_ids
        skus = {p.sku for p in db.scalars(select(Product).where(Product.id.in_(ready_ids))).all()}
        assert "SK-SEIKO5-AMB" not in skus
        assert "SK-SRPD53-01" not in skus
        pub = start_publish(batch.id, PublishRequest(product_ids=ready_ids, verify=True), db)
        result = execute_job(db, str(pub.id))
        assert result.get("published", 0) >= 1, result
        hero = db.get(Product, hero.id)
        assert hero.images
        primary = next(i for i in hero.images if i.is_primary)
        assert hero.store_product_id
        store = db.get(StoreProduct, hero.store_product_id)
        assert store is not None
        assert store.product_id == hero.id
        assert store.primary_image_path
        assert primary.derivative_path in store.primary_image_path or primary.original_path in store.primary_image_path
        assert hero.verification_passed is True
    finally:
        db.close()


def test_assessment_cannot_cite_missing_or_stale_evidence():
    db = SessionLocal()
    try:
        from app.db.models import Batch, ProductStatus, ProductVersion, Workspace

        ws = db.scalar(select(Workspace).limit(1))
        batch = Batch(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            name="assess-test",
            supplier_name="t",
            batch_kind=BatchKind.demo,
        )
        db.add(batch)
        db.flush()
        product = Product(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            batch_id=batch.id,
            sku="SK-TEST-01",
            status=ProductStatus.imported,
        )
        db.add(product)
        db.flush()
        version = ProductVersion(
            id=uuid.uuid4(),
            product_id=product.id,
            version_number=1,
            original={"sku": "SK-TEST-01"},
            proposed={"sku": "SK-TEST-01"},
            seo={},
            diffs=[],
            provenance={},
        )
        db.add(version)
        db.flush()
        product.current_version_id = version.id
        assessment = ProductAssessment(
            product_id=str(product.id),
            input_revision_id=str(version.id),
            identity_match=IdentityMatchStatus.exact_model_match,
            match_outcome=MatchOutcomeLabel.matching_evidence,
            evidence_references=[str(uuid.uuid4())],
            explanation="fake",
        )
        with pytest.raises(EvidenceValidationError, match="unknown_evidence"):
            validate_assessment(db, product, version, assessment)
        newer = ProductVersion(
            id=uuid.uuid4(),
            product_id=product.id,
            version_number=2,
            original=version.original,
            proposed=version.proposed,
            seo={},
            diffs=[],
            provenance={},
        )
        db.add(newer)
        db.flush()
        product.current_version_id = newer.id
        assessment2 = ProductAssessment(
            product_id=str(product.id),
            input_revision_id=str(version.id),
            match_outcome=MatchOutcomeLabel.matching_evidence,
            explanation="stale",
        )
        with pytest.raises(EvidenceValidationError, match="stale_product_revision"):
            validate_assessment(db, product, newer, assessment2)
    finally:
        db.rollback()
        db.close()


def test_public_evidence_omits_demo_scenario_and_protected_fields(client):
    listed = client.get("/api/store/products")
    if listed.status_code != 200 or not listed.json():
        pytest.skip("No published store products in this database")
    slug = listed.json()[0]["slug"]
    body = client.get(f"/api/store/products/{slug}/provenance").json()
    blob = str(body)
    assert "demo_scenario" not in blob
    assert "raw_response" not in blob
    assert "SHELFREADY" not in blob
    assert "API_TOKEN" not in blob
