# Use a Python version compatible with pyproject.toml
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install Node.js and build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry system-wide using pip
RUN pip install --no-cache-dir poetry

# Disable virtualenv creation using environment variable
ENV POETRY_VIRTUALENVS_CREATE=false

# Copy Poetry project files first
COPY pyproject.toml poetry.lock ./

# Install dependencies using Poetry as root
RUN poetry install --no-root --only main

# Create a non-root user
RUN useradd -m appuser

# Create data directory (owned by root initially, ownership changed later)
RUN mkdir -p /app/data

# Copy the rest of the application code and sensitive files
COPY . .

# Build the frontend
RUN cd web && \
    npm install && \
    npm run build && \
    mkdir -p dist && \
    cp -r build/* dist/

# Set ownership for the app directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["python3", "main.py"]
