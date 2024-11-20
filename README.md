# proteinbenchmark-nrp

Scripts for running proteinbenchmarks on NRP.

Each window is run in its own pod. The general outline of a pod is described by `proteinbenchmark_jm_template.yaml`, but this file is used as a template by the `run-umbrella-windows.py` script to produce Kubernetes manifest files for each simulation.

The pod performs the following actions:

1. Clone this repo to `/opt/repo` and check out the commit specified in `$SCRIPT_COMMIT`
2. Copy the contents of the `/results` directory of the `proteinbenchmark-jm-bucket` S3 bucket to `/results`
3. Execute the command `/opt/repo/$SCRIPT_PATH` with the appropriate command line flags to execute an umbrella sampling window
4. Copy any contents of the `/results` directory that are newer than the corresponding file in the S3 bucket back to the S3 bucket

If all the above succeeded, the pod completes. If the umbrella sampling window failed, step 4 is executed before the pod restarts. This is important because Kubernetes is "allowed" to stop or restart pods whenever it wants, for example to allow a higher priority job to take the pod's resources.

The `run-umbrella-windows.py` script copies the template YAML file for each window with the following modifications:

1. The target, force field, replica and window are all appended to the name of each container
2. The `$SCRIPT_COMMIT` and `$SCRIPT_PATH` environment variables are set to ensure that the current version of the `umbrella-scripts/run-umbrella-window.py` script is run in the container (it should be committed and pushed before executing `run-umbrella-windows.py`)
3. Other environment variables are set to specify the target, force field, replica and window.

## Providence

The actual Kubernetes manifest executed by NRP is stored in `results/$TARGET-$FF/replica-$REPLICA/$TARGET-$FF-$REPLICA-$WINDOW.yaml`. If this file already exists, `run-umbrella-windows.py` will refuse to overwrite it to avoid deleting providence of a previous run when `run-umbrella-windows.py` has not been updated correctly. The path, repository, and commit hash of the script used in this manifest are stored in the manifest YAML file, so combined with this Git repository this should be sufficient information to reproduce a run.

## Accessing results

Results are stored in an S3 bucket provided by NRP. This includes all input and output files from the pod itself. The contents of this bucket are copied to the pod during initialization, and copied back to the bucket when a window is completed or the pod crashes. The `--update` switch is passed to RClone for this copy, so only files that have been changed on the pod should be copied, but I haven't tested this. This should eventually be fine tuned so that only the files necessary for a particular pod are copied.

To copy files from the bucket to your machine, first ask the NRP admins on Matrix to give you S3 credentials, the set up RClone with your credentials, and then run a command like:

```bash
rclone copy nrp:proteinbenchmark-jm-bucket/results results
```

I don't actually know if NRP buckets are available per namespace or per user, so you might need your own bucket. S3 can also be set up to provide public HTTP access to files if that's preferable!

## Useful commands and websites

Visualization of GPU utilisation: https://grafana.nrp-nautilus.io/d/dRG9q0Ymz/k8s-compute-resources-namespace-gpus?var-namespace=openforcefield&orgId=1&refresh=auto&from=now-1h&to=now

Visualization of CPU utilisation: https://grafana.nrp-nautilus.io/d/85a562078cdf77779eaa1add43ccec1e/kubernetes-compute-resources-namespace-pods?orgId=1&refresh=10s&var-datasource=default&var-cluster=&var-namespace=openforcefield

NRP Nautilus docs: https://ucsd-prp.gitlab.io/

NRP GitLab instance: https://gitlab.nrp-nautilus.io/

Useful commands:

```bash
# Get the status of an underway production simulation
kubectl exec -it proteinbenchmark-jm-${TARGET}-${FF}-${REPLICA}-${WINDOW} -- cat /results/${TARGET}-${FF}/replica-${REPLICA}/window-${WINDOW}/${TARGET}-${FF}-production.out
```
