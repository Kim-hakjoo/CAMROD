"""Validate maintained workspace shell entrypoints without changing the host."""

# HH_260810 - Exercise syntax/help contracts only; setup, CAN, Docker, and
# hardware scripts must never mutate a test workstation during CTest.

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


SRC_ROOT = Path(__file__).resolve().parents[2]
OWNED_SHELL_TOOLS = (
    "setup_camrod.sh",
    "colcon_build.sh",
    "camrod_bringup/scripts/field_test_tool.sh",
    "camrod_bringup/scripts/run_bringup.sh",
    "camrod_platform/scripts/install_can0_service.sh",
    "camrod_platform/scripts/setup_can0.sh",
    "camrod_ui/scripts/sync_frontend_build.sh",
    "camrod_voice/setup_bt_audio.sh",
    "docker/build_module.sh",
    "docker/buildx_camrod.sh",
    "docker/entrypoint.camrod.sh",
    "docker/run_module.sh",
)


def test_maintained_shell_entrypoints_parse() -> None:
    """Every maintained non-vendor shell entrypoint must pass Bash parsing."""
    for relative_path in OWNED_SHELL_TOOLS:
        path = SRC_ROOT / relative_path
        assert path.is_file(), relative_path
        assert path.stat().st_mode & 0o111, relative_path
        subprocess.run(
            ["bash", "-n", str(path)],
            cwd=SRC_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )


def test_setup_help_is_non_mutating_and_resolves_workspace() -> None:
    """The dependency installer must explain usage before any host action."""
    result = subprocess.run(
        [str(SRC_ROOT / "setup_camrod.sh"), "--help"],
        cwd="/tmp",
        check=True,
        capture_output=True,
        text=True,
    )
    assert "One-time workspace setup" in result.stdout
    assert "./setup_camrod.sh --no-rosdep" in result.stdout


def test_setup_declares_renderer_runtime_dependencies() -> None:
    """No-rosdep setup must still install dependencies of installed renderers."""
    source = (SRC_ROOT / "setup_camrod.sh").read_text(encoding="utf-8")
    package = (SRC_ROOT / "camrod_bringup/package.xml").read_text(encoding="utf-8")
    for dependency in ("python3-numpy", "python3-matplotlib", "python3-pil", "python3-yaml"):
        assert dependency in source
        assert f"<exec_depend>{dependency}</exec_depend>" in package


def test_frontend_sync_publishes_complete_assets_before_atomic_index() -> None:
    """A running kiosk must never observe an index before its assets exist."""
    sync_source = (
        SRC_ROOT / "camrod_ui/scripts/sync_frontend_build.sh"
    ).read_text(encoding="utf-8")
    sync_body = sync_source[
        sync_source.index("sync_build_tree() {"):sync_source.index("\nsynced=0")
    ]

    assert "set -euo pipefail" in sync_source
    assert 'find "$SRC" -type f' in sync_body
    assert 'find "$SRC/static" -type f' in sync_body
    assert sync_body.index('find "$SRC" -type f') < sync_body.index(
        'publish_index "$dst"'
    )
    assert sync_body.index('find "$SRC/static" -type f') < sync_body.index(
        'publish_index "$dst"'
    )
    assert 'mv -f "$temporary_index" "$dst/index.html"' in sync_source


def _stub_docker_environment(tmp_path):
    bin_dir = tmp_path / 'stub-bin'
    bin_dir.mkdir()
    capture = tmp_path / 'docker-arguments.json'
    stub = bin_dir / 'docker'
    stub.write_text(
        f'#!{sys.executable}\n'
        'import json, os, pathlib, sys\n'
        'pathlib.Path(os.environ["CAMROD_TEST_DOCKER_ARGS"]).write_text('
        'json.dumps(sys.argv[1:]))\n',
        encoding='utf-8',
    )
    stub.chmod(0o755)
    env = dict(os.environ)
    env['PATH'] = f'{bin_dir}{os.pathsep}{env.get("PATH", "")}'
    env['CAMROD_TEST_DOCKER_ARGS'] = str(capture)
    return env, capture


def test_module_runner_mounts_own_checkout_and_keeps_command_arguments(tmp_path):
    """Run only a stub Docker CLI, then check the container command in isolation."""
    checkout = tmp_path / 'checkout with spaces'
    script = checkout / 'docker/run_module.sh'
    script.parent.mkdir(parents=True)
    shutil.copy2(SRC_ROOT / 'docker/run_module.sh', script)
    link = tmp_path / 'module-runner'
    link.symlink_to(script)
    env, capture = _stub_docker_environment(tmp_path)
    marker = tmp_path / 'must-not-exist'
    literal_arguments = [
        'label:=two words',
        '',
        'single\' and "double" quotes',
        f'$(touch {marker})',
        f'; touch {marker}',
        '*.yaml',
    ]
    command = [
        sys.executable, '-c', 'import json,sys; print(json.dumps(sys.argv[1:]))',
        *literal_arguments,
    ]
    subprocess.run(
        [str(link), 'camrod-test:local', *command],
        cwd=tmp_path, env=env, check=True, capture_output=True, text=True,
    )

    args = json.loads(capture.read_text(encoding='utf-8'))
    assert args[0] == 'run'
    assert args[args.index('-v') + 1] == f'{checkout}:/workspaces/camrod_ws/src:rw'
    assert args[args.index('-w') + 1] == '/workspaces/camrod_ws'
    container_command = args[args.index('camrod-test:local') + 1:]
    assert container_command[:2] == ['bash', '-lc']
    assert container_command[4:] == command

    # Replace ROS sourcing/building with shell no-ops before executing the real
    # bootstrap text. Only the harmless Python argv printer above can execute.
    result = subprocess.run(
        ['bash', '-c', 'source() { :; }\ncolcon() { :; }\n' + container_command[2],
         *container_command[3:]],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    )
    assert json.loads(result.stdout) == literal_arguments
    assert not marker.exists()


@pytest.mark.parametrize('base_image', [None, 'example.test/custom-base:humble'])
def test_module_builder_uses_own_checkout_and_requested_base(tmp_path, base_image):
    """Inspect Docker build arguments without contacting a daemon or registry."""
    env, capture = _stub_docker_environment(tmp_path)
    env.pop('BASE_IMAGE', None)
    if base_image is not None:
        env['BASE_IMAGE'] = base_image
    link = tmp_path / 'module-builder'
    link.symlink_to(SRC_ROOT / 'docker/build_module.sh')
    subprocess.run(
        [str(link), 'camrod_bringup', 'test-output:local'],
        cwd=tmp_path, env=env, check=True, capture_output=True, text=True,
    )

    args = json.loads(capture.read_text(encoding='utf-8'))
    assert args == [
        'build', '-f', str(SRC_ROOT / 'docker/Dockerfile.module'),
        '--build-arg', f'BASE_IMAGE={base_image or "camrod/base:humble"}',
        '--build-arg', 'MODULE=camrod_bringup', '-t', 'test-output:local',
        str(SRC_ROOT),
    ]
