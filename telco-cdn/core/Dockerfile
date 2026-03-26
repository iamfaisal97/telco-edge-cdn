FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y iproute2 && rm -rf /var/lib/apt/lists/*
RUN pip install flask requests flask-cors
COPY app.py .
COPY setup_network.sh .
RUN chmod +x setup_network.sh
CMD ["./setup_network.sh"]