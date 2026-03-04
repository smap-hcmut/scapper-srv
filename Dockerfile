FROM python:3.12-slim

WORKDIR /app

# Install SDK first (copied from build context)
COPY sdk/ /tmp/sdk/
RUN pip install --no-cache-dir /tmp/sdk && rm -rf /tmp/sdk

# Install dependencies
COPY scapper-srv/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scapper-srv/ .

RUN mkdir -p output

EXPOSE 8105

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8105"]
