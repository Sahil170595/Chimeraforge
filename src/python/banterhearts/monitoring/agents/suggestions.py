"""Generate actionable suggestions from monitoring summaries."""

from __future__ import annotations

from typing import Dict, List

from .model_recommender import ModelRecommender


class SuggestionsAgent:
    def __init__(self, recommender: ModelRecommender | None = None) -> None:
        self.recommender = recommender or ModelRecommender()

    def suggest(self, summary: Dict[str, Dict[str, float]]) -> List[str]:
        suggestions = []

        if "_slos" in summary:
            for res in summary["_slos"].get("results", []):
                if not res["ok"]:
                    suggestions.append(f"Investigate SLO breach: {res['message']}")

        suggestions.extend(self.recommender.recommend(summary))
        return suggestions
