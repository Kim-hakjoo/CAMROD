from pathlib import Path
import os
import shutil
import subprocess

import pytest
import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "field_test_tool.sh"


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_field_tool_shell_syntax() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_gate_commands_use_native_avg_bool_contract() -> None:
    text = _script_text()

    assert "avg_msgs/msg/AvgBool" in text
    assert "std_msgs/msg/Bool" not in text
    for topic in (
        "/planning/engage",
        "/planning/mission_engage",
        "/platform/drive_enable",
    ):
        assert topic in text
    assert 'publish_gate_bool "${topic}" false' in text
    assert "publish_gate_bool /planning/engage true" in text
    assert "publish_gate_bool /platform/drive_enable true" in text


def test_stop_gate_fails_closed_and_verifies_output() -> None:
    text = _script_text()

    assert "require_gate_subscriber" in text
    assert "has no subscriber; refusing to report a gate change" in text
    assert "verify_command_disabled" in text
    assert "/control/command_enabled did not confirm false" in text
    assert "/control/planning_engaged did not confirm false" in text
    assert "Attempt every close command" in text
    assert "/platform/set_enabled" not in text


def test_recovery_recording_requires_live_safety_owners() -> None:
    text = _script_text()

    assert "ros2 topic list --include-hidden-topics" in text
    assert "required recovery topic is not active" in text
    for topic in (
        "/control/cmd_vel_safety_gate/status",
        "/control/command_enabled",
        "/localization/pose",
        "/map/cost_grid/lanelet",
        "/platform/status",
    ):
        assert topic in text


def test_recovery_metadata_separates_requested_and_recorded_topics() -> None:
    text = _script_text()

    assert "requested_topics.txt" in text
    assert "available_at_start_topics.txt" in text
    assert "bag_info.txt" in text
    assert "recorded_topics.txt" in text


def test_watch_and_profile_collect_concurrent_evidence() -> None:
    text = _script_text()

    assert "collect_watch_sample" in text
    assert "The old sequential" in text
    assert "profile_topics" in text
    assert "tegrastats --interval 1000" in text
    assert "profile) cmd_profile" in text


def test_pose_latency_command_runs_the_synchronized_probe() -> None:
    text = _script_text()

    assert "pose-latency [seconds] [output_json]" in text
    assert "cmd_pose_latency" in text
    assert "ros2 run camrod_bringup pose_latency_probe.py" in text
    assert "pose-latency) cmd_pose_latency" in text


def test_camera_yolo_defaults_to_full_acceptance_window() -> None:
    text = _script_text()

    assert "CAMERA_YOLO_ACCEPTANCE_SECONDS=300" in text
    assert "camera_payload_probe.py" in text
    assert "/sensing/camera/econ_front/camera_info" in text
    assert "/sensing/camera/econ_front/dummy_active" in text
    assert "## component native libraries" in text


def test_config_sync_rejects_extra_package_and_install_files() -> None:
    text = _script_text()

    assert "EXTRA package file:" in text
    assert "EXTRA installed file:" in text


@pytest.mark.parametrize("mutation", [None, "approved-value", "extra-key", "installed-copy"])
def test_config_accepts_only_exact_deployment_overrides(tmp_path, mutation):
    root = SCRIPT.parents[2]
    checkout = tmp_path / "checkout"
    script = checkout / "camrod_bringup/scripts/field_test_tool.sh"
    script.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, script)
    shutil.copy2(root / "colcon_build.sh", checkout / "colcon_build.sh")
    output = tmp_path / "output"
    for label in ("platform", "map", "planning", "perception", "sensing",
                  "system", "sensor_kit", "control", "localization"):
        package = f"camrod_{label}"
        package_dir = checkout / package / "config"
        deployed_dir = checkout / "camrod_bringup/config" / label
        package_dir.mkdir(parents=True)
        deployed_dir.mkdir(parents=True)
        filenames = {"platform": ["ranger_driver.yaml"],
                     "planning": ["nav2_base.yaml", "nav2_vehicle.yaml"]}.get(label, [])
        if not filenames:
            (package_dir / "fixture.yaml").write_text("value: 1\n")
            (deployed_dir / "fixture.yaml").write_text("value: 1\n")
        for filename in filenames:
            shutil.copy2(root / package / "config" / filename, package_dir / filename)
            shutil.copy2(root / "camrod_bringup/config" / label / filename,
                         deployed_dir / filename)
        shutil.copytree(package_dir, output / "install" / package / "share" / package / "config")
    shutil.copytree(checkout / "camrod_bringup/config",
                    output / "install/camrod_bringup/share/camrod_bringup/config")
    if mutation:
        changed = checkout / "camrod_bringup/config/planning/nav2_vehicle.yaml"
        if mutation == "installed-copy":
            changed = output / "install/camrod_bringup/share/camrod_bringup/config/planning/nav2_vehicle.yaml"
        content = yaml.safe_load(changed.read_text())
        values = content["controller_server"]["ros__parameters"]["RPP"]
        values["lookahead_dist" if mutation == "approved-value" else "unapproved_key"] = 99.0
        changed.write_text(yaml.safe_dump(content))
    result = subprocess.run(
        [str(script), "config"], cwd=tmp_path,
        env=dict(os.environ, CAMROD_BUILD_ROOT=str(output)),
        capture_output=True, text=True,
    )
    if mutation is None:
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.count("OK intentional deployment override:") == 3
        assert "config sync OK" in result.stdout
    else:
        assert result.returncode != 0
        assert "DIFF " in result.stdout
