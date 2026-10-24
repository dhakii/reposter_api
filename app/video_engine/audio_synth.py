# app/video_engine/audio_synth.py
"""
Генератор и нормализатор фонового аудио для видеороликов.
Создает мягкое эмбиент-сопровождение (Cmaj9 - Am9 - Fmaj7 - G7sus4) в формате WAV.
"""

import math
import struct
import wave
from pathlib import Path


def generate_ambient_track(output_wav_path: str, duration_sec: float = 30.0, sample_rate: int = 44100) -> str:
    """
    Генерирует мягкую медитативную гармонию без роялти для фона картин.
    """
    n_samples = int(sample_rate * duration_sec)
    path = Path(output_wav_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Гармоническая последовательность аккордов (частоты в Гц)
    # Cmaj9, Am9, Fmaj7, G7sus4
    chord_progression = [
        [130.81, 196.00, 246.94, 293.66, 329.63],  # C3, G3, B3, D4, E4
        [110.00, 164.81, 220.00, 261.63, 293.66],  # A2, E3, A3, C4, D4
        [87.31, 130.81, 174.61, 220.00, 261.63],   # F2, C3, F3, A3, C4
        [98.00, 146.83, 196.00, 261.63, 293.66],   # G2, D3, G3, C4, D4
    ]

    chord_duration = duration_sec / len(chord_progression)

    data = []
    for i in range(n_samples):
        t = i / sample_rate
        chord_idx = min(int(t / chord_duration), len(chord_progression) - 1)
        freqs = chord_progression[chord_idx]

        # Синтез мягких тонов с обертонами
        sample_val = 0.0
        for f in freqs:
            # Основной тон + мягкий суб-обертон
            sample_val += math.sin(2 * math.pi * f * t) * 0.16
            sample_val += math.sin(4 * math.pi * f * t) * 0.04

        # Плавное нарастание (fade-in) 2 сек и затухание (fade-out) 2.5 сек
        envelope = min(1.0, t / 2.0) * min(1.0, (duration_sec - t) / 2.5)

        int_val = int(sample_val * envelope * 32767)
        int_val = max(-32767, min(32767, int_val))
        # Стерео каналы
        data.extend([int_val, int_val])

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(struct.pack("<" + ("h" * len(data)), *data))

    return str(path)
