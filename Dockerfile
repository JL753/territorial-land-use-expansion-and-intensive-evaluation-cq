FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 DJANGO_DEBUG=0
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=secret,id=pip_ca \
    if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi \
    && pip install --no-cache-dir -r requirements.txt
COPY manage.py audit_landcover.py serve.py ./
COPY cqsite cqsite
COPY study study
COPY web web
COPY results results
RUN useradd --create-home --uid 10001 study && chown -R study:study /app
USER study
# Use a throwaway build-time key for collectstatic/migrations. A real key is required at runtime.
RUN export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" \
    && python manage.py migrate --noinput \
    && python manage.py import_study \
    && python manage.py collectstatic --noinput
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)" || exit 1
CMD ["gunicorn", "cqsite.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
