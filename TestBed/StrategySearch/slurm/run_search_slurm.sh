CONFIG="$1"
NUM_WORKERS="$2"
PARAM="$3"
DRY_RUN=""
if [ "$PARAM" = "DRY_RUN" ]; then
	echo "Using DRY RUN"
	DRY_RUN="1"
fi

DATE="$(date +'%Y-%m-%d_%H-%M-%S')"
LOGDIR="./slurm/logs/slurm_${DATE}"
echo "SLURM Log directory: ${LOGDIR}"
mkdir -p "$LOGDIR"
SEARCH_SCRIPT="$LOGDIR/search.slurm"
SEARCH_OUT="$LOGDIR/slurm-search-%j.out"

# Submit Search script.
echo "\
#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --job-name=Search
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=2GB
#SBATCH --tasks-per-node=1
#SBATCH --time=30:00:00
#SBATCH --account=nikolaid_548
#SBATCH --output $SEARCH_OUT
#SBATCH --error $SEARCH_OUT

echo \"========== SLURM JOB INFO ==========\"
echo
echo \"The job will be started on the following node(s):\"
echo $SLURM_JOB_NODELIST
echo
echo \"Slurm User:         $SLURM_JOB_USER\"
echo \"Run Directory:      $(pwd)\"
echo \"Job ID:             $SLURM_JOB_ID\"
echo \"Job Name:           $SLURM_JOB_NAME\"
echo \"Partition:          $SLURM_JOB_PARTITION\"
echo \"Number of nodes:    $SLURM_JOB_NUM_NODES\"
echo \"Number of tasks:    $SLURM_NTASKS\"
echo \"Submitted From:     $SLURM_SUBMIT_HOST\"
echo \"Submit directory:   $SLURM_SUBMIT_DIR\"
echo \"Hostname:           $(hostname)\"
echo
echo \"Dashboard Host:     |$(hostname):8787|\"
echo

echo
echo \"========== Start ==========\"
date

echo
echo \"========== Setup ==========\"


echo
echo \"========== Starting Singularity .NET script ==========\"
singularity exec --cleanenv singularity/ubuntu_dotnet dotnet bin/StrategySearch.dll $CONFIG

echo
echo \"========== Done ==========\"
date" >"$SEARCH_SCRIPT"
if [ -z "$DRY_RUN" ]; then sbatch "$SEARCH_SCRIPT"; fi

echo "Waiting for search to start..."
if [ -z "$DRY_RUN" ]; then
	SEARCH_ACTIVE_FILE="active/search.txt"
	# Wait for scheduler to start.
	while [ ! -e $SEARCH_ACTIVE_FILE ]; do
		sleep 1
	done
fi

# Submit worker scripts.
mkdir -p "$LOGDIR/worker_logs"
mkdir -p "$LOGDIR/worker_scripts"
for ((worker_id = 0; worker_id < $NUM_WORKERS; worker_id++)); do
	WORKER_SCRIPT="$LOGDIR/worker_scripts/worker-$worker_id.slurm"
	WORKER_OUT="$LOGDIR/worker_logs/slurm-worker-$worker_id-%j.out"

	echo "\
#!/bin/bash

#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --job-name=Evaluator
#SBATCH --cpus-per-task=2
#SBATCH --mem-per-cpu=1GB
#SBATCH --tasks-per-node=1
#SBATCH --time=30:00:00
#SBATCH --account=nikolaid_548
#SBATCH --output $WORKER_OUT
#SBATCH --error $WORKER_OUT

echo \"========== SLURM JOB INFO ==========\"
echo
echo \"The job will be started on the following node(s):\"
echo $SLURM_JOB_NODELIST
echo
echo \"Slurm User:         $SLURM_JOB_USER\"
echo \"Run Directory:      $(pwd)\"
echo \"Job ID:             $SLURM_JOB_ID\"
echo \"Job Name:           $SLURM_JOB_NAME\"
echo \"Partition:          $SLURM_JOB_PARTITION\"
echo \"Number of nodes:    $SLURM_JOB_NUM_NODES\"
echo \"Number of tasks:    $SLURM_NTASKS\"
echo \"Submitted From:     $SLURM_SUBMIT_HOST\"
echo \"Submit directory:   $SLURM_SUBMIT_DIR\"
echo \"Hostname:           $(hostname)\"
echo
echo \"Dashboard Host:     |$(hostname):8787|\"
echo

echo
echo \"========== Start ==========\"
date

echo
echo \"========== Setup ==========\"


echo
echo \"========== Starting Singularity .NET script ==========\"
singularity exec --cleanenv singularity/ubuntu_dotnet dotnet bin/DeckEvaluator.dll $worker_id

echo
echo \"========== Done ==========\"
date" >"$WORKER_SCRIPT"
	if [ -z "$DRY_RUN" ]; then sbatch "$WORKER_SCRIPT"; fi
	sleep 0.2
done
