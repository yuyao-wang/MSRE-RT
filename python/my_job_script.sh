#!/bin/bash
#SBATCH --job-name=my_cpu_job          # Job name
#SBATCH --output=output_%j.txt         # Standard output and error log
#SBATCH --error=error_%j.txt           # Error log
#SBATCH --ntasks=1                     # Run on a single CPU
#SBATCH --cpus-per-task=4              # Number of CPU cores per task (adjust this as needed)
#SBATCH --time=24:00:00                # Time limit hrs:min:sec
#SBATCH --mem=16G                      # Memory limit (adjust this based on your needs)

# Activate your conda environment
# source ~/miniconda3/etc/profile.d/conda.sh
# conda activate compatible_env

# Run the Python reference model
cd "$(dirname "$0")"
python main.py
