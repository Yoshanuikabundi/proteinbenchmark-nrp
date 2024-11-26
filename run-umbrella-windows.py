#!/usr/bin/env python3

import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

INITIALS = "jm"
SCRIPT_PATH = Path("umbrella-scripts/run-umbrella-window.py")
LOCAL_RESULT_DIR = Path("results")
TARGET = "gb3"
FF = "null-0.0.3-pair-opc3"
N_REPLICAS = 1
N_WINDOWS = 1


def main():
    script_commit = get_script_commit(SCRIPT_PATH)
    with open("k8s_template.yaml") as f:
        template = yaml.safe_load(f)
    for replica in range(1, N_REPLICAS + 1):
        for window_int in range(N_WINDOWS):
            window = f"{window_int:02d}"

            k8s_manifest_path = (
                LOCAL_RESULT_DIR
                / f"{TARGET}-{FF}"
                / f"replica-{replica}"
                / f"{TARGET}-{FF}-{replica}-{window}.yaml"
            )

            manifest = add_env_to_template(
                template,
                {
                    "PROTBENCH_REPLICA": replica,
                    "PROTBENCH_TARGET": TARGET,
                    "PROTBENCH_FF": FF,
                    "PROTBENCH_WINDOW": window,
                    "PROTBENCH_SCRIPT_COMMIT": script_commit,
                    "PROTBENCH_SCRIPT_PATH": SCRIPT_PATH,
                    "PROTBENCH_REQUIRED_FILES": "\n".join([
                        f"{TARGET}-{FF}/setup/",
                        f"{TARGET}-{FF}/replica-{replica}/{TARGET}-{FF}-equilibration-1.xml",
                        f"{TARGET}-{FF}/replica-{replica}/{TARGET}-{FF}-window-{window}.pdb",
                        f"{TARGET}-{FF}/replica-{replica}/window-{window}/",
                    ]),
                },
            )

            manifest.setdefault("metadata", {})["name"] = (
                f"pb-{INITIALS}-{TARGET}-{FF}-{replica}-{window}".replace(".", "")
            )

            requested_resources = {"memory": "4Gi", "cpu": "1", "nvidia.com/gpu": "1"}
            manifest["spec"]["template"]["spec"]["containers"][-1]["resources"] = {
                "limits": dict(requested_resources),
                "requests": dict(requested_resources),
            }

            if "--dry-run" in sys.argv:
                yaml.safe_dump(
                    manifest,
                    sys.stdout,
                )
            else:
                k8s_manifest_path.parent.mkdir(parents=True, exist_ok=True)

                with open(k8s_manifest_path, "x") as f:
                    yaml.safe_dump(manifest, f)

                subprocess.run(
                    [
                        "kubectl",
                        "apply",
                        "-f",
                        k8s_manifest_path,
                    ],
                    check=True,
                )


def get_script_commit(script_path: Path) -> str:
    script_is_ignored = (
        subprocess.run(
            ["git", "check-ignore", script_path],
            check=False,
            text=True,
            capture_output=True,
        ).returncode
        == 0
    )
    script_is_checked_in = (
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", script_path],
            check=False,
            text=True,
            capture_output=True,
        ).returncode
        == 0
    )
    script_is_unmodified = (
        subprocess.run(
            ["git", "status", "--porcelain", script_path],
            check=True,
            text=True,
            capture_output=True,
        ).stdout
        == ""
    )

    if not (script_is_checked_in and script_is_unmodified) or script_is_ignored:
        print(script_is_checked_in, script_is_unmodified, script_is_ignored)
        raise ValueError(
            f"script {script_path} must be checked in to git so that the Kubernetes job can find it"
        )

    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, text=True, capture_output=True
    ).stdout.strip()


def get_containers(manifest):
    for container in manifest["spec"]["template"]["spec"].get("initContainers", []):
        yield container
    for container in manifest["spec"]["template"]["spec"].get("containers", []):
        yield container


def add_env_to_template(template: dict, envvars: dict[str, Any]) -> dict:
    output = deepcopy(template)
    for key, value in envvars.items():
        for container in get_containers(output):
            container.setdefault("env", []).append(
                {
                    "name": key,
                    "value": str(value),
                }
            )
    return output


if __name__ == "__main__":
    main()
