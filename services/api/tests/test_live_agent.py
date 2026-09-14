"""Structured output, evidence validation, resume, and live-orchestration tests."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
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

from app.agent.apply import store_assessment
from app.agent.evidence import EvidenceValidationError, validate_patch_proposal
from app.agent.runner import enqueue_resume_job, run_live
from app.agent.schemas import ListingDraft, MatchOutcomeLabel, ProductAssessment, ProductPatchProposal
from app.agent.tools import ToolContext, set_tool_context
from app.config import get_settings
from app.db.models import (
    Batch,
    BatchKind,
    Decision,
    DecisionStatus,
    EvidenceAcceptance,
    FieldEvidence,
    Job,
    JobStatus,
    MatchOutcome,
    Product,
    ProductStatus,
    ProductVersion,
    StoreProduct,
    Workspace,
)
from app.db.session import SessionLocal
from app.enrichment.service import EnrichmentBudget, enrich_product, get_provider
from app.services.catalog import process_product

get_settings.cache_clear()


class FakeResult:
    def __init__(self, structured_output, message="ok"):
        self.structured_output = structured_output
        self.message = message


class FakeAgent:
    """Controlled agent: optional tool call, then scripted structured outputs."""

    def __init__(self, outputs, tool=None):
        self.outputs = list(outputs)
        self.tool = tool
        self.calls: list[tuple[str, type | None]] = []

    def __call__(self, prompt, structured_output_model=None, **kwargs):
        self.calls.append((prompt, structured_output_model))
        if self.tool and structured_output_model is ProductAssessment:
            self.tool()
        if not self.outputs:
            raise RuntimeError("structured_output_failed:no_scripted_output")
        out = self.outputs.pop(0)
        if out == "FAIL":
            raise RuntimeError("structured_output_failed:forced")
        if structured_output_model and not isinstance(out, structured_output_model):
            raise RuntimeError("structured_output_failed:wrong_type")
        return FakeResult(out)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _product(db, sku="HC-COKE-01", original=None):
    ws = db.scalar(select(Workspace).limit(1))
    batch = Batch(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        name="live-test",
        supplier_name="t",
        batch_kind=BatchKind.demo,
        counts={},
    )
    db.add(batch)
    db.flush()
    product = Product(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        batch_id=batch.id,
        sku=sku,
        supplier_sku=sku,
        status=ProductStatus.imported,
    )
    db.add(product)
    db.flush()
    original = original or {
        "sku": sku,
        "title": "Coca-Cola",
        "brand": "Coca-Cola",
        "upc": "049000028911",
        "price": "1.99",
        "currency": "USD",
        "stock": "10",
    }
    version = process_product(db, product, original)
    db.flush()
    return product, version, batch


def test_structured_assessment_is_consumed(db):
    product, version, _ = _product(db)
    ev = FieldEvidence(
        id=uuid.uuid4(),
        product_id=product.id,
        product_version_id=version.id,
        field_name="title",
        original_supplier_value="Coca-Cola",
        proposed_value="Coca-Cola Classic",
        source_provider="replay",
        match_outcome=MatchOutcome.matching_evidence,
        match_explanation="titles match",
        acceptance_status=EvidenceAcceptance.pending,
    )
    db.add(ev)
    db.flush()
    assessment = ProductAssessment(
        candidate_identifier="049000028911",
        match_outcome=MatchOutcomeLabel.matching_evidence,
        attribute_agreements=[
            {
                "field_name": "title",
                "supplier_value": "Coca-Cola",
                "evidence_value": "Coca-Cola Classic",
                "evidence_ids": [str(ev.id)],
            }
        ],
        evidence_references=[str(ev.id)],
        explanation="Barcode record confirms the title.",
        recommended_action="none",
    )
    stored = store_assessment(db, product, version, assessment, run_id=uuid.uuid4())
    db.refresh(version)
    assert version.provenance["assessment"]["explanation"] == stored.explanation
    assert version.provenance["assessment"]["product_id"] == str(product.id)
    assert db.get(FieldEvidence, ev.id).acceptance_status == EvidenceAcceptance.accepted


def test_unknown_evidence_id_rejected(db):
    product, version, _ = _product(db, sku="HC-UNK-01")
    assessment = ProductAssessment(
        candidate_identifier=None,
        match_outcome=MatchOutcomeLabel.no_match,
        evidence_references=[str(uuid.uuid4())],
        explanation="Invented evidence",
    )
    with pytest.raises(EvidenceValidationError, match="unknown_evidence"):
        store_assessment(db, product, version, assessment, run_id=uuid.uuid4())


def test_unrelated_evidence_id_rejected(db):
    product_a, version_a, _ = _product(db, sku="HC-A-01")
    product_b, version_b, _ = _product(db, sku="HC-B-01")
    ev = FieldEvidence(
        id=uuid.uuid4(),
        product_id=product_b.id,
        product_version_id=version_b.id,
        field_name="title",
        source_provider="replay",
        match_outcome=MatchOutcome.matching_evidence,
        match_explanation="other product",
    )
    db.add(ev)
    db.flush()
    assessment = ProductAssessment(
        candidate_identifier=None,
        match_outcome=MatchOutcomeLabel.matching_evidence,
        evidence_references=[str(ev.id)],
        explanation="Wrong product evidence",
    )
    with pytest.raises(EvidenceValidationError, match="unrelated_evidence"):
        store_assessment(db, product_a, version_a, assessment, run_id=uuid.uuid4())


def test_stale_revision_cannot_receive_proposal(db):
    product, version, _ = _product(db, sku="HC-STALE-01")
    ev = FieldEvidence(
        id=uuid.uuid4(),
        product_id=product.id,
        product_version_id=version.id,
        field_name="brand",
        source_provider="replay",
        match_outcome=MatchOutcome.matching_evidence,
        match_explanation="brand matches",
    )
    db.add(ev)
    newer = ProductVersion(
        id=uuid.uuid4(),
        product_id=product.id,
        version_number=version.version_number + 1,
        original=version.original,
        proposed=dict(version.proposed),
        seo=version.seo,
        diffs=[],
        provenance={},
        is_publishable=False,
        blockers=[],
    )
    db.add(newer)
    db.flush()
    product.current_version_id = newer.id
    db.flush()
    proposal = ProductPatchProposal(
        field="brand",
        proposed_value="Coca-Cola",
        evidence_references=[str(ev.id)],
        explanation="stale",
    )
    with pytest.raises(EvidenceValidationError, match="stale_product_revision"):
        validate_patch_proposal(db, product, newer, proposal, expected_version_id=version.id)


def test_listing_draft_rejects_authenticity_claims(db):
    from app.agent.evidence import validate_listing_draft

    product, version, _ = _product(db, sku="HC-AUTH-01")
    draft = ListingDraft(
        title="Authentic certified soda",
        description="Genuine article",
        seo_title="Authentic",
        meta_description="certified",
        supporting_fact_ids=[],
    )
    with pytest.raises(EvidenceValidationError, match="authenticity"):
        validate_listing_draft(db, product, version, draft)


def test_decision_resume_targets_resolved_product(db):
    product, _, batch = _product(db, sku="HC-RES-01")
    job = enqueue_resume_job(db, batch, [str(product.id)], agent_mode="live")
    db.commit()
    assert job is not None
    assert job.job_type == "resume"
    assert job.checkpoint["product_ids"] == [str(product.id)]
    other = Job(
        id=uuid.uuid4(),
        batch_id=batch.id,
        job_type="process",
        status=JobStatus.pending,
        agent_mode="live",
        checkpoint={},
    )
    db.add(other)
    db.commit()
    assert enqueue_resume_job(db, batch, [str(product.id)], agent_mode="live") is None
    job.status = JobStatus.completed
    other.status = JobStatus.completed
    db.commit()


def test_live_structured_output_failure_is_truthful(db, monkeypatch):
    from app.agent import runner as runner_mod

    product, _, batch = _product(db, sku="HC-FAIL-01")
    job = Job(
        id=uuid.uuid4(),
        batch_id=batch.id,
        job_type="process",
        status=JobStatus.pending,
        agent_mode="live",
        checkpoint={},
    )
    db.add(job)
    db.commit()
    monkeypatch.setattr(runner_mod, "run_deterministic_processing", lambda *a, **k: {"processed": 0, "pending_decisions": 0})
    monkeypatch.setattr(runner_mod, "_build_strands_agent", lambda recorder=None: FakeAgent(["FAIL"]))
    ctx = ToolContext(db, job, batch)
    set_tool_context(ctx)
    try:
        with pytest.raises(Exception, match="structured_output_failed"):
            run_live(ctx)
        assert job.status == JobStatus.failed
        assert "replay" not in (job.error or "").lower() or "no replay" in (job.error or "").lower()
    finally:
        set_tool_context(None)


def test_live_orchestration_uses_lookup_and_assessment(db, monkeypatch):
    from app.agent import runner as runner_mod

    product, version, batch = _product(db, sku="HC-LIVE-01")
    provider = get_provider(ROOT / "fixtures")
    enrich_product(db, product, version, version.original, provider, EnrichmentBudget(5))
    db.flush()
    evidence = db.scalars(select(FieldEvidence).where(FieldEvidence.product_id == product.id)).all()
    ev_ids = [str(e.id) for e in evidence]
    assert ev_ids

    assessment = ProductAssessment(
        candidate_identifier="049000028911",
        match_outcome=MatchOutcomeLabel.matching_evidence,
        evidence_references=ev_ids[:1],
        explanation="Lookup evidence confirms this household soda.",
        recommended_action="none",
    )
    called = {"lookup": False}

    def tool():
        called["lookup"] = True
        from app.agent.tools import lookup_product_identifier

        lookup_product_identifier(str(product.id))

    agent = FakeAgent([assessment], tool=tool)
    job = Job(
        id=uuid.uuid4(),
        batch_id=batch.id,
        job_type="process",
        status=JobStatus.pending,
        agent_mode="live",
        checkpoint={"processed_ids": [str(product.id)]},
    )
    db.add(job)
    db.commit()
    monkeypatch.setattr(runner_mod, "run_deterministic_processing", lambda *a, **k: {"processed": 0, "pending_decisions": 0})
    monkeypatch.setattr(runner_mod, "_build_strands_agent", lambda recorder=None: agent)
    ctx = ToolContext(db, job, batch)
    set_tool_context(ctx)
    try:
        result = run_live(ctx)
        assert result["assessments"] == 1
        assert called["lookup"] is True
        db.refresh(version)
        assert version.provenance.get("assessment", {}).get("explanation") == assessment.explanation
        assert any(c[1] is ProductAssessment for c in agent.calls)
    finally:
        set_tool_context(None)


def test_publication_retry_does_not_duplicate(db):
    from app.agent.runner import run_publish_pass
    from app.agent.tools import publish_product, set_tool_context, ToolContext

    product, version, batch = _product(db, sku="HC-PUB-01")
    for d in db.scalars(select(Decision).where(Decision.product_id == product.id)).all():
        d.status = DecisionStatus.rejected
        d.resolved_at = datetime.now(timezone.utc)
    product.status = ProductStatus.ready
    product.approved_version_id = version.id
    version.is_publishable = True
    version.blockers = []
    db.flush()
    job = Job(
        id=uuid.uuid4(),
        batch_id=batch.id,
        job_type="publish",
        status=JobStatus.pending,
        agent_mode="replay",
        checkpoint={"product_ids": [str(product.id)]},
    )
    db.add(job)
    db.commit()
    ctx = ToolContext(db, job, batch)
    set_tool_context(ctx)
    try:
        first = publish_product(str(product.id))
        assert first.get("store_product_id")
        run_publish_pass(ctx, [str(product.id)])
        run_publish_pass(ctx, [str(product.id)])
        twins = db.scalars(select(StoreProduct).where(StoreProduct.product_id == product.id)).all()
        assert len(twins) == 1
    finally:
        set_tool_context(None)
