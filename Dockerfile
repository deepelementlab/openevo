FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e .
ENV OPENEVO_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "openevo.api.server:app", "--host", "0.0.0.0", "--port", "8765"]
