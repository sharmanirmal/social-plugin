"""Integration tests for content generator — verifies prompts receive config values."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from social_plugin.config import Config
from social_plugin.db import Database
from social_plugin.drafts.draft_manager import DraftManager
from social_plugin.generator.llm_client import GenerationResult


@pytest.fixture
def db():
    """Create a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield Database(db_path)


@pytest.fixture
def dm(db):
    return DraftManager(db)


def _make_config(overrides: dict | None = None) -> Config:
    """Create a Config from defaults + overrides without a YAML file."""
    config = Config.load("/nonexistent/config.yaml")
    if overrides:
        from social_plugin.config import _deep_merge
        config._data = _deep_merge(config._data, overrides)
    return config


def _mock_result(text: str = "Generated tweet about robots. #Robotics") -> GenerationResult:
    return GenerationResult(
        text=text,
        model="test-model",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        estimated_cost=0.001,
    )


@patch("social_plugin.generator.content_generator.create_llm_client")
def test_generate_tweet_passes_topic_from_config(mock_create, db, dm):
    """generate_tweet passes config topic to prompt builders."""
    mock_llm = MagicMock()
    mock_llm.generate.return_value = _mock_result()
    mock_create.return_value = mock_llm

    config = _make_config({"topics": {"primary": "Quantum Computing"}})

    from social_plugin.generator.content_generator import ContentGenerator
    gen = ContentGenerator(config, db, dm)
    gen.generate_tweet(dry_run=True)

    # Check that the system prompt contains the custom topic
    system_prompt = mock_llm.generate.call_args_list[0][0][0]
    user_prompt = mock_llm.generate.call_args_list[0][0][1]
    assert "Quantum Computing" in system_prompt
    assert "Quantum Computing" in user_prompt


@patch("social_plugin.generator.content_generator.create_llm_client")
def test_generate_tweet_passes_hashtags_from_config(mock_create, db, dm):
    """generate_tweet passes config hashtags to prompt builders."""
    mock_llm = MagicMock()
    mock_llm.generate.return_value = _mock_result()
    mock_create.return_value = mock_llm

    config = _make_config({
        "topics": {"hashtags": {"twitter": ["#QuantumAI", "#Qubits"]}}
    })

    from social_plugin.generator.content_generator import ContentGenerator
    gen = ContentGenerator(config, db, dm)
    gen.generate_tweet(dry_run=True)

    system_prompt = mock_llm.generate.call_args_list[0][0][0]
    assert "#QuantumAI" in system_prompt
    assert "#Qubits" in system_prompt


@patch("social_plugin.generator.content_generator.create_llm_client")
def test_generate_tweet_passes_rules_from_config(mock_create, db, dm):
    """generate_tweet passes config rules to system prompt."""
    mock_llm = MagicMock()
    mock_llm.generate.return_value = _mock_result()
    mock_create.return_value = mock_llm

    config = _make_config({
        "rules": {
            "do": ["Always cite sources"],
            "dont": ["Never use jargon"],
        }
    })

    from social_plugin.generator.content_generator import ContentGenerator
    gen = ContentGenerator(config, db, dm)
    gen.generate_tweet(dry_run=True)

    system_prompt = mock_llm.generate.call_args_list[0][0][0]
    assert "Always cite sources" in system_prompt
    assert "Never use jargon" in system_prompt


@patch("social_plugin.generator.content_generator.create_llm_client")
def test_generate_tweet_passes_style_examples(mock_create, db, dm):
    """generate_tweet passes style examples to user prompt."""
    mock_llm = MagicMock()
    mock_llm.generate.return_value = _mock_result()
    mock_create.return_value = mock_llm

    config = _make_config({
        "style_examples": [
            "Boston Dynamics does backflips. #Robotics",
            "Toyota Research achieves 94% success.",
        ]
    })

    from social_plugin.generator.content_generator import ContentGenerator
    gen = ContentGenerator(config, db, dm)
    gen.generate_tweet(dry_run=True)

    user_prompt = mock_llm.generate.call_args_list[0][0][1]
    assert "Boston Dynamics" in user_prompt
    assert "Toyota Research" in user_prompt
    assert "Match this voice" in user_prompt


@patch("social_plugin.generator.content_generator.create_llm_client")
def test_generate_tweet_passes_rejection_feedback(mock_create, db, dm):
    """generate_tweet includes rejection feedback in user prompt."""
    mock_llm = MagicMock()
    mock_llm.generate.return_value = _mock_result()
    mock_create.return_value = mock_llm

    # Insert a rejected draft with notes
    db.insert_draft({
        "id": "rej_test",
        "platform": "twitter",
        "content": "Bad tweet",
        "status": "pending",
    })
    db.update_draft_status(
        "rej_test", "rejected",
        reviewed_at=datetime.utcnow().isoformat(),
        reviewer_notes="too generic and boring",
    )

    config = _make_config()

    from social_plugin.generator.content_generator import ContentGenerator
    gen = ContentGenerator(config, db, dm)
    gen.generate_tweet(dry_run=True)

    user_prompt = mock_llm.generate.call_args_list[0][0][1]
    assert "too generic and boring" in user_prompt
    assert "things to AVOID" in user_prompt


@patch("social_plugin.generator.content_generator.create_llm_client")
def test_generate_tweet_passes_approval_feedback(mock_create, db, dm):
    """generate_tweet includes approval feedback in user prompt."""
    mock_llm = MagicMock()
    mock_llm.generate.return_value = _mock_result()
    mock_create.return_value = mock_llm

    # Insert an approved draft with notes
    db.insert_draft({
        "id": "app_test",
        "platform": "twitter",
        "content": "Great tweet",
        "status": "pending",
    })
    db.update_draft_status(
        "app_test", "approved",
        reviewed_at=datetime.utcnow().isoformat(),
        reviewer_notes="loved the specific data",
    )

    config = _make_config()

    from social_plugin.generator.content_generator import ContentGenerator
    gen = ContentGenerator(config, db, dm)
    gen.generate_tweet(dry_run=True)

    user_prompt = mock_llm.generate.call_args_list[0][0][1]
    assert "loved the specific data" in user_prompt
    assert "things that worked WELL" in user_prompt


@patch("social_plugin.generator.content_generator.create_llm_client")
def test_generate_linkedin_passes_topic_from_config(mock_create, db, dm):
    """generate_linkedin_post passes config topic to prompt builders."""
    mock_llm = MagicMock()
    mock_llm.generate.return_value = _mock_result("Generated LinkedIn post about quantum.")
    mock_create.return_value = mock_llm

    config = _make_config({"topics": {"primary": "Quantum Computing"}})

    from social_plugin.generator.content_generator import ContentGenerator
    gen = ContentGenerator(config, db, dm)
    gen.generate_linkedin_post(dry_run=True)

    system_prompt = mock_llm.generate.call_args_list[0][0][0]
    user_prompt = mock_llm.generate.call_args_list[0][0][1]
    assert "Quantum Computing" in system_prompt
    assert "Quantum Computing" in user_prompt


@patch("social_plugin.generator.content_generator.create_llm_client")
def test_generate_linkedin_passes_rules_from_config(mock_create, db, dm):
    """generate_linkedin_post passes config rules to system prompt."""
    mock_llm = MagicMock()
    mock_llm.generate.return_value = _mock_result("Generated LinkedIn post.")
    mock_create.return_value = mock_llm

    config = _make_config({
        "rules": {
            "do": ["Include statistics"],
            "dont": ["Avoid buzzwords"],
        }
    })

    from social_plugin.generator.content_generator import ContentGenerator
    gen = ContentGenerator(config, db, dm)
    gen.generate_linkedin_post(dry_run=True)

    system_prompt = mock_llm.generate.call_args_list[0][0][0]
    assert "Include statistics" in system_prompt
    assert "Avoid buzzwords" in system_prompt


@patch("social_plugin.generator.content_generator.create_llm_client")
def test_regenerate_passes_topic_and_rules(mock_create, db, dm):
    """regenerate passes topic and rules to system prompt."""
    mock_llm = MagicMock()
    mock_llm.generate.return_value = _mock_result("Regenerated tweet.")
    mock_create.return_value = mock_llm

    # Create a draft to regenerate
    db.insert_draft({
        "id": "regen_test",
        "platform": "twitter",
        "content": "Original tweet",
        "status": "pending",
        "hashtags": '["#AI"]',
    })

    config = _make_config({
        "topics": {"primary": "Quantum Computing"},
        "rules": {"do": ["Be precise"], "dont": ["No fluff"]},
    })

    from social_plugin.generator.content_generator import ContentGenerator
    gen = ContentGenerator(config, db, dm)
    gen.regenerate("regen_test", "casual")

    system_prompt = mock_llm.generate.call_args_list[0][0][0]
    assert "Quantum Computing" in system_prompt
    assert "Be precise" in system_prompt
    assert "No fluff" in system_prompt


@patch("social_plugin.generator.content_generator.create_llm_client")
def test_no_hardcoded_values_in_prompts(mock_create, db, dm):
    """With custom topic, 'Physical AI' should not appear in prompts."""
    mock_llm = MagicMock()
    mock_llm.generate.return_value = _mock_result("Generated tweet about quantum.")
    mock_create.return_value = mock_llm

    config = _make_config({
        "topics": {
            "primary": "Quantum Computing",
            "hashtags": {"twitter": ["#Quantum"]},
        }
    })

    from social_plugin.generator.content_generator import ContentGenerator
    gen = ContentGenerator(config, db, dm)
    gen.generate_tweet(dry_run=True)

    system_prompt = mock_llm.generate.call_args_list[0][0][0]
    user_prompt = mock_llm.generate.call_args_list[0][0][1]
    assert "Physical AI" not in system_prompt
    assert "Physical AI" not in user_prompt
