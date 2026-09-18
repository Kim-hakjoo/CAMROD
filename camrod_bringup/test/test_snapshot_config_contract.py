from pathlib import Path

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_CONFIG = PACKAGE_ROOT / "config" / "snapshot" / "camrod_topics.params.yaml"
LAUNCH_DEFAULTS = PACKAGE_ROOT / "config" / "bringup" / "launch_defaults.yaml"
BRINGUP_LAUNCH = PACKAGE_ROOT / "launch" / "_bringup_impl.py"


def _snapshot_parameters():
    return yaml.safe_load(SNAPSHOT_CONFIG.read_text(encoding="utf-8"))["/**"][
        "ros__parameters"
    ]


def test_snapshot_topics_have_unique_details_and_absolute_names():
    params = _snapshot_parameters()
    topics = params["topics"]
    details = params["topic_details"]

    assert len(topics) == len(set(topics))
    assert all(topic.startswith("/") for topic in topics)
    assert set(topics) == set(details)
    assert all(details[topic].get("type") for topic in topics)


def test_five_minute_buffer_is_written_in_one_minute_bagfiles():
    params = _snapshot_parameters()

    assert params["default_duration_limit"] == 300.0
    assert params["bagfile_split_duration_s"] == 60


def test_snapshot_covers_each_debug_layer_and_right_radar_raw_data():
    topics = set(_snapshot_parameters()["topics"])
    required = {
        "/system/diagnostics_agg",
        "/sensing/radar/right1/range",
        "/perception/obstacles",
        "/planning/state_machine/state",
        "/ui/selected_destination",
        "/control/cmd_vel_safety_gate/status",
        "/platform/status",
        "/tf",
        "/tf_static",
    }

    assert required <= topics


def test_bringup_owns_and_forwards_snapshot_configuration():
    defaults = yaml.safe_load(LAUNCH_DEFAULTS.read_text(encoding="utf-8"))["bringup"]
    launch_source = BRINGUP_LAUNCH.read_text(encoding="utf-8")

    assert defaults["runtime"]["enable_snapshot"] is True
    assert defaults["snapshot"]["param_file"] == "snapshot/camrod_topics.params.yaml"
    assert "bringup_cfg(cfg_get(" in launch_source
    assert "'params_file': lc['snapshot_param_file']" in launch_source
    assert "'camrod_snapshot.launch.py'" in launch_source
