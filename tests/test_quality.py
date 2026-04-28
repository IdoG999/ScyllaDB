from __future__ import annotations

import unittest

from src.lead_finder import identify_relevant_leads
from src.linkedin_api_client import _extract_results
from src.models import LeadCandidate, ScoredLead
from src.personalizer import generate_messages_with_mock_llm


class LeadQualityTests(unittest.TestCase):
    def test_non_technical_influencer_not_selected(self) -> None:
        candidate = LeadCandidate(
            full_name="Test Influencer",
            headline="Top Voice and business influencer",
            current_company="Independent",
            title="Influencer",
            location="Israel",
            profile_url="https://www.linkedin.com/in/test-influencer",
            skills=["Public Speaking", "Marketing"],
            summary="Builds social media audience.",
            source="manual_research_seed",
        )
        [scored] = identify_relevant_leads([candidate], threshold=60)
        self.assertFalse(scored.selected)
        self.assertLess(scored.relevance_score, 60)

    def test_cassandra_engineer_selected(self) -> None:
        candidate = LeadCandidate(
            full_name="Test Engineer",
            headline="Senior Backend Engineer - Data Infra",
            current_company="DataStax",
            title="Senior Backend Engineer",
            location="Israel",
            profile_url="https://www.linkedin.com/in/test-engineer",
            skills=["Cassandra", "NoSQL", "Distributed Systems"],
            summary="Owns low-latency distributed data services.",
            source="manual_research_seed",
        )
        [scored] = identify_relevant_leads([candidate], threshold=60)
        self.assertTrue(scored.selected)
        self.assertGreaterEqual(scored.relevance_score, 60)

    def test_source_does_not_auto_force_score(self) -> None:
        candidate = LeadCandidate(
            full_name="Favikon Style Source",
            headline="Marketing influencer",
            current_company="Independent",
            title="Top Voice",
            location="Israel",
            profile_url="https://www.linkedin.com/in/favikon-style",
            skills=["Personal Branding"],
            summary="No database relevance.",
            source="Favikon 2026",
        )
        [scored] = identify_relevant_leads([candidate], threshold=60)
        self.assertLess(scored.relevance_score, 60)
        self.assertFalse(scored.selected)

    def test_unverified_source_is_not_selected_even_if_relevant_text(self) -> None:
        candidate = LeadCandidate(
            full_name="Generated Candidate",
            headline="Senior Data Platform Engineer",
            current_company="DataStax",
            title="Senior Data Platform Engineer",
            location="Israel",
            profile_url="https://www.linkedin.com/in/generated-candidate",
            skills=["Cassandra", "NoSQL", "Distributed Systems"],
            summary="Owns distributed data systems.",
            source="gemini_generated_unverified",
        )
        [scored] = identify_relevant_leads([candidate], threshold=60)
        self.assertFalse(scored.selected)


class PersonalizationTests(unittest.TestCase):
    def test_mock_personalization_is_contextual(self) -> None:
        scored = ScoredLead(
            candidate=LeadCandidate(
                full_name="Alex Infra",
                headline="SRE for data services",
                current_company="DataStax",
                title="SRE",
                location="Israel",
                profile_url="https://www.linkedin.com/in/alex-infra",
                skills=["Cassandra", "Kubernetes", "SRE"],
                summary="Improves reliability of distributed data clusters.",
                source="manual_research_seed",
            ),
            relevance_score=82,
            reason="title match: sre; skills match: cassandra, kubernetes",
            selected=True,
        )
        messages = generate_messages_with_mock_llm(scored, prompt_template="unused")
        self.assertIn("operational toil", messages.linkedin_invite.lower())
        self.assertIn("migration checklist", messages.email_followup.lower())
        self.assertNotIn("prompt context used", messages.email_followup.lower())


class ApiParsingTests(unittest.TestCase):
    def test_extract_results_supports_nested_data_shape(self) -> None:
        payload = {"success": True, "data": {"results": [{"full_name": "A"}, {"full_name": "B"}]}}
        results = _extract_results(payload)
        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
