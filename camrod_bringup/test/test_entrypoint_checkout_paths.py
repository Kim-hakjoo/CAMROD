"""Run the real entrypoints without installing, cleaning, or cloning anything."""
# HH_260911 - Guard checkout identity and side-effect-free help on real worktrees.
import os
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINTS = [
    'setup_camrod.sh',
    'colcon_build.sh',
    'camrod_bringup/scripts/run_bringup.sh',
    'camrod_bringup/scripts/field_test_tool.sh',
]

@pytest.mark.parametrize('name', ENTRYPOINTS)
def test_actual_entrypoint_uses_its_own_checkout(name, tmp_path):
    env = dict(os.environ)
    env.pop('CAMROD_BUILD_ROOT', None)
    result = subprocess.run(['bash', str(ROOT / name), '--print-paths'],
                            cwd=tmp_path, env=env, capture_output=True,
                            text=True, check=True)
    paths = dict(line.split('=', 1) for line in result.stdout.splitlines())
    assert Path(paths['SRC_ROOT']).resolve() == ROOT.resolve()
    assert Path(paths['BUILD_BASE']).parent == Path(paths['WS_ROOT'])
    assert Path(paths['INSTALL_BASE']).parent == Path(paths['WS_ROOT'])
    assert not Path(paths['BUILD_BASE']).is_relative_to(ROOT)

@pytest.mark.parametrize('name', ENTRYPOINTS)
def test_output_override_cannot_be_inside_checkout(name, tmp_path):
    env = dict(os.environ, CAMROD_BUILD_ROOT=str(ROOT / 'audit-forbidden-output'))
    result = subprocess.run(['bash', str(ROOT / name), '--print-paths'],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert not (ROOT / 'audit-forbidden-output').exists()

@pytest.mark.parametrize('name', ENTRYPOINTS)
def test_help_does_not_create_build_directories(name, tmp_path):
    output = tmp_path / 'not-created'
    env = dict(os.environ, CAMROD_BUILD_ROOT=str(output))
    result = subprocess.run(['bash', str(ROOT / name), '--help'],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not output.exists()

@pytest.mark.parametrize('name', ENTRYPOINTS)
def test_explicit_output_root_keeps_source_identity(name, tmp_path):
    output = tmp_path / 'isolated-build'
    env = dict(os.environ, CAMROD_BUILD_ROOT=str(output))
    result = subprocess.run(['bash', str(ROOT / name), '--print-paths'],
                            cwd=tmp_path, env=env, capture_output=True,
                            text=True, check=True)
    paths = dict(line.split('=', 1) for line in result.stdout.splitlines())
    assert Path(paths['SRC_ROOT']).resolve() == ROOT.resolve()
    assert Path(paths['WS_ROOT']).resolve() == output.resolve()
    assert not output.exists()


@pytest.mark.parametrize('name', ENTRYPOINTS[2:])
def test_field_entrypoints_resolve_symlinked_nonstandard_checkout(name, tmp_path):
    checkout = tmp_path / 'checkout with [brackets]'
    entrypoint = checkout / name
    entrypoint.parent.mkdir(parents=True)
    shutil.copy2(ROOT / name, entrypoint)
    shutil.copy2(ROOT / 'colcon_build.sh', checkout / 'colcon_build.sh')
    link = tmp_path / 'field-entrypoint'
    link.symlink_to(entrypoint)
    env = dict(os.environ)
    env.pop('CAMROD_BUILD_ROOT', None)

    result = subprocess.run(['bash', str(link), '--print-paths'],
                            cwd=ROOT, env=env, capture_output=True,
                            text=True, check=True)

    paths = dict(line.split('=', 1) for line in result.stdout.splitlines())
    assert Path(paths['SRC_ROOT']) == checkout
    assert Path(paths['WS_ROOT']) == tmp_path / '.camrod-build' / checkout.name
    assert not Path(paths['WS_ROOT']).exists()


def test_run_bringup_sources_selected_install_and_preserves_launch_arguments(tmp_path):
    output = tmp_path / 'custom output'
    install = output / 'install'
    install.mkdir(parents=True)
    # This function replaces ros2 inside the child shell; no ROS nodes launch.
    (install / 'setup.bash').write_text(
        'ros2() { printf "SELECTED_INSTALL\\n"; printf "<%s>\\n" "$@"; }\n'
    )
    env = dict(os.environ, CAMROD_BUILD_ROOT=str(output))

    result = subprocess.run(
        ['bash', str(ROOT / ENTRYPOINTS[2]), 'sim:=true', 'label:=two words'],
        cwd=tmp_path, env=env, capture_output=True, text=True, check=True,
    )

    assert 'SELECTED_INSTALL\n<launch>\n<camrod_bringup>\n' in result.stdout
    assert '<bringup.launch.py>\n<sim:=true>\n<label:=two words>\n' in result.stdout
