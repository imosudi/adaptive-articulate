# AdaptiveArticulate Blockers and Mitigations

## 1. faster-whisper Installation Failure

### Issue:
Installing `faster-whisper` fails during compilation of PyAV (`av`) because the build environment lacks `pkg-config` and `ffmpeg` development libraries (e.g., `libavformat-dev`, `libavcodec-dev`), and no prebuilt wheels of PyAV are available for Python 3.14 on PyPI.

### Mitigation / Fallback:
As permitted by the spec (§1 Tech Stack / Speech assessment), we fall back to using the `openai-whisper` `base` model. It executes behind the exact same `SpeechAssessmentEngine` interface. It does not require compiling PyAV and uses command-line `ffmpeg` or direct PyTorch processing.
