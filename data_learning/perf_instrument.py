#!/usr/bin/env python3
"""Performance instrumentation for pro_render.

Tracks per-stage timing, memory usage, process metrics, and generates
diagnostic reports to isolate render bottlenecks.
"""

import os
import subprocess
import sys
import time
import json
from contextlib import contextmanager
from pathlib import Path
from dataclasses import dataclass, asdict, field

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


@dataclass
class MemorySnapshot:
    """Process memory state."""
    rss_mb: float  # Resident Set Size in MB
    vms_mb: float  # Virtual Memory in MB
    available_mb: float  # System available memory in MB
    fd_count: int  # Number of open file descriptors


@dataclass
class ProcessMetrics:
    """Metrics for a single subprocess."""
    name: str  # ffmpeg, blender, etc
    start_time: float  # Wall-clock start
    end_time: float = 0.0
    elapsed_s: float = 0.0
    exit_code: int = 0
    was_waited: bool = False


@dataclass
class ShotMetrics:
    """Metrics for a single shot render."""
    shot_idx: int
    shot_kind: str
    planned_duration_s: float
    asset_resolution_s: float = 0.0
    scene_construction_s: float = 0.0
    frame_render_s: float = 0.0
    encoding_s: float = 0.0
    cleanup_s: float = 0.0
    total_s: float = 0.0
    mem_start: MemorySnapshot = field(default_factory=lambda: MemorySnapshot(0, 0, 0, 0))
    mem_end: MemorySnapshot = field(default_factory=lambda: MemorySnapshot(0, 0, 0, 0))
    processes: list[ProcessMetrics] = field(default_factory=list)


@dataclass
class RenderMetrics:
    """Full render session metrics."""
    story_slug: str
    total_beats: int
    total_shots: int
    start_time: float
    end_time: float = 0.0
    total_elapsed_s: float = 0.0
    planned_total_s: float = 0.0
    actual_duration_s: float = 0.0
    shots: list[ShotMetrics] = field(default_factory=list)
    stages: dict = field(default_factory=dict)  # Named stages like "narration", "assembly"


_current_render = None
_current_shot = None
_shot_wall_start = 0.0
_process_pids = {}


def init_render(story_slug: str, total_beats: int, total_shots: int):
    """Start a new render session."""
    global _current_render
    _current_render = RenderMetrics(
        story_slug=story_slug,
        total_beats=total_beats,
        total_shots=total_shots,
        start_time=time.time(),
    )


def start_shot(shot_idx: int, shot_kind: str, planned_duration_s: float):
    """Begin tracking a shot."""
    global _current_shot, _shot_wall_start
    _shot_wall_start = time.time()
    _current_shot = ShotMetrics(
        shot_idx=shot_idx,
        shot_kind=shot_kind,
        planned_duration_s=planned_duration_s,
        mem_start=_capture_memory(),
    )


def end_shot():
    """Finalize the current shot. total_s is WALL time for the whole shot,
    so unattributed cost (total - sum of phases) is visible, never hidden."""
    global _current_shot, _shot_wall_start
    if _current_shot:
        _current_shot.mem_end = _capture_memory()
        _current_shot.total_s = time.time() - _shot_wall_start
        if _current_render:
            _current_render.shots.append(_current_shot)
        _current_shot = None


@contextmanager
def stage(name: str, shot_phase: str = None):
    """Context manager for timing a render phase.

    Args:
        name: Phase name (e.g., "narration", "video_assembly")
        shot_phase: If set, accumulate into this shot phase
                   (asset_resolution, scene_construction, frame_render, encoding, cleanup)
    """
    start = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start
        if _current_render:
            if name not in _current_render.stages:
                _current_render.stages[name] = {"elapsed_s": 0.0, "count": 0}
            _current_render.stages[name]["elapsed_s"] += elapsed
            _current_render.stages[name]["count"] += 1

        if _current_shot and shot_phase:
            attr = f"{shot_phase}_s"
            if hasattr(_current_shot, attr):
                # ACCUMULATE — one shot can resolve several assets
                setattr(_current_shot, attr,
                        getattr(_current_shot, attr) + elapsed)

        print(f"[perf] {name}: {elapsed:.2f}s", file=sys.stderr)


@contextmanager
def track_subprocess(name: str):
    """Context manager to track subprocess lifecycle.

    Args:
        name: Subprocess name (e.g., "ffmpeg_shot_3")
    """
    start = time.time()
    metrics = ProcessMetrics(name=name, start_time=start)
    pid = os.getpid()  # Will be overridden if we capture a child PID

    try:
        yield metrics
    finally:
        metrics.end_time = time.time()
        metrics.elapsed_s = metrics.end_time - metrics.start_time
        if _current_shot:
            _current_shot.processes.append(metrics)


def track_ffmpeg_call(cmd_args: list[str]) -> int:
    """Execute an ffmpeg command and track it.

    Args:
        cmd_args: Full ffmpeg command line

    Returns:
        Exit code
    """
    with track_subprocess("ffmpeg") as metrics:
        result = subprocess.run(cmd_args, check=False)
        metrics.exit_code = result.returncode
        metrics.was_waited = True
        return result.returncode


def _capture_memory() -> MemorySnapshot:
    """Capture current memory state."""
    if HAS_PSUTIL:
        try:
            proc = psutil.Process()
            mem_info = proc.memory_info()
            rss_mb = mem_info.rss / 1024 / 1024
            vms_mb = mem_info.vms / 1024 / 1024
            available_mb = psutil.virtual_memory().available / 1024 / 1024
            fds = proc.num_fds() if hasattr(proc, 'num_fds') else 0
            return MemorySnapshot(
                rss_mb=rss_mb,
                vms_mb=vms_mb,
                available_mb=available_mb,
                fd_count=fds,
            )
        except Exception as e:
            print(f"[perf] memory capture (psutil) failed: {e}", file=sys.stderr)
            return MemorySnapshot(0, 0, 0, 0)
    else:
        # Fallback: read from /proc/self/status on Linux
        try:
            status_file = Path("/proc/self/status")
            if status_file.exists():
                status = status_file.read_text()
                rss_kb = 0
                for line in status.split('\n'):
                    if line.startswith("VmRSS:"):
                        rss_kb = int(line.split()[1])
                rss_mb = rss_kb / 1024
                # Try to get available memory from /proc/meminfo
                available_mb = 0
                meminfo = Path("/proc/meminfo").read_text()
                for line in meminfo.split('\n'):
                    if line.startswith("MemAvailable:"):
                        available_mb = int(line.split()[1]) / 1024
                        break
                fds = len(list(Path("/proc/self/fd").iterdir())) if Path("/proc/self/fd").exists() else 0
                return MemorySnapshot(
                    rss_mb=rss_mb,
                    vms_mb=rss_mb,  # Approximation
                    available_mb=available_mb,
                    fd_count=fds,
                )
        except Exception as e:
            print(f"[perf] memory capture (/proc) failed: {e}", file=sys.stderr)
        return MemorySnapshot(0, 0, 0, 0)


def end_render(actual_duration_s: float, planned_total_s: float = 0.0):
    """Finalize the render session and return metrics."""
    global _current_render
    if not _current_render:
        return None

    _current_render.end_time = time.time()
    _current_render.total_elapsed_s = _current_render.end_time - _current_render.start_time
    _current_render.actual_duration_s = actual_duration_s
    _current_render.planned_total_s = planned_total_s

    result = _current_render
    _current_render = None
    return result


def report_json(metrics: RenderMetrics) -> str:
    """Generate a JSON performance report."""
    return json.dumps(asdict(metrics), indent=2)


def report_summary(metrics: RenderMetrics) -> str:
    """Generate a human-readable performance summary."""
    lines = [
        f"=== PERFORMANCE REPORT: {metrics.story_slug} ===",
        f"Total time: {metrics.total_elapsed_s:.1f}s",
        f"Video duration: {metrics.actual_duration_s:.1f}s (planned {metrics.planned_total_s:.1f}s)",
        f"Shots rendered: {len(metrics.shots)}/{metrics.total_shots}",
        "",
        "Stage breakdown:",
    ]
    for stage_name in sorted(metrics.stages.keys()):
        data = metrics.stages[stage_name]
        lines.append(f"  {stage_name}: {data['elapsed_s']:.2f}s ({data['count']} calls)")

    if metrics.shots:
        lines.extend(["", "Shot timings (slowest first):"])
        sorted_shots = sorted(metrics.shots, key=lambda s: s.total_s, reverse=True)
        for shot in sorted_shots[:5]:  # Top 5
            lines.append(
                f"  Shot {shot.shot_idx} ({shot.shot_kind}): {shot.total_s:.2f}s "
                f"(render {shot.frame_render_s:.2f}s, encode {shot.encoding_s:.2f}s)"
            )

        # Memory summary
        if metrics.shots[0].mem_start.rss_mb > 0:
            first_rss = metrics.shots[0].mem_start.rss_mb
            peak_rss = max((s.mem_end.rss_mb for s in metrics.shots), default=0)
            lines.extend([
                "",
                f"Memory: start {first_rss:.0f}MB -> peak {peak_rss:.0f}MB "
                f"(Δ{peak_rss - first_rss:+.0f}MB)",
            ])

    return "\n".join(lines)


def save_metrics(metrics: RenderMetrics, path: Path):
    """Save metrics to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_json(metrics))


def deterministic_test_mode(story_dict: dict, work_dir: Path) -> dict:
    """Run a performance test on 5 representative shots without external media.

    Args:
        story_dict: Story definition with beats
        work_dir: Working directory for temp files

    Returns:
        Metrics dictionary with timing for each shot type
    """
    # This is a stub for Phase 4.4 — actual implementation in Phase 4
    print("[perf] deterministic_test_mode: stub for Phase 4.4", file=sys.stderr)
    return {}
