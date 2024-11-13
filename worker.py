from pathlib import Path
from time import sleep

from proteinbenchmark import ProteinBenchmarkSystem, benchmark_targets, force_fields

import rediswq


def worker_function(itemstr: str, dest_path: Path):
    target, _, replica = itemstr.partition("#")
    benchmark_system = ProteinBenchmarkSystem(
        result_directory=dest_path / target,
        target_name=target,
        target_parameters=benchmark_targets[target],
        force_field_name="ff14sb-tip3p",
        water_model="tip3p",
        force_field_file=force_fields["ff14sb-tip3p"]["force_field_file"],
        water_model_file=force_fields["ff14sb-tip3p"]["water_model_file"],
    )
    benchmark_system.setup()
    benchmark_system.run_simulations(replica=replica)
    benchmark_system.analyze_observables(replica=replica)


def main():
    print("Connecting to queue")

    host = "pdbscan-jm-redis"

    q = rediswq.RedisWQ(name="job2", host=host)
    print("Worker with sessionID: " + q.sessionID())
    print("Initial queue state: empty=" + str(q.empty()))
    while not q.empty():
        print("Requesting lease")
        item = q.lease(lease_secs=9999, block=True, timeout=2)
        if item is not None:
            itemstr = item.decode("utf-8")
            print("Working on " + itemstr)

            worker_function(itemstr, Path("/data/"))

            q.complete(item)
        else:
            print("Waiting for work")
            sleep(10)
    print("Queue empty, exiting")


if __name__ == "__main__":
    main()
