#!/usr/bin/env python3

import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

SCRIPT_PATH = Path("umbrella-scripts/run-umbrella-window.py")
RESULT_DIR = Path("results")
TARGET = "gb3"
FF = "null-0.0.3-pair-opc3"
N_REPLICAS = 1
N_WINDOWS = 1


def main():
    with open("proteinbenchmark_jm_template.yaml") as f:
        template = yaml.safe_load(f)
    for replica in range(1, N_REPLICAS + 1):
        for window in range(N_WINDOWS):
            target_dir = Path(RESULT_DIR, f"{TARGET}-{FF}")
            replica_dir = target_dir / f"replica-{replica}"
            k8s_manifest_path = (
                replica_dir / f"{TARGET}-{FF}-{replica}-{window:02d}.yaml"
            )

            manifest = rename_template(
                add_env_to_template(
                    template,
                    {
                        "REPLICA": replica,
                        "TARGET": TARGET,
                        "FF": FF,
                        "WINDOW": window,
                        "RESULT_DIR": RESULT_DIR,
                        "SCRIPT_COMMIT": get_script_commit(),
                        "SCRIPT_PATH": SCRIPT_PATH,
                    },
                ),
                append=f"-{TARGET}-{FF}-{replica}-{window:02d}",
            )

            requested_resources = {"memory": "4Gi", "cpu": "1", "nvidia.com/gpu": "1"}
            manifest["spec"]["containers"][-1]["resources"] = {
                "limits": dict(requested_resources),
                "requests": dict(requested_resources),
            }

            if "--dry-run" in sys.argv:
                yaml.safe_dump(
                    manifest,
                    sys.stdout,
                )
            else:
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


def get_script_commit() -> str:
    script_is_ignored = (
        subprocess.run(
            ["git", "check-ignore", SCRIPT_PATH],
            check=False,
            text=True,
            capture_output=True,
        ).returncode
        == 0
    )
    script_is_checked_in = (
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", SCRIPT_PATH],
            check=False,
            text=True,
            capture_output=True,
        ).returncode
        == 0
    )
    script_is_unmodified = (
        subprocess.run(
            ["git", "status", "--porcelain", SCRIPT_PATH],
            check=True,
            text=True,
            capture_output=True,
        ).stdout
        == ""
    )

    if not (script_is_checked_in and script_is_unmodified) or script_is_ignored:
        print(script_is_checked_in, script_is_unmodified, script_is_ignored)
        raise ValueError(
            f"script {SCRIPT_PATH} must be checked in to git so that the Kubernetes job can find it"
        )

    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, text=True, capture_output=True
    ).stdout.strip()


def get_containers(manifest):
    for container in manifest["spec"]["initContainers"]:
        yield container
    for container in manifest["spec"]["containers"]:
        yield container


def rename_template(template: dict, append: str) -> dict:
    output = deepcopy(template)
    output["metadata"]["name"] += append
    for container in get_containers(output):
        container["name"] += append
    return output


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
