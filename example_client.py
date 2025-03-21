import requests
import json

# API endpoint
API_URL = "http://localhost:8000/run-command"

# Example: Run 'ls -la' command
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
    "working_directory": "test"  # Optional: run command from this subdirectory
}

# Send request to API
response = requests.post(API_URL, json=payload)

# Print response
print(f"Status code: {response.status_code}")
print(json.dumps(response.json(), indent=2))
