#!bin/bash

echo "Opening the API directory"
cd /root/soda-internal-api

echo "Stashing any local changes"
git stash

echo "Pulling the latest changes from the repository"
git pull

git checkout main