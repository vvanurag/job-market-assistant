# Airflow with the project installed in its own virtual environment (NFR-23).
FROM apache/airflow:3.3.2-python3.12

USER root
RUN python -m venv /opt/jobmarket-venv && chown -R airflow: /opt/jobmarket-venv
USER airflow

# Install the project's dependencies; the source itself is mounted at /opt/jobmarket
COPY --chown=airflow:root pyproject.toml README.md /opt/jobmarket/
COPY --chown=airflow:root src /opt/jobmarket/src
RUN /opt/jobmarket-venv/bin/pip install --no-cache-dir -e "/opt/jobmarket[transform]"
