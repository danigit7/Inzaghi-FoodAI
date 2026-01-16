# Use official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the backend directory contents into the container at /app/backend
COPY backend/ ./backend/

# Upgrade pip to ensure latest version
RUN pip install --upgrade pip

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Set environment variable for port (default to 8000 if not set)
ENV PORT=8000

# Run uvicorn when the container launches
CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT"]
