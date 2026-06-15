from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from metaos.core.schemas import Asset, AssetKind, Source, SourceType
from metaos.documents.service import ParsedDocument
from metaos.knowledge import (
    ClaimStance,
    ClaimType,
    EntityType,
    EvidenceRelation,
    SummaryLevel,
    extract_knowledge_foundation,
    standardize_document,
)


class KnowledgeFoundationTests(unittest.TestCase):
    def test_extract_knowledge_foundation_parses_structures_and_citations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "case.md"
            source = Source(id="src_1", type=SourceType.local_file, uri="file:///case.md")
            asset = Asset(id="asset_1", source_id=source.id, kind=AssetKind.markdown, path=path)
            document = ParsedDocument(
                title="Case",
                source_path=path,
                extension=".md",
                text="""
                # Case

                Entity: Alice | person | Founder
                Alias: Alice | A. | en
                Entity: Project X | project | Internal platform
                Event: 2026-06-15 | Launch | Alice launched Project X | Alice, Project X | Hangzhou
                Claim: fact | supports | Project X launched on schedule | 0.9
                Claim: interpretation | disputes | Launch reduced strategic risk | 0.4
                Summary: document | Launch case summary
                """,
            )
            standardized = standardize_document(source=source, asset=asset, document=document)

            foundation = extract_knowledge_foundation(standardized)

            self.assertEqual(foundation.document_version_id, standardized.document_version.id)
            self.assertEqual({entity.name for entity in foundation.entities}, {"Alice", "Project X"})
            alice = next(entity for entity in foundation.entities if entity.name == "Alice")
            self.assertEqual(alice.type, EntityType.person)
            self.assertEqual(alice.source_count, 1)
            self.assertEqual(foundation.aliases[0].entity_id, alice.id)
            self.assertEqual(foundation.aliases[0].alias, "A.")
            self.assertEqual(foundation.events[0].event_time, date(2026, 6, 15))
            self.assertEqual(foundation.events[0].participants, ["Alice", "Project X"])
            self.assertEqual(foundation.events[0].citations[0].file_path, path)
            self.assertEqual([claim.claim_type for claim in foundation.claims], [ClaimType.fact, ClaimType.interpretation])
            self.assertEqual([claim.stance for claim in foundation.claims], [ClaimStance.supports, ClaimStance.disputes])
            self.assertEqual(
                [link.relation for link in foundation.evidence_links],
                [EvidenceRelation.supports, EvidenceRelation.counters],
            )
            self.assertEqual(foundation.evidence_links[0].citation.source_id, source.id)
            self.assertEqual(foundation.summaries[0].level, SummaryLevel.document)
            self.assertEqual(foundation.summaries[0].target_id, standardized.document_version.id)
            self.assertEqual(foundation.summaries[0].citations[0].asset_id, asset.id)


if __name__ == "__main__":
    unittest.main()
