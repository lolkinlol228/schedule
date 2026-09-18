FROM node:24-bookworm-slim AS ui
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json vite.config.ts index.html components.json ./
COPY src ./src
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir 'pip>=26.2.1' && pip install --no-cache-dir -r requirements.lock.txt
COPY backend ./backend
COPY --from=ui /app/dist ./dist
RUN useradd --create-home school && mkdir /app/data && chown school:school /app/data
USER school
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
