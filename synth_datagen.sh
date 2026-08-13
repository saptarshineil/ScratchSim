#!/bin/bash
#SBATCH --job-name=daytona_defect_datagen
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-gpu=64
#SBATCH --mem=128G
#SBATCH --time=10-00
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --export=DSNAME=daytona_custom-test_run,FRAMES=3,RUNS=5,RES=2048

DATAPATH=/opt/cache/$USER

OUTPATH=$DATAPATH/$DSNAME

rm -rf $OUTPATH

mkdir -p $OUTPATH/output
mkdir -p $OUTPATH/masks

WORKSPACE=$PWD/SratchSim

### This is a sample docker script. Please adpat and put data like cctexture in the correct path to get it working 
## MAIN

#docker build -t <name_of_docker_image> .
rootless-docker run --rm \
    --gpus all \
    --shm-size=20g \
    -v $WORKSPACE:/workspace \
    -v $DATAPATH/cctextures:/cctextures \
    -v $OUTPATH/output:/output \
    -v $OUTPATH/masks:/masks \
    <name_of_docker_image> \
    bash -c "blenderproc run /workspace/createScene.py \
               --blend_file='/workspace/Objects/daytona.blend' \
               --cc_material_path='/cctextures' \
               --runs=$RUNS \
               --frames=$FRAMES \
               --length=$LENGTH\
               "
