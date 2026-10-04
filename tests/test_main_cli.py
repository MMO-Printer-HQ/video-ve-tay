"""Tests for main CLI entrypoint."""

import os
import subprocess
import sys
from pathlib import Path
import pytest


def test_cli_help():
    """Verify CLI --help flag displays all available arguments and exits cleanly."""
    cmd = [sys.executable, "main.py", "--help"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    stdout = result.stdout
    assert "--svg" in stdout
    assert "--hand" in stdout
    assert "--output" in stdout
    assert "--duration" in stdout
    assert "--hold" in stdout
    assert "--fps" in stdout
    assert "--width" in stdout
    assert "--height" in stdout
    assert "--scale-hand" in stdout
    assert "--tip-x" in stdout
    assert "--tip-y" in stdout


def test_cli_custom_run(tmp_path):
    """Run main.py with customized parameters and verify output video."""
    out_video = tmp_path / "custom_output.mp4"
    cmd = [
        sys.executable,
        "main.py",
        "--svg", "assets/demo_sketch.svg",
        "--hand", "assets/default_hand.png",
        "--output", str(out_video),
        "--duration", "1.0",
        "--hold", "0.5",
        "--fps", "15",
        "--width", "480",
        "--height", "270",
        "--scale-hand", "0.3",
        "--tip-x", "24",
        "--tip-y", "12",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
    assert out_video.exists()
    assert out_video.stat().st_size > 1000
    assert "Progress:" in result.stdout or "Done" in result.stdout or "Video generated" in result.stdout


def test_cli_default_run():
    """Run main.py with small test parameters to verify zero-config behavior quickly."""
    test_out = "test_cli_output.mp4"
    if os.path.exists(test_out):
        os.remove(test_out)

    cmd = [
        sys.executable,
        "main.py",
        "--duration", "1.0",
        "--hold", "0.5",
        "--fps", "15",
        "--width", "480",
        "--height", "270",
        "--output", test_out,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert os.path.exists(test_out)
        assert os.path.getsize(test_out) > 1000
    finally:
        if os.path.exists(test_out):
            os.remove(test_out)


def test_cli_zero_args_default():
    """Verify executing main.py with zero CLI arguments generates output_handdrawn.mp4."""
    out_file = "output_handdrawn.mp4"
    if os.path.exists(out_file):
        os.remove(out_file)

    cmd = [sys.executable, "main.py"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"CLI zero-arg failed with stderr: {result.stderr}"
        assert os.path.exists(out_file)
        assert os.path.getsize(out_file) > 1000
        assert "Render completed" in result.stdout
    finally:
        if os.path.exists(out_file):
            os.remove(out_file)



def test_cli_invalid_file():
    """Verify CLI fails gracefully when invalid svg file path is provided."""
    cmd = [
        sys.executable,
        "main.py",
        "--svg", "non_existent_file.svg",
        "--output", "test_invalid.mp4",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "not found" in result.stderr.lower() or "not found" in result.stdout.lower() or "error" in result.stderr.lower()


def test_cli_invalid_tip_args():
    """Verify CLI fails when only one of tip-x or tip-y is provided."""
    cmd = [
        sys.executable,
        "main.py",
        "--tip-x", "24",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "tip-x and --tip-y" in result.stderr


def test_cli_invalid_hand_file():
    """Verify CLI fails when hand graphic file is missing."""
    cmd = [
        sys.executable,
        "main.py",
        "--hand", "non_existent_hand.png",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "hand image file not found" in result.stderr.lower()


def test_cli_invalid_dimension():
    """Verify CLI rejects invalid canvas dimensions."""
    cmd = [
        sys.executable,
        "main.py",
        "--width", "-500",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0


def test_main_direct_invocation(tmp_path):
    """Test invoking main() directly in Python without subprocess."""
    from main import main

    out_file = str(tmp_path / "direct_call.mp4")
    ret = main([
        "--svg", "assets/demo_sketch.svg",
        "--hand", "assets/default_hand.png",
        "--output", out_file,
        "--duration", "0.5",
        "--hold", "0.2",
        "--exit", "0.2",
        "--fps", "10",
        "--width", "320",
        "--height", "180",
    ])
    assert ret == 0
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 1000

