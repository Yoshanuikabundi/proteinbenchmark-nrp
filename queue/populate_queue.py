#!/usr/bin/env python3

"""
Populate a redis list via kubectl exec

Check the state of the list:
    echo lrange $QUEUE_NAME 0 -1 | kubectl exec --stdin $POD_NAME -- redis-cli

Clear the list:
    echo del $QUEUE_NAME | kubectl exec --stdin $POD_NAME -- redis-cli
"""

import json
import subprocess
import sys
from typing import Generator
from uuid import uuid4

QUEUE_NAME = "proteinbenchmark"
REDIS_POD_NAME = "deploy/proteinbenchmark-jm-redis"

TARGETS = [
    "test",
]
FORCE_FIELD = "null-0.0.3-pair-nmr-1e4-opc3"


def generate_queue() -> Generator[dict[str, str], None, None]:
    for target in TARGETS:
        yield dict(
            job="steered",
            target=target,
            force_field=FORCE_FIELD,
        )


def generate_command(data):
    item_id = uuid4().hex
    commands = [
        f"SET {QUEUE_NAME}:item:{item_id} '{json.dumps(data)}'",
        f"LPUSH {QUEUE_NAME}:queue {item_id}",
    ]
    return "\n".join(commands)


def main():
    redis_commands = "\n".join(
        (
            "MULTI",
            *(generate_command(data) for data in generate_queue()),
            "EXEC",
        )
    )
    if "--dry-run" in sys.argv:
        print(redis_commands)
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
            input=redis_commands,
            text=True,
            check=True,
        )


if __name__ == "__main__":
    main()
