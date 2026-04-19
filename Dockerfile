FROM python:3.11-slim

# Install git and curl
RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the rest of the code
COPY . .

# Configure git user
RUN git config --global user.email "greg@gregasi.com" && git config --global user.name "GregASI"

RUN pip install --no-cache-dir -r requirements.txt

CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4"]