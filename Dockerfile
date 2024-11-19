FROM mambaorg/micromamba:2-cuda12.2.2-ubuntu22.04

ARG BRANCH=nagl
ARG REPO=openforcefield/proteinbenchmark
ARG ENV_PATH=devtools/conda-envs/proteinbenchmark-simulation.yaml
# ARG ENV_PATH=devtools/conda-envs/proteinbenchmark.yaml

USER root
RUN apt-get update && apt-get install -y rclone git gcc
USER $MAMBA_USER

ADD --chown=$MAMBA_USER:$MAMBA_USER \
    https://github.com/$REPO/raw/refs/heads/$BRANCH/$ENV_PATH \
    /tmp/env.yaml

RUN micromamba install -y -n base click openff-nagl 'python<3.12' -f /tmp/env.yaml &&\
    micromamba clean --all --yes &&\
    micromamba list

ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN pip install git+https://github.com/${REPO}.git@${BRANCH}
