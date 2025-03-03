FROM python:3.12-slim

# Install gcc and clean up the package lists to save space
RUN apt-get update && \
    apt-get install -y gcc && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip wheel setuptools
RUN pip install -r requirements.txt --timeout 120
COPY . .
CMD ["python", "main.py"]