"""User feedback storage and keyword extraction for adaptive filtering."""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple


FEEDBACK_FILE = "feedback.json"

# Number of top keywords to extract from irrelevant job titles/descriptions
AUTO_BLACKLIST_KEYWORDS = 3
# Bonus points for a job matching a previously-marked-relevant title
RELEVANT_BONUS = 2.0
# Penalty points for a job matching a previously-marked-irrelevant title
IRRELEVANT_PENALTY = 1.5


class FeedbackStore:
    """Stores and applies user feedback signals for adaptive job filtering."""

    def __init__(self, filepath: str = FEEDBACK_FILE):
        self.filepath = filepath

    def _load(self) -> dict:
        """Load feedback data from disk."""
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {"signals": [], "auto_blacklist": [], "auto_interests": []}

    def _save(self, data: dict) -> None:
        """Persist feedback data to disk."""
        os.makedirs(os.path.dirname(self.filepath) or ".", exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def mark_relevant(self, title: str, company: str = "", description: str = "") -> List[str]:
        """Record a job as relevant. Suggests keywords to add to interests.
        
        Returns list of suggested keywords from title.
        """
        data = self._load()
        keywords = self._extract_keywords(title, description)
        
        signal = {
            "title": title,
            "company": company,
            "signal": "relevant",
            "timestamp": datetime.now().isoformat(),
            "keywords": keywords,
        }
        data["signals"].append(signal)
        
        # Add top keywords to auto-interests (will be merged with interests.json at runtime)
        for kw in keywords[:AUTO_BLACKLIST_KEYWORDS]:
            if kw not in data["auto_interests"]:
                data["auto_interests"].append(kw)
        
        self._save(data)
        return keywords

    def mark_irrelevant(self, title: str, company: str = "", description: str = "") -> List[str]:
        """Record a job as irrelevant. Auto-adds keywords to blacklist.
        
        Returns list of auto-blacklisted keywords.
        """
        data = self._load()
        keywords = self._extract_keywords(title, description)
        
        signal = {
            "title": title,
            "company": company,
            "signal": "irrelevant",
            "timestamp": datetime.now().isoformat(),
            "keywords": keywords,
        }
        data["signals"].append(signal)
        
        # Add top keywords to auto-blacklist
        auto_blacklisted = []
        for kw in keywords[:AUTO_BLACKLIST_KEYWORDS]:
            if kw not in data["auto_blacklist"]:
                data["auto_blacklist"].append(kw)
                auto_blacklisted.append(kw)
        
        self._save(data)
        return auto_blacklisted

    def get_signals(self) -> List[dict]:
        """Return all feedback signals, newest first."""
        data = self._load()
        return list(reversed(data.get("signals", [])))

    def get_stats(self) -> dict:
        """Return feedback statistics."""
        data = self._load()
        signals = data.get("signals", [])
        relevant = sum(1 for s in signals if s["signal"] == "relevant")
        irrelevant = sum(1 for s in signals if s["signal"] == "irrelevant")
        return {
            "total_signals": len(signals),
            "relevant": relevant,
            "irrelevant": irrelevant,
            "auto_blacklist_count": len(data.get("auto_blacklist", [])),
            "auto_interests_count": len(data.get("auto_interests", [])),
        }

    def get_auto_blacklist(self) -> List[str]:
        """Return auto-discovered blacklist keywords."""
        data = self._load()
        return data.get("auto_blacklist", [])

    def get_auto_interests(self) -> List[str]:
        """Return auto-discovered interest keywords."""
        data = self._load()
        return data.get("auto_interests", [])

    def reset(self) -> None:
        """Clear all feedback data."""
        self._save({"signals": [], "auto_blacklist": [], "auto_interests": []})

    @staticmethod
    def _extract_keywords(title: str, description: str = "") -> List[str]:
        """Extract meaningful keywords from a job title and optional description.
        
        Returns list of lowercase keyword phrases (2+ words preferred).
        """
        keywords = []
        
        # Extract from title: find multi-word phrases (skip common words)
        skip_words = {"the", "a", "an", "and", "or", "for", "of", "in", "at", "to", 
                      "with", "from", "on", "off", "by", "as", "is", "are", "was", 
                      "been", "be", "will", "can", "may", " Research ", " Engineer",
                      " Scientist", " Manager", " Staff", " Position", " Role"}
        
        title_words = title.lower().split()
        # Keep phrases of 2+ words that aren't common stop words
        for i, word in enumerate(title_words):
            word = word.strip("-,();:")
            if word in skip_words:
                continue
            # Build phrase from this word
            phrase = word
            for j in range(i + 1, min(i + 4, len(title_words))):
                next_word = title_words[j].strip("-,();:")
                if next_word in skip_words or len(next_word) <= 2:
                    break
                phrase += " " + next_word
                if len(phrase.split()) >= 2:
                    keywords.append(phrase)
        
        # Also extract from description if provided
        if description:
            desc_words = re.findall(r'\b([a-z]{4,})\b', description.lower())
            from collections import Counter
            desc_freq = Counter(desc_words)
            # Top non-common words from description
            common = {"about", "working", "team", "role", "will", "your", "this", 
                      "position", "required", "experience", "development", "including"}
            for word, count in desc_freq.most_common(10):
                if word not in common and word not in keywords:
                    keywords.append(word)
        
        return list(dict.fromkeys(keywords))  # deduplicate, preserve order


def load_feedback_blacklist(filepath: str = FEEDBACK_FILE) -> List[str]:
    """Convenience function to load auto-blacklist from feedback store."""
    store = FeedbackStore(filepath)
    return store.get_auto_blacklist()


def load_feedback_interests(filepath: str = FEEDBACK_FILE) -> List[str]:
    """Convenience function to load auto-interests from feedback store."""
    store = FeedbackStore(filepath)
    return store.get_auto_interests()
