"""Contextual bandit model using SGDClassifier for online learning.

Each user gets their own model that learns which tools work best
in which contexts based on feedback signals.
"""

import os
import numpy as np

from .features import TOOLS, FEATURE_DIM

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "rl_models")


class ToolSelector:
    """Online-learning tool selector using SGDClassifier."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self._model = None
        self._fitted = False

    @property
    def model_path(self) -> str:
        return os.path.join(MODEL_DIR, f"{self.user_id}.joblib")

    def _ensure_model(self):
        """Lazily initialize the SGDClassifier."""
        if self._model is not None:
            return
        try:
            from sklearn.linear_model import SGDClassifier
            self._model = SGDClassifier(
                loss="log_loss",
                penalty="l2",
                alpha=0.001,
                random_state=42,
                warm_start=True,
            )
        except ImportError:
            self._model = None

    def predict(self, features: list[float]) -> dict[str, float]:
        """Return tool -> probability mapping for the given context.

        If the model hasn't been trained yet, returns uniform probabilities.
        """
        if not self._fitted or self._model is None:
            uniform = 1.0 / len(TOOLS)
            return {tool: uniform for tool in TOOLS}

        X = np.array([features])
        try:
            probs = self._model.predict_proba(X)[0]
            classes = list(self._model.classes_)
            result = {}
            for i, cls in enumerate(classes):
                tool = TOOLS[int(cls)] if isinstance(cls, (int, np.integer)) and int(cls) < len(TOOLS) else str(cls)
                result[tool] = float(probs[i])
            # Fill missing tools with 0
            for tool in TOOLS:
                if tool not in result:
                    result[tool] = 0.0
            return result
        except Exception:
            uniform = 1.0 / len(TOOLS)
            return {tool: uniform for tool in TOOLS}

    def update(self, features: list[float], tool: str, reward: float) -> None:
        """Update the model with a single training sample.

        Args:
            features: Context feature vector
            tool: Tool that was used
            reward: Reward signal (-1.0 to 1.0)
        """
        self._ensure_model()
        if self._model is None:
            return

        # Convert tool to index
        if tool in TOOLS:
            tool_idx = TOOLS.index(tool)
        else:
            return  # Unknown tool, skip

        # Weight the sample by absolute reward
        X = np.array([features])
        y = np.array([tool_idx])
        weight = np.array([max(abs(reward), 0.1)])

        try:
            self._model.partial_fit(X, y, classes=list(range(len(TOOLS))), sample_weight=weight)
            self._fitted = True
        except Exception:
            pass

    def save(self) -> None:
        """Persist the model to disk."""
        if self._model is None or not self._fitted:
            return
        try:
            import joblib
            os.makedirs(MODEL_DIR, exist_ok=True)
            joblib.dump({"model": self._model, "fitted": self._fitted}, self.model_path)
        except Exception:
            pass

    def load(self) -> bool:
        """Load a previously saved model. Returns True if loaded."""
        try:
            import joblib
            if not os.path.exists(self.model_path):
                return False
            data = joblib.load(self.model_path)
            self._model = data["model"]
            self._fitted = data.get("fitted", True)
            return True
        except Exception:
            return False
