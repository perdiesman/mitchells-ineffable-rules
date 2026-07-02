FROM python:3.12-slim

# Set workdir to /workspace. When running the container, users should
# mount their target code directory to /workspace.
WORKDIR /workspace

# Copy dependencies first to leverage caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy source code
COPY mir /app/mir

# Ensure /app is in the Python search path
ENV PYTHONPATH=/app

# Define the entrypoint to our linter script
ENTRYPOINT ["python", "/app/mir/main.py"]
