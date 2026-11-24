# Análise de mineração de processos (executada sob demanda).
FROM docker.io/library/python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends graphviz \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 agrosmart
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip setuptools && pip install -r requirements.txt
COPY analise_processo.py .
USER agrosmart
CMD ["python", "analise_processo.py"]
