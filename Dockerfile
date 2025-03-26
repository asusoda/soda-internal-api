FROM python:3.8-slim-buster

# Set the working directory
WORKDIR /app

# Create appuser
RUN useradd -m appuser

# Create data directory
RUN mkdir -p /app/data

# Copy environment files first
COPY .env .env
COPY google-secret.json google-secret.json
RUN chown appuser:appuser .env google-secret.json

# Install dependencies
COPY requirements.txt .
RUN pip3 install --upgrade pip && \
    pip3 install -r requirements.txt

# Copy application code
COPY . .

# Create entrypoint script as root
RUN echo '#!/bin/bash\n\
chown -R appuser:appuser /app/data\n\
chmod -R 755 /app/data\n\
exec "$@"' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

# Set ownership of application files
RUN chown -R appuser:appuser /app

# Switch to appuser
USER appuser

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Run the application
CMD ["python3", "main.py"]
