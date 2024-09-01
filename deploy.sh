#!/bin/bash

# Ensure Conda is available in the shell
echo "Ensuring Conda is available in the shell"
source /root/miniconda3/etc/profile.d/conda.sh

# Check if the environment exists and delete it if it does
if conda env list | grep -q "\bsoda\b"; then
    echo "Conda environment 'soda' already exists. Deleting it."
    conda env remove -n soda --yes  # Automatically agree to delete
else
    echo "Conda environment 'soda' does not exist. Proceeding to create it."
fi

echo "Creating the Conda environment from environment.yml"
conda env create -f environment.yml

echo "Updating system packages and installing chromium-chromedriver"
sudo apt update
sudo apt install -y chromium-chromedriver

echo "Activating conda environment"
conda activate soda

# Check if the environment was activated successfully
if [[ "$CONDA_DEFAULT_ENV" != "soda" ]]; then
    echo "Failed to activate the Conda environment 'soda'. Exiting."
    exit 1
fi

echo "Updating pip and installing dependencies"
pip install --upgrade pip  # Conda environment will use the correct version of pip
pip install -r requirements.txt  # Install dependencies listed in requirements.txt

echo "Deploying using gunicorn"
gunicorn --bind 0.0.0.0:8000 main:app  # Update "main:app" to match your entry point
