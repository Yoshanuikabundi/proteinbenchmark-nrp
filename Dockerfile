FROM mambaorg/micromamba:2-alpine3.20

ARG BRANCH=nagl
ARG REPO=openforcefield/proteinbenchmark
ARG ENV_PATH=devtools/conda-envs/proteinbenchmark.yaml

ADD --chown=$MAMBA_USER:$MAMBA_USER \
    https://github.com/$REPO/raw/refs/heads/$BRANCH/$ENV_PATH \
    /tmp/env.yaml
RUN micromamba install -y -n base -f /tmp/env.yaml &&\
    pip install git+https://github.com/$REPO.git@$BRANCH &&\
    micromamba clean --all --yes
