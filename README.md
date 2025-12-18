# CLI2REST

A FastAPI wrapper that allows running any CLI tool through a REST API. This service creates a temporary environment with the specified files and executes the requested command, returning the output.

## Features

- Run any CLI tool via REST API
- Create temporary file structures on-the-fly
- Specify working directory for command execution
- Get stdout, stderr, and exit code in the response

## Getting Started

### Prerequisites

- Docker
- Python 3.8+ (for local development)

### Using the Pre-built Image

Pull the image from GitHub Container Registry:

```bash
docker pull ghcr.io/tzok/cli2rest:latest
```

Run the container:

```bash
docker run -p 8000:8000 ghcr.io/tzok/cli2rest:latest
```

### Building the Docker Image Locally

Build the Docker image with:

```bash
docker build -t cli2rest .
```

### Running the Container

Run the container with:

```bash
docker run -p 8000:8000 cli2rest
```

The API will be available at http://localhost:8000.

## API Usage

### Run Command Endpoint

**Endpoint:** `POST /run-command`

**Request Format:** `multipart/form-data`

**Form Fields:**

- `arguments` (list): List of strings representing the command and its arguments
- `input_files` (files): Multiple file uploads with filenames as relative paths
- `output_files` (list): List of relative paths to return after execution

**Response:**

The response is a `multipart/form-data` stream. The first part is a JSON object containing execution metadata, followed by any requested output files as separate binary parts.

**Metadata JSON structure:**
```json
{
  "status": "COMPLETED",
  "exit_code": 0,
  "stdout": "string",
  "stderr": "string",
  "command": ["list", "of", "args"],
  "missing_files": [],
  "execution_stats": {
    "start_time": "2025-12-18T12:00:00+00:00",
    "end_time": "2025-12-18T12:00:00.123000+00:00",
    "duration_seconds": 0.123,
    "max_rss_kb": 4567,
    "cpu_user_seconds": 0.05
  }
}
```

### Example

```python
import requests
import json
from email import message_from_bytes

API_URL = "http://localhost:8000/run-command"

# Prepare files and data
files = [('input_files', ('hello.txt', b'Hello World!'))]
data = {
    'arguments': ['cat', 'hello.txt'],
    'output_files': ['hello.txt']
}

# Send request
response = requests.post(API_URL, data=data, files=files)

if response.status_code == 200:
    # Parse multipart response
    raw_message = f"Content-Type: {response.headers.get('Content-Type')}\r\n\r\n".encode() + response.content
    msg = message_from_bytes(raw_message)

    for part in msg.walk():
        disposition = part.get("Content-Disposition", "")
        if 'name="metadata"' in disposition:
            print("Metadata:", json.loads(part.get_payload(decode=True)))
        elif "filename=" in disposition:
            filename = part.get_filename()
            content = part.get_payload(decode=True)
            print(f"Received file: {filename} ({len(content)} bytes)")
```

## Building Custom Images

You can use this image as a base for custom CLI tool wrappers:

1. Create a new Dockerfile:

```dockerfile
FROM ghcr.io/tzok/cli2rest:latest

# Install additional tools
RUN apt-get update && apt-get install -y \
    your-tool-package \
    another-tool-package \
    && rm -rf /var/lib/apt/lists/*

# Add any custom configuration
COPY custom-config.json /app/

# You can also override the default command if needed
# CMD ["uvicorn", "custom_app:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. Build your custom image:

```bash
docker build -t custom-cli2rest .
```

3. Run your custom image:

```bash
docker run -p 8000:8000 custom-cli2rest
```

**Note:** The base image includes the `requests` library. This allows for convenient healthchecks in Docker Compose, for example:
```yaml
healthcheck:
  test: ["CMD-SHELL", "python -c \"import requests; requests.get('http://localhost:8000/health').raise_for_status()\" || exit 1"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## Security Considerations

- This API allows execution of arbitrary commands, so it should be deployed with appropriate security measures.
- Consider running in an isolated environment.
- Add authentication and authorization to the API in production.
- Limit the commands that can be executed based on your use case.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
