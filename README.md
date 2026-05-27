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
- [uv](https://docs.astral.sh/uv/)
- Python 3.10+ (for local development)

### Using the Pre-built Image

The default published image is based on **Python 3.13**.

Pull the image from GitHub Container Registry:

```bash
docker pull ghcr.io/tzok/cli2rest:latest
```

Run the container:

```bash
docker run -p 8000:8000 ghcr.io/tzok/cli2rest:latest
```

Explicit Python variants are also published:

```bash
docker pull ghcr.io/tzok/cli2rest:py3.10
docker pull ghcr.io/tzok/cli2rest:py3.11
docker pull ghcr.io/tzok/cli2rest:py3.12
docker pull ghcr.io/tzok/cli2rest:py3.13
docker pull ghcr.io/tzok/cli2rest:py3.14
```

Versioned release tags are also published on versioned releases:

```bash
docker pull ghcr.io/tzok/cli2rest:1.2.3
docker pull ghcr.io/tzok/cli2rest:1.2.3-py3.10
docker pull ghcr.io/tzok/cli2rest:1.2.3-py3.11
docker pull ghcr.io/tzok/cli2rest:1.2.3-py3.12
docker pull ghcr.io/tzok/cli2rest:1.2.3-py3.13
docker pull ghcr.io/tzok/cli2rest:1.2.3-py3.14
```

### Building the Docker Image Locally

Build the default image (Python 3.13):

```bash
docker build -t cli2rest .
```

Build an image for a different Python version:

```bash
docker build \
  --build-arg UV_BASE_IMAGE=ghcr.io/astral-sh/uv:python3.12-trixie-slim \
  -t cli2rest:py3.12 .
```

### Running the Container

Run the container with:

```bash
docker run -p 8000:8000 cli2rest
```

The API will be available at http://localhost:8000.

## Local Development

Install dependencies and run the server:

```bash
uv sync --locked
uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

Run with auto-reload:

```bash
uv run uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Run the integration test (requires a running server on port 8000):

```bash
uv run example_client.py
ls output_output.txt  # should exist after successful run
```

Manage dependencies:

```bash
uv add <package>
uv remove <package>
uv lock --upgrade-package <package>
```

## API Usage

### Run Command Endpoint

**Endpoint:** `POST /run-command`

**Request Format:** `multipart/form-data`

**Form Fields:**

- `arguments` (list): List of strings representing the command and its arguments
- `input_files` (files): Multiple file uploads with filenames as relative paths
- `output_files` (list): List of relative paths to return after execution
- `timeout` (number, optional): Maximum command runtime in seconds

**Response:**

The response is a `multipart/form-data` stream. The first part is a JSON object containing execution metadata, followed by any requested output files as separate binary parts.

If a command exceeds `timeout`, the metadata part reports `status` as `TIMEOUT` and `exit_code` as `null`.

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

### Example With Timeout

Use the `timeout` form field to stop long-running commands:

```bash
curl -X POST http://localhost:8000/run-command \
  -F 'arguments=bash' \
  -F 'arguments=-lc' \
  -F 'arguments=sleep 10; echo done' \
  -F 'timeout=2'
```

The response format is unchanged. Check the `metadata` part of the multipart response for the `TIMEOUT` status.

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

**Note:** The base image does not include the `requests` library. For healthchecks, use the Python standard library:

```yaml
healthcheck:
  test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\" || exit 1"]
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
