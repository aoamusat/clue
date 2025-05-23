FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy the entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create instance directory for SQLite database
RUN mkdir -p instance

ENV FLASK_APP=subly
ENV FLASK_ENV=production

EXPOSE 5000

# Use the entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
