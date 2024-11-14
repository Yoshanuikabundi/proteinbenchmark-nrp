#!/bin/bash

source ~/.bashrc
ulimit -s unlimited

SCRIPT_DIR=/data/ucsd/gilsonlab/ccavender/protein-ff/benchmarks/gb3-native-contacts
RESULT_DIR=${SCRIPT_DIR}/results
TARGET=gb3
FF=null-0.0.3-pair-nmr-1e4-opc3
TARGET_DIR=$RESULT_DIR/${TARGET}-${FF}

for REPLICA in 1 2 3; do
    for WINDOW in $(seq 0 30); do

        WINDOW_STR=$(printf "%02d" "$WINDOW")
        REPLICA_DIR=$TARGET_DIR/replica-${REPLICA}
        WINDOW_DIR=$REPLICA_DIR/window-${WINDOW_STR}
        SLURM_SCRIPT=${TARGET}-${FF}-${REPLICA}-${WINDOW_STR}.sbatch

        cd $REPLICA_DIR

        cat > $SLURM_SCRIPT << EOF
#!/bin/bash
#SBATCH -J $TARGET-$FF-$REPLICA-${WINDOW_STR}
#SBATCH -p 168h
#SBATCH -c 4
#SBATCH --gres=gpu:1
#SBATCH -t 48:00:00
#SBATCH --mem=4GB

source \$HOME/.bashrc
ulimit -s unlimited
conda activate openff-proteinbenchmark

echo \$(hostname) \$CUDA_VISIBLE_DEVICES

python $SCRIPT_DIR/run-umbrella-window.py \\
    -f $FF -t $TARGET -r $REPLICA -w $WINDOW -o $RESULT_DIR

EOF

        sbatch -o %x-%j.out -e %x-%j.err $SLURM_SCRIPT

    done
done

