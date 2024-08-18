FROM python:3.8-slim-buster

# Set the working directory
WORKDIR /app

# Copy requirements file to the working directory
COPY requirements.txt .

# Install dependencies
RUN pip3 install -r requirements.txt

# Copy the rest of the application code to the working directory
COPY . .

# Run the application
CMD ["python3", "main.py"]
