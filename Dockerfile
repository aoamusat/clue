FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create instance directory for SQLite database
RUN mkdir -p instance

# Set environment variables
ENV FLASK_APP=main.py
ENV FLASK_ENV=production

# Expose port for the application
EXPOSE 5000

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app"]