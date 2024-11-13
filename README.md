# proteinbenchmark-nrp

Files for running [`proteinbenchmark`] on NRP.

## Configuring a benchmark

| To configure...                      | Look in the file...                  |
|--------------------------------------|--------------------------------------|
| `proteinbenchmark` branch/commit/rev | Dockerfile (requires image rebuild)  |
| Number of replicas                   | populate_queue.py                    |
| Targets to benchmark                 | populate_queue.py                    |
| Resources of each worker pod         | proteinbenchmark_jm_worker.yaml      |
| Number of worker pods                | proteinbenchmark_jm_worker.yaml      |
| Disk quota for outputs               | proteinbenchmark_jm_workervol.yaml   |
| Expected time to complete an item    | worker.py                            |

Changes to the Kubernetes `.yaml` files are applied when you run `kubectl apply -f file.yaml`. Changes to `worker.py` and `rediswq.py` must be pushed to the NRP GitLab repository and then will take effect on any new pods. Changes to the Dockerfile require the image to be rebuilt and pushed to the NRP GitLab Docker registry, from which point they will take effect on any new pods. To rebuild the Docker image and push to the NRP GitLab Docker registry:
```shell
docker build -t gitlab-registry.nrp-nautilus.io/josh.mitchell/proteinbenchmark-nrp .
docker push gitlab-registry.nrp-nautilus.io/josh.mitchell/proteinbenchmark-nrp
```

## Starting a benchmark

1. Start the redis PVC. This is a persistent disk volume that stores the status of the queue in case the redis server restarts:
```shell
kubectl apply -f proteinbenchmark_jm_redisvol.yaml
```
2. Start the redis server. This acts as a queue that the workers pull work from:
```shell
kubectl apply -f proteinbenchmark_jm_redis.yaml
```
3. Populate the queue. Queue entries take the form `{target}#{replica_index}`. For instance, to perform three replicas of the `ala5` target, put `ala5#1`, `ala5#2`, and `ala5#3` on the queue.
```shell
# remember to configure the script by editing the global variables at the top
python populate_queue.py
```
4. Start the worker PVC. This is a persistent disk volume that stores the output of completed and in progress benchmarks.
```shell
kubectl apply -f proteinbenchmark_jm_workervol.yaml
```
5. Start the worker job itself. This is a scalable collection of pods that repeatedly poll the redis server for the next job to do, execute the job, tell redis the job is complete, and repeat. A job is considered to have failed and thus returns to the queue after 9999 seconds; this is configurable in the `lease_secs` argument to the `q.lease()` call in `worker.py`:
```shell
kubectl apply -f proteinbenchmark_jm_worker.yaml
```
## Managing a benchmark

Inspect running pods:

```shell
kubectl get pods
kubectl describe pod $POD_NAME
kubectl logs $POD_NAME
```

Inspect active PVCs:

```shell
kubectl get pvcs
kubectl describe pvc proteinbenchmark-jm-workervol
kubectl describe pvc proteinbenchmark-jm-redisvol
```

Scale the number of workers running in parallel:

```shell
kubectl patch -f proteinbenchmark_jm_worker.yaml -p '{"spec":{"parallelism":10}}' # Tell kubernetes to use 10 worker pods
```

View the remaining entries in the queue:

```shell
echo lrange $QUEUE_NAME 0 -1 | kubectl exec --stdin $POD_NAME -- redis-cli
```

Restart something
```shell
kubectl delete -f name.yaml
kubectl apply -f name.yaml
```

## Finishing a benchmark

1. Push the results to a S3 bucket:
```shell
kubectl apply -f proteinbenchmark_jm_pushbucket.yaml
```
2. Download the results from the S3 bucket (you'll need the nrp remote configured in rclone):
```shell
rclone copy nrp:proteinbenchmark-jm-bucket/data proteinbenchmark_results --progress
```
3. Clean up everything still running on Kubernetes:
```shell
kubectl delete -f proteinbenchmark_jm_workervol.yaml
kubectl delete -f proteinbenchmark_jm_worker.yaml
kubectl delete -f proteinbenchmark_jm_redisvol.yaml
kubectl delete -f proteinbenchmark_jm_redis.yaml
```
4. Delete the S3 bucket (once you've got the data)


[`proteinbenchmark`]: https://github.com/openforcefield/proteinbenchmark/tree/nagl
