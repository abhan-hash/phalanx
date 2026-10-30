"""Unit tests for Threat Reconnaissance and Nebius Serverless Jobs."""

from phalanx.jobs import NebiusJobDispatcher
from phalanx.recon import ThreatRecon


def test_threat_recon_search():
    recon = ThreatRecon()
    report = recon.search_threats(query="LLM agent CVE prompt injection", max_results=3)
    assert len(report.findings) >= 1
    assert report.query is not None
    assert report.findings[0].title is not None
    assert report.findings[0].extracted_mechanic is not None


def test_nebius_job_manifest():
    dispatcher = NebiusJobDispatcher()
    manifest = dispatcher.generate_manifest(workers=4)
    assert manifest["apiVersion"] == "serverless.nebius.ai/v1alpha1"
    assert manifest["kind"] == "ServerlessJob"
    assert "matrix" in manifest["spec"]
    assert len(manifest["spec"]["matrix"]) >= 6


def test_nebius_job_execution():
    dispatcher = NebiusJobDispatcher()
    pairs = [("fake-ceo", "acme-roofing-bec")]
    modes = ["standard", "naive"]
    summary = dispatcher.execute_job(pairs=pairs, blue_modes=modes, workers=2, max_turns=4)

    assert summary.total_fights == 2
    assert summary.job_id.startswith("nebius-job-")
    assert summary.duration_seconds >= 0.0
    assert len(summary.results) == 2
