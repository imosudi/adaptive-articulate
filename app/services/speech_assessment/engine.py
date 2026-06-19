import abc
import difflib
import re
from typing import Any, Dict, List

import numpy as np
import whisper


class SpeechAssessmentEngineInterface(abc.ABC):
    @abc.abstractmethod
    def transcribe(self, audio_data: np.ndarray) -> str:
        """Transcribe audio data directly from a numpy array."""
        pass

    @abc.abstractmethod
    def assess(self, audio_data: np.ndarray, duration: float, prompt_text: str) -> Dict[str, Any]:
        """Assess speech pronunciation and return scores."""
        pass


class WhisperSpeechAssessmentEngine(SpeechAssessmentEngineInterface):
    def __init__(self, model_name: str = "base"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self) -> Any:
        if self._model is None:
            self._model = whisper.load_model(self.model_name)
        return self._model

    def transcribe(self, audio_data: np.ndarray) -> str:
        """Transcribe audio data using Whisper model on CPU."""
        result = self.model.transcribe(audio_data)
        text = result.get("text", "")
        return str(text).strip()

    def normalize_text(self, text: str) -> List[str]:
        """Convert text to lowercase and remove punctuation."""
        cleaned = re.sub(r"[^\w\s]", "", text.lower())
        return cleaned.split()

    def assess(self, audio_data: np.ndarray, duration: float, prompt_text: str) -> Dict[str, Any]:
        """Assess speech pronunciation against target prompt text.

        Returns:
            Dict containing:
                - transcribed_text (str)
                - accuracy_score (float, 0-100)
                - completeness_score (float, 0-100)
                - fluency_score (float, 0-100)
                - overall_score (float, 0-100)
        """
        # 1. Transcribe the audio
        transcribed_text = self.transcribe(audio_data)

        # 2. Normalize strings
        target_words = self.normalize_text(prompt_text)
        transcribed_words = self.normalize_text(transcribed_text)

        # 3. Handle edge cases
        if not target_words and not transcribed_words:
            return {
                "transcribed_text": transcribed_text,
                "accuracy_score": 100.0,
                "completeness_score": 100.0,
                "fluency_score": 100.0,
                "overall_score": 100.0,
            }

        if not target_words:
            # Student spoke but prompt was empty
            return {
                "transcribed_text": transcribed_text,
                "accuracy_score": 0.0,
                "completeness_score": 100.0,
                "fluency_score": 50.0,
                "overall_score": 30.0,
            }

        if not transcribed_words:
            # Student didn't speak anything detectable
            return {
                "transcribed_text": transcribed_text,
                "accuracy_score": 0.0,
                "completeness_score": 0.0,
                "fluency_score": 0.0,
                "overall_score": 0.0,
            }

        # 4. Sequence Alignment
        matcher = difflib.SequenceMatcher(None, target_words, transcribed_words)
        matching_blocks = matcher.get_matching_blocks()
        matches = sum(block.size for block in matching_blocks)

        # 5. Completeness: percentage of target words matched
        completeness = matches / len(target_words)

        # 6. Accuracy: SequenceMatcher ratio (standard F1-like similarity)
        accuracy = matcher.ratio()

        # 7. Fluency: based on speaking rate (WPS: Words Per Second)
        # Optimal speaking rate is around 1.2 to 2.8 words/second (approx 72 to 168 WPM)
        if duration > 0:
            rate = len(transcribed_words) / duration
            if 1.2 <= rate <= 2.8:
                fluency = 1.0
            elif rate < 1.2:
                fluency = max(0.2, rate / 1.2)
            else:  # rate > 2.8
                fluency = max(0.2, 1.0 - (rate - 2.8) / 2.8)
        else:
            fluency = 0.0

        # Scale metrics to [0.0, 100.0]
        accuracy_pct = round(accuracy * 100.0, 1)
        completeness_pct = round(completeness * 100.0, 1)
        fluency_pct = round(fluency * 100.0, 1)

        # 8. Overall: weighted sum
        overall = (0.5 * accuracy_pct) + (0.3 * completeness_pct) + (0.2 * fluency_pct)
        overall_pct = round(overall, 1)

        return {
            "transcribed_text": transcribed_text,
            "accuracy_score": accuracy_pct,
            "completeness_score": completeness_pct,
            "fluency_score": fluency_pct,
            "overall_score": overall_pct,
        }
