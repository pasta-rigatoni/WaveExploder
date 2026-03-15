import numpy as np
import pytest
import soundfile as sf


@pytest.fixture
def make_wav(tmp_path):
    """Factory fixture that writes a WAV file under tmp_path.

    Args:
        rel_path: path relative to tmp_path (parent dirs are created automatically)
        num_channels: number of audio channels
        num_samples: number of samples per channel (default 1000)
        sample_rate: sample rate in Hz (default 48000)
        channel_amplitudes: dict mapping 0-based channel index to amplitude (default 0.0)
    """
    def _factory(rel_path, num_channels, num_samples=1000, sample_rate=48000, channel_amplitudes=None):
        if num_channels == 1:
            data = np.zeros(num_samples)
            if channel_amplitudes and 0 in channel_amplitudes:
                data[:] = channel_amplitudes[0]
        else:
            data = np.zeros((num_samples, num_channels))
            if channel_amplitudes:
                for ch_idx, amp in channel_amplitudes.items():
                    data[:, ch_idx] = amp

        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), data, sample_rate)
        return path

    return _factory
