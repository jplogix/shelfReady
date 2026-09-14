"""Create or reset an isolated Seiko demonstration batch. Default is dry-run."""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

from sqlalchemy import select

os.environ.setdefault("AGENT_MODE", "replay")
os.environ.setdefault("LOOKUP_PROVIDER", "replay")

from app.agent.runner import execute_job
from app.api.routes import import_fixture_batch, start_process, start_publish
from app.api.schemas import PublishRequest
from app.db.models import Batch, BatchKind, Job, JobStatus, Product, StoreProduct
from app.db.session import SessionLocal
from app.policy.readiness import refresh_product_readiness
from app.services.bootstrap_storefront import _accept_safe_decisions, ready_public_demo_ids
from app.services.demo_catalog import canonical_sku, PUBLIC_FEATURED_SKUS


def main() -> None:
    parser = argparse.ArgumentParser(description="Isolated Seiko demo reset (does not delete unrelated catalogs).")
    parser.add_argument("--apply", action="store_true", help="Create a fresh Seiko batch, process, approve safe decisions, publish featured SKUs.")
    args = parser.parse_args()
    db = SessionLocal()
    existing = list(db.scalars(select(Batch).where(Batch.source_filename == "seiko_demo_catalog.csv")).all())
    featured = []
    for row in db.scalars(select(StoreProduct)).all():
        product = db.get(Product, row.product_id)
        sku = (product.supplier_sku or product.sku) if product else row.variant_sku
        if canonical_sku(sku) in PUBLIC_FEATURED_SKUS:
            featured.append(row)
    print(f"Existing Seiko-named batches: {len(existing)}")
    print(f"Published featured Seiko store rows: {len(featured)}")
    if not args.apply:
        print("Dry-run. Re-run with --apply to import a new isolated Seiko batch and publish eligible featured SKUs.")
        print("Household and stress-test batches are left unchanged. No production data is deleted.")
        db.close()
        return
    for job in db.scalars(select(Job).where(Job.status.in_([JobStatus.pending, JobStatus.running]))).all():
        job.status = JobStatus.failed
        job.error = "cleared_for_seiko_reset"
    db.commit()
    batch = import_fixture_batch(
        db,
        csv_name="seiko_demo_catalog.csv",
        batch_name=f"Seiko demonstration · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
        supplier_name="Pacific Watch Distributors",
        batch_kind=BatchKind.demo,
    )
    print(f"Imported batch {batch.id}")
    hero = db.scalar(select(Product).where(Product.batch_id == batch.id, Product.sku == "SK-SRPD55-01"))
    assert hero and not hero.images
    job = start_process(batch.id, db)
    execute_job(db, str(job.id))
    _accept_safe_decisions(db, batch.id)
    for product in db.scalars(select(Product).where(Product.batch_id == batch.id)).all():
        refresh_product_readiness(db, product)
    db.commit()
    ready = ready_public_demo_ids(db, batch.id)
    print(f"Ready featured products: {len(ready)}")
    if ready:
        pub = start_publish(batch.id, PublishRequest(product_ids=ready, verify=True), db)
        result = execute_job(db, str(pub.id))
        print(result)
    db.close()


if __name__ == "__main__":
    main()
