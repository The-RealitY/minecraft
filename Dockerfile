# Use a Python 3.10 Alpine-based image as the base image
FROM python:3.10-alpine

# Set the working directory inside the container
WORKDIR /app

# Install dependencies for building and other packages, and remove after installing
RUN apk add --no-cache --virtual .build-deps gcc libpq-dev musl-dev && apk del .build-deps

# Copy the necessary files to the container
COPY ./mc_backup /app/mc_backup
COPY credentials.json /app
COPY token.json /app
COPY requirements.txt /app

# Run Backup API Server Requirements
RUN pip install --no-cache-dir -r requirements.txt

# Run the FastAPI application using Uvicorn
CMD ["python3", "-m", "mc_backup"]
