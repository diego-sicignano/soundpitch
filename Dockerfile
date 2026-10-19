# One container serves the API and the page. Build from the repository root:
#   docker build -t soundpitch .
#   docker run -p 8000:8000 --env-file backend/.env soundpitch
FROM python:3.13-slim

WORKDIR /srv/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY frontend /srv/frontend

RUN useradd --system --no-create-home soundpitch
USER soundpitch
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
