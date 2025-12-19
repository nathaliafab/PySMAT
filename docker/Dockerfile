FROM python:3.11-slim

ARG USER_ID=1000
ARG GROUP_ID=1000

# Install system dependencies and create user
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        curl \
        jq \
        build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    groupadd -g ${GROUP_ID} appuser && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} appuser

WORKDIR /app

# Install Python dependencies
COPY SMAT/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt ruff mypy pytest

USER appuser
CMD ["/bin/bash", "-i"]