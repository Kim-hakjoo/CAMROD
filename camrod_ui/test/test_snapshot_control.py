"""Unit coverage for the administrator snapshot bridge and frontend contract."""

import asyncio
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

from rclpy.time import Time

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "runtime" / "python"),
)

from camrod_ui.ui_backend_node import UiBackendNode  # noqa: E402


class _DoneFuture:

    def __init__(self, result):
        self._result = result

    def done(self):
        return True

    def result(self):
        return self._result


class _FakeClient:

    def __init__(self, result, ready=True):
        self.ready = ready
        self.result = result
        self.requests = []

    def service_is_ready(self):
        return self.ready

    def call_async(self, request):
        self.requests.append(request)
        return _DoneFuture(self.result)


def _backend(output_directory: str):
    backend = UiBackendNode.__new__(UiBackendNode)
    backend.snapshot_output_directory = Path(output_directory).resolve()
    backend.snapshot_request_timeout_s = 1.0
    backend.snapshot_minimum_free_space_mb = 0
    backend._snapshot_lock = threading.Lock()
    backend._snapshot_write_pending = False
    backend._snapshot_last_result = {}
    backend.snapshot_configure_client = _FakeClient(
        SimpleNamespace(
            success=True,
            recording=True,
            writing=False,
            active_topics=[],
            dynamic_topics=[],
            rejected_topics=[],
            message="active",
        )
    )
    return backend


class SnapshotBackendTest(unittest.TestCase):

    def test_topic_input_normalizes_deduplicates_and_rejects_invalid_names(self):
        topics, rejected = UiBackendNode._normalize_snapshot_topics([
            "sensing/radar/right1/range",
            "/sensing/radar/right1/range",
            "/bad topic",
        ])
        self.assertEqual(topics, ["/sensing/radar/right1/range"])
        self.assertEqual(rejected, ["/bad topic"])

    def test_snapshot_uses_server_owned_directory_and_sanitized_label(self):
        response = SimpleNamespace(success=True, message="Saved 12 messages")
        with tempfile.TemporaryDirectory() as directory:
            backend = _backend(directory)
            backend.snapshot_client = _FakeClient(response)
            result = asyncio.run(
                backend.trigger_snapshot(label="right radar/../check", selected_topics=[])
            )

            self.assertTrue(result["success"])
            self.assertTrue(result["path"].startswith(str(Path(directory).resolve())))
            self.assertIn("right_radar_check", Path(result["path"]).name)
            self.assertNotIn("..", Path(result["path"]).name)
            self.assertEqual(backend.snapshot_client.requests[0].topics, [])
            self.assertFalse(backend._snapshot_write_pending)

    def test_snapshot_uses_operator_selected_output_directory(self):
        response = SimpleNamespace(success=True, message="Saved 12 messages")
        with tempfile.TemporaryDirectory() as directory:
            backend = _backend(directory)
            backend.snapshot_client = _FakeClient(response)
            selected_directory = Path(directory) / "field test" / "bags"
            result = asyncio.run(
                backend.trigger_snapshot(
                    label="radar",
                    selected_topics=[],
                    output_directory=str(selected_directory),
                )
            )

            self.assertTrue(result["success"])
            self.assertEqual(Path(result["path"]).parent, selected_directory)
            self.assertTrue(selected_directory.is_dir())
            self.assertEqual(
                Path(backend.snapshot_client.requests[0].filename).parent,
                selected_directory,
            )

    def test_snapshot_rejects_relative_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = _backend(directory)
            backend.snapshot_client = _FakeClient(
                SimpleNamespace(success=True, message="unused")
            )
            result = asyncio.run(
                backend.trigger_snapshot(output_directory="relative/bags")
            )

            self.assertFalse(result["success"])
            self.assertIn("absolute path", result["message"])
            self.assertEqual(backend.snapshot_client.requests, [])
            self.assertFalse(backend._snapshot_write_pending)

    def test_snapshot_applies_requested_lookback_to_start_time(self):
        response = SimpleNamespace(success=True, message="Saved 12 messages")
        with tempfile.TemporaryDirectory() as directory:
            backend = _backend(directory)
            backend.snapshot_client = _FakeClient(response)
            backend.get_clock = lambda: SimpleNamespace(
                now=lambda: Time(seconds=100.0)
            )
            result = asyncio.run(
                backend.trigger_snapshot(selected_topics=[], lookback_seconds=30)
            )

            self.assertTrue(result["success"])
            request = backend.snapshot_client.requests[0]
            self.assertEqual(request.start_time.sec, 70)
            self.assertEqual(request.start_time.nanosec, 0)

    def test_busy_snapshot_is_rejected_without_calling_service(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = _backend(directory)
            backend._snapshot_write_pending = True
            backend.snapshot_client = _FakeClient(
                SimpleNamespace(success=True, message="unused")
            )
            result = asyncio.run(backend.trigger_snapshot())
            self.assertFalse(result["success"])
            self.assertTrue(result["busy"])
            self.assertEqual(backend.snapshot_client.requests, [])

    def test_frontend_mounts_separate_buffer_and_write_controls(self):
        frontend = (
            Path(__file__).resolve().parents[1]
            / "camrod_ui_robot/assets/frontend/src/SnapshotControl.js"
        ).read_text(encoding="utf-8")
        app = (
            Path(__file__).resolve().parents[1]
            / "camrod_ui_robot/assets/frontend/src/App.js"
        ).read_text(encoding="utf-8")
        self.assertIn("<SnapshotControl />", app)
        self.assertIn("{ id: 'snapshot', label: '스냅샷' }", app)
        self.assertIn("activeTab === 'snapshot'", app)
        self.assertIn("...TELEMETRY_TABS,", app)
        self.assertNotIn("      <SnapshotControl />\n\n      <div className=\"steering-tuning-card\">", app)
        self.assertIn("/api/admin/snapshot/topics", frontend)
        self.assertIn("/api/admin/snapshot/status", frontend)
        self.assertIn("/api/admin/snapshot'", frontend)
        self.assertIn("버퍼링 시작", frontend)
        self.assertIn("ROSBAG Snapshot", frontend)
        self.assertIn("스냅샷 저장", frontend)
        self.assertIn("저장 폴더", frontend)
        self.assertIn("저장 범위", frontend)
        self.assertIn("lookback_seconds", frontend)
        self.assertIn("파일 이름 태그 (선택)", frontend)
        self.assertIn("output_directory", frontend)


if __name__ == "__main__":
    unittest.main()
