# Use a Python version compatible with pyproject.toml
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install build tools needed for some Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry system-wide using pip
RUN pip install --no-cache-dir poetry

# Disable virtualenv creation using environment variable
ENV POETRY_VIRTUALENVS_CREATE=false

# Copy Poetry project files first
COPY pyproject.toml poetry.lock ./

# Install dependencies using Poetry as root
# --no-root: Don't install the project itself (since package-mode=false)
# --only main: Install only main dependencies (not dev)
RUN poetry install --no-root --only main

# Create a non-root user
RUN useradd -m appuser

# Create data directory (owned by root initially, ownership changed later)
RUN mkdir -p /app/data

# Copy the rest of the application code and sensitive files
COPY . .

# Set ownership for the app directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["python3", "main.py"]
