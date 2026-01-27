# Stage 1: Build the React Frontend
FROM node:18 as build-step
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Serve with FastAPI
FROM python:3.10-slim
WORKDIR /app

# Copy backend requirements and install
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy Backend Code
COPY backend/ ./backend/
RUN mkdir -p backend/data/sessions && chmod -R 777 backend/data/sessions

# Copy Built Frontend Assets from Stage 1
# Vite defaults output to dist, but your config said ../backend/static
# Let's trust the vite.config.js output setting or move it manually.
# In the previous step, we saw vite.config.js outputting to '../backend/static'.
# So 'npm run build' inside /app/frontend should put files in /app/backend/static.
# Let's verify where it ended up.
# Since we are copying the "result" from stage 1, we rely on the file structure.
COPY --from=build-step /app/backend/static ./backend/static

ENV PORT=7860
CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT"]
