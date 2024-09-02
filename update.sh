#!/bin/bash

echo "Opening the API directory"
cd /root/soda-internal-api || { echo "Failed to change directory. Exiting."; exit 1; }

echo "Stashing any local changes"
git stash

echo "Pulling the latest changes from the repository"
git pull

echo "Checking out the main branch"
git checkout main

echo "Restarting the daemon process for soda-api.service"
sudo systemctl restart soda-api.service

echo "Daemon process restarted successfully."
