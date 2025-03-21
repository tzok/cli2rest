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

**Request Body:**

```json
{
  "cli_tool": "string", // The CLI tool to run
  "arguments": ["string"], // List of arguments to pass to the tool
  "files": [
    // Files to create before running the command
    {
      "relative_path": "string", // Path relative to the working directory
      "content": "string" // Content of the file
    }
  ],
  "working_directory": "string" // Optional: subdirectory to run the command from
}
```

**Response:**

```json
{
  "stdout": "string", // Standard output from the command
  "stderr": "string", // Standard error from the command
  "exit_code": 0, // Exit code from the command
  "command": "string" // The command that was executed
}
```

### Example

```python
import requests

API_URL = "http://localhost:8000/run-command"

payload = {
    "cli_tool": "ls",
    "arguments": ["-la"],
    "files": [
        {
            "relative_path": "test/example.txt",
            "content": "This is an example file content."
        },
        {
            "relative_path": "test/nested/another.txt",
            "content": "This is another file in a nested directory."
        }
    ],
    "working_directory": "test"
}

response = requests.post(API_URL, json=payload)
print(response.json())
```

## Building Custom Images

You can use this image as a base for custom CLI tool wrappers:

1. Create a new Dockerfile:

```dockerfile
FROM cli2rest:latest

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
