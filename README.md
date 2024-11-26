# proteinbenchmark-nrp

Scripts for running proteinbenchmarks on NRP.

To run a simulation, edit the constants (with names in SHOUTING_CASE) at the top of `run-umbrella-windows.py`, then execute `run-umbrella-windows.py`. Please remember to set the `INITIALS` variable to your own initials so that everyone knows who to contact in case something goes wrong!

Each simulation window is run in its own job consisting of a single pod. The job manages pod failures and allows it to run for longer than 6 hours. The general outline of both job and pod is described by `k8s_template.yaml`, but this file is used as a template by the `run-umbrella-windows.py` script to produce Kubernetes manifest files for each simulation.

Each pod performs the following actions:

1. Clone this repo to `/opt/repo` and check out the commit specified in `$PROTBENCH_SCRIPT_COMMIT`
2. Copy the required contents of the `/results` directory of the `proteinbenchmark-jm-bucket` S3 bucket to `/results`
3. Pip install the `proteinbenchmark` library from the GitHub repository
4. Execute the command `/opt/repo/$PROTBENCH_SCRIPT_PATH -o/results` to execute an umbrella sampling window (or some other simulation)
5. Copy any contents of the `/results` directory that are newer than the corresponding file in the S3 bucket back to the S3 bucket

If all the above succeeded, the job completes. If the umbrella sampling window failed, step 5 is executed before the pod restarts. This is important because Kubernetes is "allowed" to stop or restart pods whenever it wants, for example to allow a higher priority job to take the pod's resources.

Note that step 2 will not fail if some required files were missing from the S3 bucket. This is because required files include outputs from previous pods that should be continued from the current pod. These outputs are not present at the start of the first pod's run, so the pod is tolerant of all files' absence. Missing files will cause errors when they are required by the script.

The `run-umbrella-windows.py` script copies the template YAML file for each window with the following modifications:

1. The name of the job is set. It describes the user's initials, as well as the target, force field, replica and window. This ensures that all jobs have a descriptive, unique and accurate name.
2. The `$PROTBENCH_SCRIPT_COMMIT` and `$PROTBENCH_SCRIPT_PATH` environment variables are set to ensure that the current version of the `umbrella-scripts/run-umbrella-window.py` script is run in the container (it should be committed and pushed before executing `run-umbrella-windows.py`)
3. The `$PROTBENCH_REQUIRED_FILES` environment var is set to a newline-separated list of files required by the script, which will be copied from the S3 bucket in an initialization container
3. Other environment variables are set to specify the target, force field, replica, window, and any other per-simulation configuration values. These environment variables should be consumed by the script.

## Configuration

| To configure...                      | Look in the file...                  |
|--------------------------------------|--------------------------------------|
| Conda environment                    | Dockerfile (requires [image rebuild])|
| Your initials (please do this)       | run-umbrella-windows.py              |
| Number of replicas                   | run-umbrella-windows.py              |
| Number of windows                    | run-umbrella-windows.py              |
| Target to benchmark                  | run-umbrella-windows.py              |
| Force field to benchmark             | run-umbrella-windows.py              |
| Files required by worker pod         | run-umbrella-windows.py              |
| Resources of each worker pod         | k8s_template.yaml                    |
| `proteinbenchmark` branch/commit/rev | k8s_template.yaml                    |

To rebuild the docker image according to the `Dockerfile` currently checked in to the `main` branch, run this workflow: [image rebuild]

[image rebuild]: https://github.com/openforcefield/proteinbenchmark-nrp/actions/workflows/rebuild-docker.yaml

## Accessing results

Results are stored in an S3 bucket provided by NRP. This includes all input and output files from the pod itself. The contents of this bucket are copied to the pod during initialization, and copied back to the bucket when a window is completed or the pod crashes. The `--update` switch is passed to RClone for this copy, so only files that have been changed on the pod should be copied, but I haven't tested this. This should eventually be fine tuned so that only the files necessary for a particular pod are copied.

To copy files from the bucket to your machine, first download the rclone config file:

```bash
kubectl get secret jm-rclone-config -o jsonpath='{.data.rclone\.conf}' | base64 --decode > ~/.config/rclone/rclone.conf
```

Then run a command like:

```bash
rclone copy --progress nrp:proteinbenchmark-jm-bucket/results results
```

To copy files from your machine to the bucket, only copying files that are missing from the bucket or are newer on your machine, do something like:

```bash
rclone copy --progress --update results nrp:proteinbenchmark-jm-bucket/results
```

To remove files from the bucket:

```bash
rclone delete --progress nrp:proteinbenchmark-jm-bucket/results/files/to/remove
```

RClone *should* work with globs/wildcards, just remember to escape them so your shell doesn't process them before passing the output on to RClone. You can escape strings in most shells by prefixing with a backslash or putting the entire path in single quotes.

S3 can also be set up to provide public HTTP access to files if that's preferable!

## Minutiae

### Providence

The actual Kubernetes manifest executed by NRP is stored in `results/$TARGET-$FF/replica-$REPLICA/$TARGET-$FF-$REPLICA-$WINDOW.yaml`. If this file already exists, `run-umbrella-windows.py` will refuse to overwrite it to avoid deleting providence of a previous run when `run-umbrella-windows.py` has not been updated correctly. The path, repository, and commit hash of the script used in this manifest are stored in the manifest YAML file, so combined with this Git repository this should be sufficient information to reproduce a run.

### CUDA version

The CUDA version is specified in three places. I don't know if all three have to be the same or how flexible this is, but here's where they are so you can find them:

1. `k8s_template.yaml`: This defines the CUDA version installed on the node our container will run on.
2. `Dockerfile` in two places:
  a. The first line, which defines the upstream docker image to base ours on
  b. The `RUN micromamba install ...` line, which augments the Conda environment to fix the CUDA version so that installed packages are compatible.

To see what versions of CUDA are available on NRP at the moment, take a look at the last two columns of the output of this command:

```bash
kubectl get nodes -L nvidia.com/gpu.product,nvidia.com/cuda.runtime.major,nvidia.com/cuda.runtime.minor -l nvidia.com/gpu.product
```

### Initialization containers and root

Our Docker image is based on the [Micromamba docker image]. This makes it very easy and fast to install packages and environments through Conda. Unfortunately, it also means that we don't have access to the root user in our main container. This is a bit of a pain because Kubernetes mounts all volumes as owned by root with 755/644 permissions (owner writes, group/other reads).

To get around this limitation, we perform a lot of initialization in other containers prior to spinning up the main container. Firstly, we clone this repository with the root-enabled `alpine/git` image in a container called `init-git`, and then we spin up `init-rclone` with the `rclone/rclone` image to download the results directory from S3 and set its permissions so that the Micromamba user can write to it. Once all the files are in place and properly permissioned, the `main` container with our custom image can take over.

There should be a way to do this [more elegantly], but I couldn't get it to work and the current strategy is... fine.

[Micromamba docker image]: https://micromamba-docker.readthedocs.io/en/latest/
[more elegantly]: https://stackoverflow.com/questions/43544370/kubernetes-how-to-set-volumemount-user-group-and-file-permissions

## Useful commands and links

Visualization of GPU utilisation: https://grafana.nrp-nautilus.io/d/dRG9q0Ymz/k8s-compute-resources-namespace-gpus?var-namespace=openforcefield&orgId=1&refresh=auto&from=now-1h&to=now

Visualization of CPU utilisation: https://grafana.nrp-nautilus.io/d/85a562078cdf77779eaa1add43ccec1e/kubernetes-compute-resources-namespace-pods?orgId=1&refresh=10s&var-datasource=default&var-cluster=&var-namespace=openforcefield

NRP Nautilus docs: https://docs.nrp.ai/

Useful commands:

```bash
# Get the status of an underway production simulation
kubectl exec job/pb-${INITIALS}-${TARGET}-${FF}-${REPLICA}-${WINDOW} -- cat /results/${TARGET}-${FF}/replica-${REPLICA}/window-${WINDOW}/${TARGET}-${FF}-production.out

# Get a shell into a pod
kubectl exec -it ${PODNAME} -- /bin/bash

# Get a shell into a job
kubectl exec -it job/${JOBNAME} -- /bin/bash

# View the logs (with timestamps) of a pod that just restarted, including its initialization containers
kubectl logs ${PODNAME} --previous --all-containers --timestamps
```
