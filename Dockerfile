FROM python:3.8-slim-buster

# Set the working directory
WORKDIR /app

# Create a non-root user
RUN useradd -m appuser

# Create data directory
RUN mkdir -p /app/data

# Copy sensitive files first and set permissions
COPY .env .env
COPY google-secret.json google-secret.json
RUN chown appuser:appuser .env google-secret.json

# Switch to non-root user
USER appuser

# Add local bin to PATH for the non-root user
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Copy requirements file to the working directory
COPY requirements.txt .

# Upgrade pip and install dependencies as non-root user
RUN pip3 install --upgrade pip && \
    pip3 install -r requirements.txt

# Copy the rest of the application code to the working directory
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["python3", "main.py"]
