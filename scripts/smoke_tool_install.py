"""Exercise the wheel through the same isolated environment used by ``uv tool install``."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def smoke(uv: str, wheel: Path, python: str) -> None:
    wheel = wheel.resolve()
    if not wheel.is_file():
        raise AssertionError(f"Wheel does not exist: {wheel}")
    with tempfile.TemporaryDirectory(prefix="edd-tool-install-") as scratch:
        root = Path(scratch).resolve()
        tool_directory = root / "tools"
        binary_directory = root / "bin"
        project = root / "project"
        project.mkdir()
        env = {
            **os.environ,
            "UV_TOOL_DIR": str(tool_directory),
            "UV_TOOL_BIN_DIR": str(binary_directory),
            "DEEPEVAL_DISABLE_DOTENV": "1",
            "DEEPEVAL_TELEMETRY_OPT_OUT": "1",
        }
        installed = subprocess.run(
            [uv, "tool", "install", "--python", python, str(wheel)],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if installed.returncode != 0:
            raise AssertionError(f"uv tool install failed\n{installed.stdout}\n{installed.stderr}")
        executable = binary_directory / "edd"
        if not executable.is_file():
            raise AssertionError("uv tool install did not expose the edd executable")

        def invoke(*arguments: str, expected: int = 0) -> dict:
            result = subprocess.run(
                [str(executable), *arguments, "--json"],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            if result.returncode != expected:
                raise AssertionError(
                    f"edd {arguments} exited {result.returncode}; expected {expected}\n"
                    f"{result.stdout}\n{result.stderr}"
                )
            return json.loads(result.stdout)

        doctor = invoke("doctor")
        assert doctor["decision"] == "PASS"
        initialized = invoke("init")
        assert initialized["command"] == "init" and initialized["agent"] == "codex"
        assert (project / "edd.toml").is_file()
        assert (project / ".agents/skills/edd-check/SKILL.md").is_file()
        invoke("prepare", "tool-smoke", "--brief", "Return the declared acknowledgement")
        check = invoke("check", expected=1)
        assert check["change"] == "tool-smoke" and check["decision"] == "FAIL"
        demo = invoke("demo", "cancellation")
        assert demo["demonstrated"] is True

        print(
            json.dumps(
                {
                    "result": "PASS",
                    "wheel": wheel.name,
                    "installed_command": str(executable),
                    "checks": ["doctor", "bare init", "bare check", "offline demo"],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--uv", required=True, help="uv executable")
    parser.add_argument("--wheel", required=True, type=Path, help="EDD wheel to install")
    parser.add_argument("--python", required=True, help="Python used for the isolated tool")
    arguments = parser.parse_args()
    smoke(arguments.uv, arguments.wheel, arguments.python)
