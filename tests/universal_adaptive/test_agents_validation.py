"""Validation tests ensuring all deployed agents, rules, and skills adhere to schema and frontmatter rules."""
import re
import unittest
from pathlib import Path


def parse_frontmatter(content: str) -> dict[str, str]:
    """Extract YAML frontmatter between leading --- delimiters."""
    match = re.match(r"^---\r?\n(.*?)\r?\n---", content, re.DOTALL)
    if not match:
        return {}
    fm_lines = match.group(1).splitlines()
    data = {}
    for line in fm_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip().strip("\"'")
    return data


class AgentsValidationTestCase(unittest.TestCase):
    def setUp(self):
        self.workspace_root = Path("/home/nova/projects/cantina")
        self.agents_dir = self.workspace_root / ".agents" / "agents"
        self.rules_dir = self.workspace_root / ".agents" / "rules"
        self.skills_dir = self.workspace_root / ".agents" / "skills"

    def test_all_12_agents_deployed_and_valid(self):
        expected_agents = [
            "orchestrator.md",
            "architecture_analyst.md",
            "repository_investigator.md",
            "implementation_engineer.md",
            "verification_engineer.md",
            "independent_challenger.md",
            "security_reviewer.md",
            "release_engineer.md",
            "knowledge_curator.md",
            "evaluator.md",
            "domain_compiler_engineer.md",
            "domain_security_researcher.md",
        ]
        self.assertTrue(self.agents_dir.exists(), f"Agents dir {self.agents_dir} must exist")

        for agent_file in expected_agents:
            path = self.agents_dir / agent_file
            self.assertTrue(path.exists(), f"Agent file {agent_file} is missing from {self.agents_dir}")
            content = path.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)
            self.assertTrue(bool(fm), f"Agent {agent_file} missing valid YAML frontmatter")
            for req_field in ["id", "name", "role", "category", "version", "authority_level"]:
                self.assertIn(req_field, fm, f"Agent {agent_file} frontmatter missing required field: {req_field}")
            self.assertIn("# ", content, f"Agent {agent_file} must have markdown title")

    def test_rules_deployed_and_valid(self):
        expected_rules = [
            "rule_glassbox_conversation_sandbox.md",
            "rule_universal_adaptive_engineering.md",
            "rule_evidence_provenance_integrity.md",
        ]
        self.assertTrue(self.rules_dir.exists(), f"Rules dir {self.rules_dir} must exist")

        for rule_file in expected_rules:
            path = self.rules_dir / rule_file
            self.assertTrue(path.exists(), f"Rule file {rule_file} is missing from {self.rules_dir}")
            content = path.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)
            self.assertTrue(bool(fm), f"Rule {rule_file} missing valid YAML frontmatter")
            for req_field in ["id", "name", "category", "severity"]:
                self.assertIn(req_field, fm, f"Rule {rule_file} frontmatter missing required field: {req_field}")

    def test_skills_deployed_and_valid(self):
        expected_skills = [
            "universal-adaptive-orchestrator",
            "canonical-schemas",
            "architecture-adapter",
            "verification-agent",
            "universal-inherited-workflow",
        ]
        for skill_name in expected_skills:
            skill_path = self.skills_dir / skill_name / "SKILL.md"
            self.assertTrue(skill_path.exists(), f"Skill file {skill_path} missing")
            content = skill_path.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)
            self.assertTrue(bool(fm), f"Skill {skill_name} missing frontmatter")
            self.assertIn("name", fm, f"Skill {skill_name} frontmatter missing 'name'")
            self.assertEqual(fm["name"], skill_name)


if __name__ == "__main__":
    unittest.main()
