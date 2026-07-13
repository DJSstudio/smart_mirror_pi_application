from app.platform import raspberry_pi_camera_adapter as camera


def test_csi_fps_is_limited_to_realtime_imx415_mode():
    assert camera._csi_fps(60) == 30
    assert camera._csi_fps(30) == 30
    assert camera._csi_fps(15) == 15


def test_pi5_fallback_requests_low_latency(monkeypatch):
    monkeypatch.setattr(camera, "_is_pi5", lambda: True)

    command = camera._rpicam_cmd(3840, 2160, 30, 25_000_000)

    assert "--low-latency" in command
    assert command[command.index("--libav-format") + 1] == "mpegts"
    assert command[command.index("--width") + 1] == "3840"
    assert command[command.index("--height") + 1] == "2160"
    assert command[command.index("--framerate") + 1] == "30"


def test_non_pi5_does_not_receive_pi5_only_encoder_flags(monkeypatch):
    monkeypatch.setattr(camera, "_is_pi5", lambda: False)

    command = camera._rpicam_cmd(3840, 2160, 30, 25_000_000)

    assert "--low-latency" not in command
    assert "--libav-format" not in command
