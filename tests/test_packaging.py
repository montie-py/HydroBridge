"""Build the wheel and install it into a fresh venv without extras, the way a core-only user gets it.

Slower than the other tests (builds a wheel, creates a venv); skip with `pytest -m "not packaging"`.
"""
import shutil
import subprocess
import sys
import textwrap
import venv
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.packaging

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def wheel(tmp_path_factory):
    poetry = shutil.which("poetry")
    if poetry is None:
        pytest.skip("poetry is needed to build the wheel")
    out_dir = tmp_path_factory.mktemp("dist")
    subprocess.run([poetry, "build", "--format", "wheel", "--output", str(out_dir)],
                   cwd=PROJECT_ROOT, check=True, capture_output=True)
    [wheel_path] = out_dir.glob("hydrobridge-*.whl")
    return wheel_path


def installed_packages(python):
    result = subprocess.run([python, "-m", "pip", "list", "--format=freeze"],
                            capture_output=True, text=True, check=True)
    return {line.split("==")[0].lower() for line in result.stdout.split()}


@pytest.fixture(scope="module")
def fresh_venv(wheel, tmp_path_factory):
    """Python of a fresh venv with the wheel installed and no extras, and what the venv had before."""
    env_dir = tmp_path_factory.mktemp("venv")
    venv.create(env_dir, with_pip=True)
    python = env_dir / ("Scripts" if sys.platform == "win32" else "bin") / "python"
    # a fresh venv isn't empty, and what it holds depends on the Python version (3.11 adds setuptools)
    before = installed_packages(python)
    # --no-index: nothing may come from PyPI, so any required dependency would make this fail
    subprocess.run([python, "-m", "pip", "install", "--no-index", "--quiet", wheel],
                   check=True, capture_output=True)
    return python, before


@pytest.fixture(scope="module")
def core_only_python(fresh_venv):
    return fresh_venv[0]


def run(python, code):
    return subprocess.run([python, "-c", textwrap.dedent(code)], capture_output=True, text=True)


def test_wheel_contains_only_the_library(wheel):
    names = zipfile.ZipFile(wheel).namelist()
    packages = {name.split("/")[0] for name in names}
    assert packages == {"hydrobridge", wheel.name.split("-py3")[0] + ".dist-info"}
    assert "hydrobridge/register_map.py" in names


def test_dependencies_are_only_behind_extras(wheel):
    metadata = zipfile.ZipFile(wheel).read(
        next(n for n in zipfile.ZipFile(wheel).namelist() if n.endswith(".dist-info/METADATA"))
    ).decode()
    requirements = [line for line in metadata.splitlines() if line.startswith("Requires-Dist:")]
    assert requirements, "expected the adapters' dependencies listed as extras"
    assert all("extra ==" in line for line in requirements), requirements


def test_core_installs_with_nothing_else(fresh_venv):
    python, before = fresh_venv
    assert installed_packages(python) - before == {"hydrobridge"}


def test_core_works_without_extras(core_only_python):
    result = run(core_only_python, """
        import asyncio, datetime
        from hydrobridge import (RegisterField, RegisterMap, RegistersProcessingService,
                                 RawRegisterBlock, RegisterSourcePort, TelemetryPublisherPort)

        class Source(RegisterSourcePort):
            async def read_block(self):
                return RawRegisterBlock("gw", [0x3FC0, 0x0000], datetime.datetime.now())

        class Publisher(TelemetryPublisherPort):
            async def publish(self, reading):
                print(reading.registers)

        register_map = RegisterMap([RegisterField("level", 0, word_order="high_low")])
        asyncio.run(RegistersProcessingService(Source(), Publisher(), register_map).run_once())
    """)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "{'level': 1.5}"


@pytest.mark.parametrize("module, extra", [
    ("hydrobridge.adapters.modbus", "modbus"),
    ("hydrobridge.adapters.azure_iot", "azure"),
])
def test_adapter_without_its_extra_names_the_extra_to_install(core_only_python, module, extra):
    result = run(core_only_python, f"import {module}")
    assert result.returncode != 0
    assert f'pip install "hydrobridge[{extra}]"' in result.stderr
