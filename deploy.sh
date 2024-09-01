#!/bin/bash

# Check if the environment exists
if conda env list | grep -q "\bsoda\b"; then
    echo "Conda environment 'soda' already exists."
else
    echo "Creating the Conda environment from environment.yml"
    conda env create -f environment.yml
fi

echo "Updating system packages and installing chromium-chromedriver"
sudo apt update
sudo apt install -y chromium-chromedriver

echo "Ensuring Conda is available in the shell"
source ~/anaconda3/etc/profile.d/conda.sh

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
