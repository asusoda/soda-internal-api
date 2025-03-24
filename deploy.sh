#!/bin/bash

echo "Opening the API directory"
cd /root/soda-internal-api || { echo "Failed to change directory. Exiting."; exit 1; }

echo "Pulling the latest changes from the repository"
git pull

echo "Checking out the main branch"
git checkout main

echo "Building the Docker image for soda-internal-api"
docker build -t soda-internal-api .

echo "Stopping any existing container with the same name if it exists"
docker stop soda-internal-api || true
docker rm soda-internal-api || true

echo "Running the Docker container"
docker run -d \
  --name soda-internal-api \
  -p 8000:8000 \
  -v /root/soda-internal-api/data:/app/data \
  soda-internal-api

echo "Deployment completed using Docker."
