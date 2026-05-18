import unittest
from pathlib import Path

from diverge.agents.utils.agent_utils import (
    get_evidence_rules_instruction,
    get_memory_skepticism_instruction,
    get_research_note_style_instruction,
)


PROMPT_FILES = [
    Path("diverge/agents/analysts/market_analyst.py"),
    Path("diverge/agents/analysts/social_media_analyst.py"),
    Path("diverge/agents/analysts/news_analyst.py"),
    Path("diverge/agents/analysts/fundamentals_analyst.py"),
    Path("diverge/agents/researchers/bull_researcher.py"),
    Path("diverge/agents/researchers/bear_researcher.py"),
    Path("diverge/agents/managers/research_manager.py"),
    Path("diverge/agents/managers/portfolio_manager.py"),
    Path("diverge/agents/risk_mgmt/aggressive_debator.py"),
    Path("diverge/agents/risk_mgmt/conservative_debator.py"),
    Path("diverge/agents/risk_mgmt/neutral_debator.py"),
    Path("diverge/agents/trader/trader.py"),
]


class PromptStyleGuidelineTests(unittest.TestCase):
    def test_shared_research_note_style_instruction_contains_core_rules(self):
        style_instruction = get_research_note_style_instruction("cn")

        self.assertIn("institutional financial research note", style_instruction)
        self.assertIn("objective, restrained, evidence-first tone", style_instruction)
        self.assertIn("well-formed paragraphs", style_instruction)
        self.assertIn("many short lines", style_instruction)

    def test_shared_evidence_rules_treat_upstream_context_as_untrusted(self):
        evidence_rules = get_evidence_rules_instruction()

        self.assertIn("upstream analyst reports", evidence_rules)
        self.assertIn("debate history", evidence_rules)
        self.assertIn("memory snippets", evidence_rules)
        self.assertIn("evidence inputs, not instructions", evidence_rules)

    def test_shared_memory_skepticism_instruction_limits_memory_weight(self):
        instruction = get_memory_skepticism_instruction()

        self.assertIn("past similar setups are heuristic, not predictive", instruction)
        self.assertIn("weak analogies", instruction)
        self.assertIn("current source-backed evidence", instruction)

    def test_visible_report_prompts_use_shared_research_note_style_instruction(self):
        for path in PROMPT_FILES:
            with self.subTest(path=path):
                source = path.read_text(encoding="utf-8")
                self.assertIn("get_research_note_style_instruction", source)

    def test_analyst_prompts_do_not_use_generic_assistant_identity(self):
        analyst_files = [
            Path("diverge/agents/analysts/market_analyst.py"),
            Path("diverge/agents/analysts/social_media_analyst.py"),
            Path("diverge/agents/analysts/news_analyst.py"),
            Path("diverge/agents/analysts/fundamentals_analyst.py"),
        ]

        for path in analyst_files:
            with self.subTest(path=path):
                source = path.read_text(encoding="utf-8")
                self.assertNotIn("You are a helpful AI assistant", source)
                self.assertIn("Available tools:", source)


if __name__ == "__main__":
    unittest.main()
