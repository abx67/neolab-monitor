"""Tests for the feedback system."""

import json
import os
import tempfile
import pytest
from src.feedback import FeedbackStore


@pytest.fixture
def feedback_file(tmp_path):
    """Create a temp feedback file for testing."""
    return str(tmp_path / "feedback.json")


@pytest.fixture
def store(feedback_file):
    """Create a FeedbackStore pointing to temp file."""
    return FeedbackStore(feedback_file)


def test_empty_initial_state(store):
    """Fresh store has no signals."""
    assert store.get_signals() == []
    assert store.get_stats()["total_signals"] == 0


def test_mark_relevant(store, feedback_file):
    """Marking relevant adds a signal and suggests keywords."""
    keywords = store.mark_relevant("Research Engineer, RL", "Anthropic", 
                                   "Work on reinforcement learning...")
    signals = store.get_signals()
    assert len(signals) == 1
    assert signals[0]["signal"] == "relevant"
    assert signals[0]["title"] == "Research Engineer, RL"
    assert signals[0]["company"] == "Anthropic"
    assert len(keywords) > 0


def test_mark_irrelevant(store, feedback_file):
    """Marking irrelevant adds a signal and builds auto-blacklist."""
    blacklisted = store.mark_irrelevant("Recruiter, AI Research", "OpenAI")
    signals = store.get_signals()
    assert len(signals) == 1
    assert signals[0]["signal"] == "irrelevant"
    assert len(blacklisted) > 0
    
    # Check auto-blacklist
    auto_bl = store.get_auto_blacklist()
    assert len(auto_bl) > 0


def test_stats(store, feedback_file):
    """Stats reflect recorded signals."""
    store.mark_relevant("Research Engineer, RL")
    store.mark_irrelevant("Recruiter, AI Research")
    stats = store.get_stats()
    assert stats["total_signals"] == 2
    assert stats["relevant"] == 1
    assert stats["irrelevant"] == 1


def test_reset(store, feedback_file):
    """Reset clears all data."""
    store.mark_relevant("Research Engineer")
    store.reset()
    assert store.get_signals() == []
    assert store.get_stats()["total_signals"] == 0


def test_auto_interests_persistence(store, feedback_file):
    """Auto-interests are persisted and retrievable."""
    store.mark_relevant("Research Engineer, RL and LLMs")
    interests = store.get_auto_interests()
    assert len(interests) > 0
    # Should contain extracted keywords
    combined = " ".join(interests).lower()
    assert "rl" in combined or "llm" in combined or "research" in combined


def test_extract_keywords(store):
    """Keyword extraction produces meaningful phrases."""
    keywords = FeedbackStore._extract_keywords(
        "Research Engineer, Machine Learning (Reinforcement Learning)",
        "Work on RL algorithms for large language models."
    )
    assert len(keywords) > 0
    # Should have multi-word phrases
    multi_word = [k for k in keywords if " " in k]
    assert len(multi_word) > 0
