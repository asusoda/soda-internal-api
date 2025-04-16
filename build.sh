#!/bin/bash

# Build the frontend
echo "Building frontend..."
cd web
npm install
npm run build

# Create dist directory if it doesn't exist
mkdir -p dist

# Copy built files to dist directory
cp -r build/* dist/

echo "Frontend build complete!" 