FROM apache/airflow:2.9.3

USER root

WORKDIR /opt/airflow

# dbt debug/deps requires the git executable for package resolution.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=airflow:root requirements.txt requirements-dbt.txt /opt/airflow/

USER airflow

# Keep the Airflow runtime on versions compatible with the base image.
RUN --mount=type=cache,target=/home/airflow/.cache/pip,uid=50000,gid=0 \
    pip install \
        --timeout 300 \
        --retries 10 \
        -r /opt/airflow/requirements.txt \
    && pip check

# dbt 1.11 needs newer protobuf/telemetry packages than Airflow 2.9.3.
# Install it in a separate environment so neither dependency set can corrupt
# the other. DAG dbt tasks call this executable explicitly.
RUN --mount=type=cache,target=/home/airflow/.cache/pip,uid=50000,gid=0 \
    python -m venv /home/airflow/dbt-venv \
    && /home/airflow/dbt-venv/bin/pip install \
        --timeout 300 \
        --retries 10 \
        -r /opt/airflow/requirements-dbt.txt \
    && /home/airflow/dbt-venv/bin/pip check
