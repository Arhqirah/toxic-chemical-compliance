FROM python:3.12-slim

WORKDIR /app

# Install dependencies first, so Docker can cache this layer
# and skip it when only the code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Don't run as root inside the container
RUN useradd --create-home appuser
USER appuser

EXPOSE 5000

# Production server. In development, docker-compose.yml overrides this
# with Flask's debug server.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
