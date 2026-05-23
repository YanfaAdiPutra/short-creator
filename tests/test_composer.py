"""Tests for the composer helper functions (no actual ffmpeg invocation)."""

from __future__ import annotations

from short_creator.pipeline.composer import center_crop_plan


def test_center_crop_landscape_to_portrait():
    plan = center_crop_plan(1920, 1080, duration=30.0)
    # 9:16 carved from 1920x1080 should be ~608x1080
    assert plan.source_width == 1920
    assert plan.source_height == 1080
    assert plan.output_height == 1080
    assert plan.output_width == 1080 * 9 // 16  # 608
    seg = plan.segments[0]
    assert seg.start == 0.0
    assert seg.end == 30.0
    # Centered
    assert seg.x == (1920 - plan.output_width) // 2
    assert seg.y == 0


def test_center_crop_already_portrait():
    # Source is taller than 9:16 — we should crop top/bottom, not left/right.
    plan = center_crop_plan(720, 1600, duration=10.0)
    assert plan.output_width == 720
    expected_h = int(720 / (9 / 16))
    assert plan.output_height == expected_h
    seg = plan.segments[0]
    assert seg.x == 0
    assert seg.y == (1600 - expected_h) // 2
