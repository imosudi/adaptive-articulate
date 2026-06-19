import os
import wave
from typing import Optional, Tuple

import numpy as np
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.attempt import ExerciseAttempt
from app.models.exercise import Exercise
from app.services.speech_assessment.engine import (
    SpeechAssessmentEngineInterface,
    WhisperSpeechAssessmentEngine,
)


class AssessmentService:
    def __init__(
        self,
        upload_folder: Optional[str] = None,
        engine: Optional[SpeechAssessmentEngineInterface] = None,
    ):
        self.upload_folder = upload_folder
        self.engine = engine or WhisperSpeechAssessmentEngine()

    def validate_audio_file(
        self, file_storage: FileStorage, content_length: int
    ) -> Tuple[bool, str]:
        """Validates file size (limit 5MB) and magic bytes (WAV, MP3, WebM)."""
        MAX_SIZE = 5 * 1024 * 1024  # 5MB
        if content_length > MAX_SIZE:
            return False, "File exceeds the 5MB size limit."

        # Read first 16 bytes for magic bytes validation
        file_storage.stream.seek(0)
        header = file_storage.stream.read(16)
        file_storage.stream.seek(0)  # Reset stream position

        # Check file extension
        filename = file_storage.filename or ""
        ext = os.path.splitext(filename.lower())[1]
        if ext not in [".wav", ".mp3", ".webm"]:
            return (
                False,
                "Unsupported file extension. Only WAV, MP3, and WebM are allowed.",
            )

        # Verify magic bytes
        is_valid = False
        # WAV magic bytes: starts with 'RIFF' and has 'WAVE' at offset 8
        if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
            is_valid = True
        # MP3 magic bytes: ID3 header or sync frame
        elif (
            header.startswith(b"ID3")
            or header.startswith(b"\xff\xfb")
            or header.startswith(b"\xff\xf3")
            or header.startswith(b"\xff\xf2")
        ):
            is_valid = True
        # WebM magic bytes: EBML header
        elif header.startswith(b"\x1a\x45\xdf\xa3"):
            is_valid = True

        if not is_valid:
            return (
                False,
                "Invalid audio file format. Content headers do not match allowed formats.",
            )

        return True, ""

    def load_wav_to_numpy(self, file_path: str) -> Tuple[np.ndarray, float]:
        """Loads WAV file into float32 mono numpy array resampled to 16kHz.

        Returns (numpy_array, duration).
        """
        with wave.open(file_path, "rb") as f:
            channels = f.getnchannels()
            sample_width = f.getsampwidth()
            rate = f.getframerate()
            n_frames = f.getnframes()

            raw_data = f.readframes(n_frames)
            duration = n_frames / float(rate)

            if sample_width == 1:
                data = np.frombuffer(raw_data, dtype=np.uint8).astype(np.float32) - 128.0
                data /= 128.0
            elif sample_width == 2:
                data = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
                data /= 32768.0
            elif sample_width == 4:
                data = np.frombuffer(raw_data, dtype=np.int32).astype(np.float32)
                data /= 2147483648.0
            else:
                raise ValueError(f"Unsupported sample width: {sample_width}")

            if channels > 1:
                data = data.reshape(-1, channels).mean(axis=1)

            if rate != 16000:
                new_len = int(duration * 16000)
                data = np.interp(
                    np.linspace(0, len(data), new_len, endpoint=False),
                    np.arange(len(data)),
                    data,
                ).astype(np.float32)

            return data, duration

    def process_assessment(
        self, student_id: int, exercise_id: int, file_storage: FileStorage
    ) -> ExerciseAttempt:
        """Validates, saves the WAV file, loads it, runs Whisper assessment,

        creates and commits ExerciseAttempt record.
        """
        from flask import current_app

        upload_folder = self.upload_folder or os.path.join(
            current_app.root_path, "private_uploads/attempts"
        )
        os.makedirs(upload_folder, exist_ok=True)

        filename = file_storage.filename or "recording.wav"
        temp_filename = f"temp_{student_id}_{exercise_id}_{secure_filename(filename)}"
        temp_path = os.path.join(upload_folder, temp_filename)
        file_storage.save(temp_path)

        try:
            # Load the WAV file using our custom loader
            audio_array, duration = self.load_wav_to_numpy(temp_path)

            # Retrieve the target exercise to assess against
            exercise = db.session.get(Exercise, exercise_id)
            if not exercise:
                raise ValueError("Exercise not found.")

            # Perform the assessment
            assessment = self.engine.assess(audio_array, duration, exercise.prompt_text)

            # Create final attempt record
            attempt = ExerciseAttempt(
                student_id=student_id,
                exercise_id=exercise_id,
                audio_path="",  # will update after renaming
                transcription=assessment["transcribed_text"],
                accuracy_score=assessment["accuracy_score"],
                fluency_score=assessment["fluency_score"],
                completeness_score=assessment["completeness_score"],
                overall_score=assessment["overall_score"],
            )
            db.session.add(attempt)
            db.session.commit()

            # Now rename the temp file to a permanent path using attempt.id
            permanent_filename = f"attempt_{attempt.id}.wav"
            permanent_path = os.path.join(upload_folder, permanent_filename)
            os.rename(temp_path, permanent_path)

            # Update the attempt with the permanent audio path
            relative_path = os.path.join("private_uploads/attempts", permanent_filename)
            attempt.audio_path = relative_path
            db.session.commit()

            return attempt

        except Exception as e:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e
