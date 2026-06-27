FROM python:3.11-slim

WORKDIR /app

# Copy requirements relative to root build context
COPY backend/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source directories
COPY backend/ ./backend
COPY agents/ ./agents
COPY prompts/ ./prompts
COPY knowledge_base/ ./knowledge_base
COPY observability/ ./observability

ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Start command
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
