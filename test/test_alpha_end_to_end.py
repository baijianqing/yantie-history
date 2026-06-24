from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from metaos.censorate import AuditStatus, audit_research_answer, audit_research_quality
from metaos.chancellor import generate_chancellor_briefing, generate_weekly_report
from metaos.compiler import CompileResearchRequest, IssueCompiler, PROMPT_VERSION
from metaos.core.schemas import Asset, AssetKind, Chunk, Citation, Source, SourceType
from metaos.documents.service import ParsedDocument
from metaos.knowledge import extract_knowledge_foundation, standardize_document
from metaos.ledger import (
    ActionStatus,
    Decision,
    DecisionReversibility,
    DailyReview,
    WorkEvent,
    WorkEventSource,
    WorkEventType,
    generate_daily_summary,
)
from metaos.ministries import Ministry, RecommendationCandidate, generate_ministry_reports
from metaos.research import EvidenceAssessment, build_evidence_matrix, draft_research_answer
from metaos.search import SearchCandidate, full_text_search, rrf_fuse
from metaos.sovereignty import (
    AttentionBudget,
    CognitiveConstitution,
    CurrentRole,
    Intent,
    IntentHorizon,
    IntentStatus,
    NotToDoItem,
    NotToDoScope,
)
from metaos.workshop import (
    EpisodeReviewStatus,
    VideoRenderStatus,
    episode_from_daily_summary,
    generate_episode_assets,
    render_episode_video,
    review_episode,
)


class AlphaCompilerProvider:
    def __init__(self, source_id: str):
        self.source_id = source_id
        self.calls: list[dict[str, Any]] = []

    def compile_theme(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return {
            "operator": "decision_support",
            "theme_spec": {
                "theme_name": "Alpha closure",
                "theme_description": "Runtime-generated theme for closing the Alpha service loop.",
                "key_terms": ["MetaOS Alpha", "service closure", "evidence"],
                "synonyms": {"closure": ["end-to-end loop", "service-level acceptance"]},
                "positive_patterns": ["cited evidence", "explicit counterevidence"],
                "negative_patterns": ["uncited implementation claim"],
                "required_dimensions": ["intent", "knowledge", "audit", "action", "review"],
                "excluded_dimensions": ["generic news aggregation"],
                "evidence_preferences": {"citation_required": True, "counterevidence": True},
            },
            "evidence_requirements": [
                {
                    "requirement_type": "decision_criterion",
                    "description": "Decide whether the Alpha service loop has enough cited closure evidence.",
                    "required_count": 1,
                    "source_constraints": {"citation_required": True},
                    "counterevidence_required": True,
                }
            ],
            "research_scope": {
                "included_sources": [self.source_id],
                "excluded_sources": ["untrusted_feed"],
                "entity_filters": ["MetaOS Alpha"],
                "cost_limit": 45,
                "depth": "standard",
            },
            "research_plan": {
                "steps": [
                    {
                        "order": 1,
                        "operator": "decision_support",
                        "description": "Collect cited support and counterevidence before proposing action.",
                        "query_hints": ["MetaOS Alpha service closure evidence"],
                        "expected_evidence": ["supporting claim", "remaining gap"],
                    }
                ],
                "query_plan": ["MetaOS Alpha service closure evidence HTTP RQ"],
                "stop_conditions": ["evidence requirement satisfied and counterevidence observed"],
                "prompt_version": PROMPT_VERSION,
            },
        }


class AlphaEndToEndTests(unittest.TestCase):
    @unittest.skipIf(shutil.which("ffmpeg") is None, "ffmpeg is required for MP4 closure test")
    def test_alpha_service_loop_runs_from_intent_to_reviewable_video(self) -> None:
        today = date(2026, 6, 15)
        fixture_timestamp = datetime(2026, 6, 15, 10, tzinfo=timezone.utc)
        constitution = CognitiveConstitution(
            principles=["Intent constrains attention before questions are answered."],
            decision_rules=["Separate cited facts, inference, dispute, and reflection."],
            attention_rules=["Do not turn research into an infinite feed."],
            not_to_do_defaults=["Do not chase generic news."],
        )
        intent = Intent(
            id="intent_alpha",
            title="Ship MetaOS Alpha",
            description="Close the personal intent operating system loop.",
            horizon=IntentHorizon.quarter,
            status=IntentStatus.active,
            priority=5,
            success_criteria=["Every research result yields an action or explicit no-action."],
            constraints=["No new topic-specific Python branches."],
            constitution_id=constitution.id,
        )
        role = CurrentRole(
            id="role_builder",
            name="Alpha Builder",
            responsibilities=["Connect service modules with tests"],
            allowed_focus=["MetaOS Alpha closure"],
            forbidden_focus=["generic news feed"],
        )
        budget = AttentionBudget(
            id="budget_today",
            date=today,
            total_minutes=300,
            research_minutes=60,
            build_minutes=120,
            review_minutes=45,
            content_minutes=45,
        )
        not_to_do = NotToDoItem(
            title="Ignore unrelated trend scans",
            reason="Alpha closure needs evidence, not novelty.",
            scope=NotToDoScope.intent,
            related_intent_id=intent.id,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source, asset, parsed = self.fixture_document(root)
            standardized = standardize_document(source=source, asset=asset, document=parsed)
            foundation = extract_knowledge_foundation(standardized)
            core_chunks = self.core_chunks(standardized.document_version.stable_id, standardized.chunks)

            self.assertEqual(standardized.document_version.source_id, source.id)
            self.assertTrue(all(chunk.previous_chunk_id or chunk.ordinal == 1 for chunk in standardized.chunks))
            self.assertTrue(foundation.entities)
            self.assertTrue(foundation.claims)
            self.assertTrue(foundation.evidence_links)

            compiler_provider = AlphaCompilerProvider(source.id)
            compilation = IssueCompiler(compiler_provider).compile(
                CompileResearchRequest(
                    question="Should MetaOS Alpha closure be accepted for service-level review?",
                    intent_id=intent.id,
                    role_id=role.id,
                    attention_budget_id=budget.id,
                )
            )
            self.assertEqual(compilation.theme_spec.theme_name, "Alpha closure")
            self.assertEqual(compiler_provider.calls[0]["intent_id"], intent.id)

            search_results = full_text_search(
                "MetaOS Alpha service closure evidence HTTP RQ",
                chunks=core_chunks,
                filters={"source_id": source.id},
                top_k=5,
            )
            vector_results = [
                SearchCandidate(
                    chunk_id=chunk.id,
                    knowledge_item_id=chunk.knowledge_item_id,
                    text=chunk.text,
                    heading_path=chunk.heading_path,
                    ordinal=chunk.ordinal,
                    score=0.92 - (chunk.ordinal * 0.01),
                    citation=chunk.citation,
                )
                for chunk in core_chunks
            ]
            fused = rrf_fuse(
                {"full_text": search_results, "vector": vector_results},
                filters={"source_id": source.id},
                top_k=5,
            )
            self.assertGreaterEqual(len(search_results), 2)
            self.assertGreaterEqual(len(fused), 2)
            self.assertTrue(all(candidate.citation for candidate in fused))

            requirement = compilation.evidence_requirements[0]
            support = next(candidate for candidate in fused if "service flow links" in candidate.text)
            counter = next(candidate for candidate in fused if "HTTP job endpoints" in candidate.text)
            execution = build_evidence_matrix(
                compilation,
                [
                    support.model_copy(
                        update={"metadata": {"requirement_id": requirement.id, "stance": "support"}}
                    ),
                    counter.model_copy(
                        update={"metadata": {"requirement_id": requirement.id, "stance": "counter"}}
                    ),
                ],
            )
            self.assertEqual(execution.evidence_matrix[0].assessment, EvidenceAssessment.contested)
            self.assertEqual(execution.missing_evidence, [])

            answer = draft_research_answer(
                compilation,
                execution,
                conclusion=(
                    "MetaOS Alpha has enough cited service-level closure evidence for review, "
                    "while HTTP/RQ wiring remains a scoped follow-up."
                ),
                action_title="Review Alpha closure evidence and plan HTTP/RQ wiring",
                personal_reflections=["Keep the next task small and independently reversible."],
            )
            answer = answer.model_copy(update={"created_at": fixture_timestamp})
            self.assertEqual(answer.actions[0].status, ActionStatus.proposed)
            self.assertEqual(answer.actions[0].intent_id, intent.id)
            self.assertTrue(answer.fact_statements)
            self.assertTrue(answer.model_inferences)
            self.assertTrue(answer.disputed_views)
            self.assertTrue(answer.personal_reflections)

            citation_audit = audit_research_answer(answer, execution, compilation.research_scope)
            quality_audit = audit_research_quality(
                compilation,
                execution,
                attention_budget=budget,
                retrieval_cost_minutes=25,
                retrieval_channels=["full_text", "vector"],
            )
            self.assertEqual(citation_audit.status, AuditStatus.passed)
            self.assertEqual(quality_audit.status, AuditStatus.passed)

            review = DailyReview(
                id="review_today",
                date=today,
                facts=["Research answer completed with cited support and counterevidence."],
                judgments=["Service-level Alpha closure is reviewable."],
                reflections=["Attention stayed bounded by intent and budget."],
                actions_done=["Built end-to-end closure test"],
                actions_missed=["Draft weekly report"],
                lessons=["Counterevidence should be visible before action."],
            )
            work_event = WorkEvent(
                date=today,
                event_type=WorkEventType.research,
                title="Ran Alpha closure research",
                source=WorkEventSource.research_task,
                source_ref=compilation.research_task.id,
                related_intent_id=intent.id,
                citations=answer.citations,
            )
            decision = Decision(
                title="Accept service-level closure for review",
                context="The evidence matrix is contested but complete.",
                options=["accept", "defer"],
                chosen_option="accept",
                reasoning="Citation and quality audits passed.",
                evidence_links=answer.citations,
                reversibility=DecisionReversibility.reversible,
                decided_at=datetime(2026, 6, 15, 11, tzinfo=timezone.utc),
            )
            summary = generate_daily_summary(
                today,
                review,
                work_events=[work_event],
                decisions=[decision],
                actions=answer.actions,
            )
            self.assertIn("Research answer completed", summary.fact_summary)
            self.assertIn(answer.actions[0].title, summary.action_summary)
            self.assertTrue(summary.citations)

            episode = episode_from_daily_summary(summary, angle="Alpha closure review")
            assets = generate_episode_assets(episode, root / "assets")
            approved_episode = review_episode(
                episode,
                status=EpisodeReviewStatus.approved,
                reviewer_id="human_reviewer",
                reviewed_at=datetime(2026, 6, 15, 12, tzinfo=timezone.utc),
                review_notes="Approved for Alpha closure artifact.",
            )
            export = render_episode_video(approved_episode, assets, root / "exports")
            export = export.model_copy(
                update={"created_at": fixture_timestamp, "updated_at": fixture_timestamp}
            )
            self.assertEqual(export.render_status, VideoRenderStatus.succeeded)
            self.assertIsNotNone(export.mp4_path)
            assert export.mp4_path is not None
            self.assertTrue(export.mp4_path.exists())
            self.assertGreater(export.mp4_path.stat().st_size, 0)

            ministry_reports = generate_ministry_reports(
                today,
                intent=intent,
                attention_budget=budget,
                candidates=[
                    RecommendationCandidate(
                        ministry=Ministry.technology,
                        title="Wire HTTP/RQ contracts",
                        reason="The closure test identified service-level wiring as the next gap.",
                        intent_alignment="Supports Alpha acceptance",
                        reading_cost_minutes=20,
                        cost_of_ignoring="Manual-only closure remains fragile.",
                        suggested_action="Open the next narrow API/RQ wiring task.",
                        citations=answer.citations,
                        score=0.95,
                        intent_id=intent.id,
                    )
                ],
            )
            self.assertLessEqual(sum(len(report.items) for report in ministry_reports), 5)
            self.assertTrue(any(not report.items and report.empty_reason for report in ministry_reports))

            briefing = generate_chancellor_briefing(
                today,
                intent=intent,
                role=role,
                attention_budget=budget,
                daily_review=review,
                research_answers=[answer],
                ministry_reports=ministry_reports,
            )
            self.assertEqual(briefing.intent_id, intent.id)
            self.assertEqual(briefing.role_id, role.id)
            self.assertIn("Intent: Ship MetaOS Alpha", briefing.today_focus)
            self.assertIn(answer.actions[0].title, briefing.today_focus)
            self.assertIn("Draft weekly report", briefing.deferred_items)
            self.assertEqual(not_to_do.related_intent_id, intent.id)
            self.assertIn("generic news feed", briefing.ignored_items)
            self.assertEqual(briefing.source_research_ids, [answer.id])
            self.assertEqual(briefing.source_review_id, review.id)

            weekly_report = generate_weekly_report(
                date(2026, 6, 15),
                date(2026, 6, 21),
                intent=intent,
                daily_summaries=[summary],
                briefings=[briefing],
                research_answers=[answer],
                video_exports=[export],
            )
            self.assertEqual(weekly_report.intent_id, intent.id)
            self.assertEqual(weekly_report.daily_summary_ids, [summary.id])
            self.assertEqual(weekly_report.briefing_ids, [briefing.id])
            self.assertEqual(weekly_report.research_answer_ids, [answer.id])
            self.assertEqual(weekly_report.video_export_ids, [export.id])
            self.assertIn(answer.actions[0].title, weekly_report.pending_actions)
            self.assertIn(export.mp4_path.as_posix(), weekly_report.content_exports)

    def fixture_document(self, root: Path) -> tuple[Source, Asset, ParsedDocument]:
        path = root / "alpha-evidence.md"
        text = "\n".join(
            [
                "# Alpha Evidence",
                "",
                "## Service Closure",
                "",
                "Entity: MetaOS Alpha | project | Personal intent operating system alpha.",
                (
                    "Claim: fact | supports | MetaOS Alpha service flow links intent, "
                    "knowledge, evidence, audit, action, daily review, and video export. | 0.86"
                ),
                "Event: 2026-06-15 | Alpha closure exercise | Service-level closure test validates the core chain. | MetaOS Alpha | local",
                "Summary: document | Alpha closure evidence binds knowledge, research, and review artifacts.",
                "MetaOS Alpha service closure evidence confirms that a proposed Action is tied back to cited research.",
                "",
                "## Remaining Gap",
                "",
                (
                    "Claim: interpretation | disputes | HTTP job endpoints and durable RQ orchestration "
                    "still require later contract wiring. | 0.70"
                ),
                "HTTP RQ counterevidence shows the service closure is not yet full production automation.",
            ]
        )
        path.write_text(text, encoding="utf-8")
        source = Source(id="src_alpha", type=SourceType.local_file, uri=path.as_uri(), title="Alpha Evidence")
        asset = Asset(id="asset_alpha", source_id=source.id, kind=AssetKind.markdown, path=path)
        parsed = ParsedDocument(title="Alpha Evidence", text=text, source_path=path, extension=".md")
        return source, asset, parsed

    def core_chunks(self, knowledge_item_id: str, chunks) -> list[Chunk]:
        return [
            Chunk(
                id=chunk.id,
                knowledge_item_id=knowledge_item_id,
                text=chunk.text,
                heading_path=chunk.heading_path,
                ordinal=chunk.ordinal,
                char_count=chunk.char_count,
                citation=chunk.citation,
            )
            for chunk in chunks
        ]


if __name__ == "__main__":
    unittest.main()
