# Use official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies and Node.js
RUN apt-get update && apt-get install -y curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean

# Set the working directory in the container
WORKDIR /app

# Copy the frontend directory
COPY frontend/ ./frontend/

# Build the Frontend
RUN cd frontend && npm install && npm run build

# Copy the backend directory contents into the container at /app/backend
COPY backend/ ./backend/

# Upgrade pip to ensure latest version
RUN pip install --upgrade pip

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Set environment variable for port (default to 7860 for Hugging Face Spaces)
ENV PORT=7860

# Run uvicorn when the container launches
CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT"]
