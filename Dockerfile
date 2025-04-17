# Base image with Python + Chromium + ChromeDriver pre-installed
FROM zenika/python-chrome:latest

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full project
COPY . .

# Expose port for Railway
EXPOSE 8080

# Command to run your bot
CMD ["python", "sbpdcl_bot.py"]
