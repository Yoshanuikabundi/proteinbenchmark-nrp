import json
import subprocess
from itertools import count
from pathlib import Path
from time import sleep
from typing import Literal

from redis import Redis
from redis_work_queue import Item, KeyPrefix, WorkQueue


def worker_function(
    output_directory: Path,
    job: Literal["window", "steered"],
    target: str = "gb3",
    force_field: str = "null-0.0.3-pair-opc3",
    replica: int = 1,
    window: int = 0,
) -> list[
    dict[Literal["window", "job", "target", "force_field", "replica"], int | str]
]:
    if job == "window":
        subprocess.run(
            [
                "umbrella-scripts/run-umbrella-window.py",
                f"--force-field={force_field}",
                f"--output_directory={output_directory}",
                f"--replica={replica}",
                f"--target={target}",
                f"--window_index={window}",
            ],
            check=True,
        )
        return []
    elif job == "steered":
        subprocess.run(
            [
                "umbrella-scripts/run-steered-md.py",
                f"--force-field={force_field}",
                f"--output_directory={output_directory}",
                f"--replica={replica}",
                f"--target={target}",
            ],
            check=True,
        )
        n_generated_windows = len(list(Path.glob(".*-window-.*.pdb")))
        return [
            {
                "window": i,
                "job": "steered",
                "target": target,
                "force_field": force_field,
                "replica": replica,
            }
            for i in range(n_generated_windows)
        ]
    else:
        raise ValueError(f"Unknown job type {job}")


class CompletableWorkQueue(WorkQueue):
    def has_work_left(self, db: Redis):
        """``True`` if there is still work left on the queue, ``False`` otherwise.

        Note that this function may return ``True`` even though no work is available;
        in this case, either jobs are still running, or the queue should be cleaned.
        """
        all_items: list[bytes | str] = db.keys(self._item_data_key.of("*"))
        return len(all_items) != 0


def main():
    print("Connecting to queue")

    db = Redis(host="pdbscan-jm-redis")
    q = CompletableWorkQueue(KeyPrefix("proteinbenchmark"))

    print("Worker with sessionID: " + q._session)
    print(
        f"Initial queue state: ready={q.queue_len(db)}, processing={q.processing(db)}"
    )

    while q.has_work_left():
        print("Requesting lease")
        item = q.lease(db, lease_secs=9999, block=True, timeout=2)
        if item is not None:
            item_data = item.data_json()
            print(f"Working on {item_data}")

            new_jobs = worker_function(output_directory=Path("/data/"), **item_data)

            we_are_first_to_complete_item = q.complete(db, item)

            if we_are_first_to_complete_item:
                copy_data_to_pvc()

                pipeline = db.pipeline()
                for job in new_jobs:
                    new_item = Item.from_json_data(job)
                    q.add_unique_item_to_pipeline(pipeline, new_item)
                pipeline.execute()
        else:
            print("Waiting for work")
            sleep(10)
    print("Queue empty, exiting")


if __name__ == "__main__":
    main()
