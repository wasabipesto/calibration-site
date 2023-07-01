FROM python:3-alpine

ENV TZ="America/New_York"
ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/manifold

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY templates/* templates/
COPY app.py .

CMD ["python","app.py"]
