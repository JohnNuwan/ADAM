FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY server.py .
COPY static/ static/
COPY templates/ templates/
EXPOSE 8084
CMD ["python", "server.py"]

