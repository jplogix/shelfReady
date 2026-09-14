"""Seed workspace and optional baseline normalization rules (inactive until approved)."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.config import get_settings
from app.db.models import NormalizationRule, RuleScope, Workspace
from app.db.session import SessionLocal


def seed() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        ws = db.scalar(select(Workspace).limit(1))
        if not ws:
            ws = Workspace(
                id=uuid.uuid4(),
                name=settings.workspace_name,
                auto_publish_demo=False,
                currency=settings.currency_default,
            )
            db.add(ws)
            db.flush()
            print(f"Created workspace {ws.id} ({ws.name})")
        else:
            print(f"Workspace exists: {ws.id} ({ws.name})")

        # Seed inactive suggested rules (operator must approve to activate — already active seed
        # aliases live in code; these demonstrate persisted rule storage)
        existing = db.scalar(select(NormalizationRule).limit(1))
        if not existing:
            suggestions = [
                ("brand", "GUCCI", "Gucci"),
                ("brand", "Gucci Eyewear", "Gucci"),
                ("color", "BLK/GLD", "Black,Gold"),
            ]
            for rtype, src, tgt in suggestions:
                db.add(
                    NormalizationRule(
                        id=uuid.uuid4(),
                        workspace_id=ws.id,
                        rule_type=rtype,
                        source_value=src,
                        target_value=tgt,
                        scope=RuleScope.workspace,
                        active=False,
                    )
                )
            print("Seeded inactive suggested normalization rules")
        db.commit()
    finally:
        db.close()

    from app.services.bootstrap_storefront import ensure_public_storefront

    ensure_public_storefront()


if __name__ == "__main__":
    seed()
