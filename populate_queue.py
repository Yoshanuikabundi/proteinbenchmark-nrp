#!/usr/bin/env python3

"""
Populate a redis list via kubectl exec

Check the state of the list:
    echo lrange $QUEUE_NAME 0 -1 | kubectl exec --stdin $POD_NAME -- redis-cli

Clear the list:
    echo del $QUEUE_NAME | kubectl exec --stdin $POD_NAME -- redis-cli
"""

import subprocess
import sys
from typing import Generator, Sequence

QUEUE_NAME = "job2"
REDIS_POD_NAME = "deploy/proteinbenchmark-jm-redis"

N_NEW_REPLICAS = 1
FIRST_REPLICA_INDEX = 0
TARGETS = [
    "ala5",
]


def generate_queue(
    targets: Sequence[str] = TARGETS,
    n_replicas: int = N_NEW_REPLICAS,
    first_replica_index: int = FIRST_REPLICA_INDEX,
) -> Generator[str, None, None]:
    for i in range(first_replica_index, n_replicas + first_replica_index):
        for target in targets:
            yield f"{target}#{i}"


def main():
    redis_command = f"rpush {QUEUE_NAME} {' '.join(generate_queue())}"
    if "--dry-run" in sys.argv:
        print(redis_command)
    else:
        subprocess.run(
            args=[
                "kubectl",
                "exec",
                "--stdin",
                REDIS_POD_NAME,
                "--",
                "redis-cli",
            ],
            input=redis_command,
            text=True,
            check=True,
        )


if __name__ == "__main__":
    main()
