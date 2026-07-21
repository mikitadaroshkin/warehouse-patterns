# Minimal image that builds the star schema and prints the analytical query
# output. There is no long-running service here -- the container runs the demo
# once and exits, which is the whole point of a patterns write-up repo.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run the demo by default; override with `docker run ... pytest` to run tests.
CMD ["python", "build_demo.py"]
