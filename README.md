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

- `cli_tool` (string): The CLI tool to run
- `arguments` (string): JSON array of arguments to pass to the tool
- `output_files` (string): JSON array of relative paths to return after execution
- `input_files` (files): Multiple file uploads with filenames as relative paths

**Response:**

```json
{
  "stdout": "string", // Standard output from the command
  "stderr": "string", // Standard error from the command
  "exit_code": 0, // Exit code from the command
  "command": "string", // The command that was executed
  "output_files": [
    {
      "relative_path": "string", // Path relative to the working directory
      "content_base64": "string" // Base64-encoded content of the file
    }
  ]
}
```

### Example

```python
import requests
import json
import os
import base64

API_URL = "http://localhost:8000/run-command"

# Prepare files to upload
files = [
    ('input_files', ('test/example.txt', open('example.txt', 'rb'), 'text/plain')),
    ('input_files', ('test/nested/another.txt', open('another.txt', 'rb'), 'text/plain'))
]

# Prepare form data
data = {
    'cli_tool': 'ls',
    'arguments': json.dumps(['-la']),
    'output_files': json.dumps(['test/output.txt'])
}

# Send request to API
response = requests.post(API_URL, data=data, files=files)

# Process response
result = response.json()
print(f"Command: {result['command']}")
print(f"Exit code: {result['exit_code']}")
print(f"Stdout: {result['stdout']}")

# Process output files
for file_data in result['output_files']:
    file_path = file_data['relative_path']
    content = base64.b64decode(file_data['content_base64']).decode('utf-8')
    print(f"Output file {file_path}: {content}")
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

## Security Considerations

- This API allows execution of arbitrary commands, so it should be deployed with appropriate security measures.
- Consider running in an isolated environment.
- Add authentication and authorization to the API in production.
- Limit the commands that can be executed based on your use case.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
