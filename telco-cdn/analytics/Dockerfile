FROM python:3.11-slim
WORKDIR /app
RUN pip install flask requests redis pandas scikit-learn numpy
COPY . .
CMD ["python", "app.py"]