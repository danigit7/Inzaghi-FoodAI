# --- Stage 1: Build Frontend ---
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# Copy frontend dependency files
COPY frontend/package.json ./

# Install dependencies (use npm install to allow missing lockfile)
RUN npm install

# Copy the rest of the frontend source code
COPY frontend/ .

# Build the React app
RUN npm run build

# --- Stage 2: Setup Backend ---
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y gcc && apt-get clean

WORKDIR /app

# Copy backend requirements
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Copy built frontend from Stage 1 to /app/static
COPY --from=frontend-builder /frontend/dist ./static

# Expose port
EXPOSE 7860

# Run uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
