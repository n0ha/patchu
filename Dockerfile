# Use an official Python runtime as a base image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the application files into the container
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir flask pillow reportlab

# Expose the Flask app's port
EXPOSE 5000

# Set the command to run the Flask app
CMD ["python", "app.py"]
