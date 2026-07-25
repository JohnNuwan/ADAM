FROM python:3.12-slim
WORKDIR /app
RUN mkdir -p /data
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY server.py models.py eva-bridge.py start.sh ./
COPY static/ static/
COPY templates/ templates/
EXPOSE 8085
CMD ["python", "server.py", "--port", "8085"]
