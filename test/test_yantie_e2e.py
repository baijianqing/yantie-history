from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metaos.yantie import render_yantie_static_html


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "docs" / "yantie"
SOURCE_PACK = ROOT / "metaos" / "yantie" / "data" / "evidence_pack.json"
STATIC_PACK = STATIC_ROOT / "data" / "evidence_pack.json"


def _static_files() -> set[str]:
    return {path.relative_to(STATIC_ROOT).as_posix() for path in STATIC_ROOT.rglob("*") if path.is_file()}


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key))
            keys.update(_walk_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(_walk_keys(item))
    return keys


def test_yantie_e2e_static_delivery_package_is_offline_and_lightweight() -> None:
    files = _static_files()
    required_files = {
        ".nojekyll",
        "index.html",
        "data/evidence_pack.json",
        "assets/audio/narrative.mp3",
        "assets/audio/debate.mp3",
        "assets/audio/reflection.mp3",
    }
    assert required_files <= files

    blocked_suffixes = {".db", ".sqlite", ".sqlite3", ".faiss", ".parquet", ".pkl", ".npy", ".bin"}
    blocked_name_tokens = {"chroma", "vector", "embedding", "rag_intermediate", "library", "raw_corpus"}
    for relative_path in files:
        lowered = relative_path.lower()
        assert Path(lowered).suffix not in blocked_suffixes
        assert not any(token in lowered for token in blocked_name_tokens)

    total_bytes = sum((STATIC_ROOT / relative_path).stat().st_size for relative_path in files)
    assert total_bytes < 25 * 1024 * 1024

    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    assert 'data-yantie-runtime="static"' in html
    assert 'const staticPackUrl = "data/evidence_pack.json";' in html
    assert "external_echo_enabled: false" in html
    assert "writes_to_evidence_pack: false" in html


def test_yantie_e2e_static_export_matches_source_of_truth() -> None:
    assert STATIC_PACK.read_text(encoding="utf-8") == SOURCE_PACK.read_text(encoding="utf-8")
    assert (STATIC_ROOT / "index.html").read_text(encoding="utf-8") == render_yantie_static_html()


def test_yantie_e2e_evidence_pack_claims_are_closed_and_auditable() -> None:
    pack = json.loads(STATIC_PACK.read_text(encoding="utf-8"))
    evidence_ids = {item["evidence_id"] for item in pack["evidence_units"]}
    source_ids = {item["source_id"] for item in pack["sources"]}

    assert pack["schema_version"] == "yantie_evidence_pack_v1"
    assert pack["pack_id"] == "yantie_meeting_v1"
    assert len(pack["sources"]) >= 4
    assert len(pack["actors"]) >= 6
    assert len(pack["events"]) >= 8
    assert len(pack["evidence_units"]) >= 20
    assert len(pack["claims"]) >= 12
    assert len(pack["relations"]) >= 20
    assert pack["external_references"] == []

    for evidence in pack["evidence_units"]:
        assert evidence["source_id"] in source_ids
        assert evidence["canonical_location"]
        assert evidence["paraphrase_zh"]
        assert evidence["review_status"] == "verified"
        assert evidence["copyright_note"]

    for claim in pack["claims"]:
        if claim["claim_type"] == "personal_reflection_prompt":
            assert claim["display_zone"] == "judgment_card"
            assert not claim["evidence_ids"]
            assert not claim["counterevidence_ids"]
            assert not claim["external_reference_ids"]
            continue
        assert claim["evidence_ids"]
        assert set(claim["evidence_ids"]) <= evidence_ids
        assert set(claim.get("counterevidence_ids") or []) <= evidence_ids
        assert not claim.get("external_reference_ids")

    forbidden_keys = {"embedding", "vector", "chunk_embedding", "raw_fulltext", "rag_context"}
    assert forbidden_keys.isdisjoint(_walk_keys(pack))


def test_yantie_e2e_acceptance_runner_covers_delivery_gate() -> None:
    script = (ROOT / "scripts" / "check-yantie-acceptance.mjs").read_text(encoding="utf-8")

    for scenario in [
        "opening-map",
        "first-choice",
        "standpoint-entry",
        "court-entry",
        "fiscal-livelihood",
        "key-evidence",
        "power-silence",
        "retirement-dossier",
        "post-court-explorer",
    ]:
        assert f'"{scenario}"' in script

    assert 'name: "desktop", width: 1440, height: 960' in script
    assert 'name: "mobile", width: 390, height: 844' in script
    assert 'name: "reduced-motion", width: 390, height: 844' in script
    assert '--base-url <url>' in script
    assert '--screenshot-dir <path>' in script
    assert "dossier overlaps debate HUD" in script
    assert "post-court details not expanded" in script
    assert 'scenarioId === "power-silence"' in script
