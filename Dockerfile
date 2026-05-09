FROM python:3.12-slim

WORKDIR /app

# Install SDK wheel bundled in service directory
COPY scapper-srv/tinlikesub-*.whl /tmp/
RUN pip install --no-cache-dir /tmp/tinlikesub-*.whl && rm -f /tmp/tinlikesub-*.whl

# Install dependencies
COPY scapper-srv/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scapper-srv/ .

RUN mkdir -p output

EXPOSE 8105

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8105", "--log-level", "warning", "--no-access-log"]
