import requests
import json
import os
import base64
import tempfile

# API endpoint
API_URL = "http://localhost:8000/run-command"

# Create temporary files for the example
with tempfile.TemporaryDirectory() as temp_dir:
    # Create example files
    example_file_path = os.path.join(temp_dir, "example.txt")
    with open(example_file_path, "w") as f:
        f.write("This is an example file content.")

    nested_dir = os.path.join(temp_dir, "nested")
    os.makedirs(nested_dir, exist_ok=True)

    another_file_path = os.path.join(nested_dir, "another.txt")
    with open(another_file_path, "w") as f:
        f.write("This is another file in a nested directory.")

    # Prepare multipart form data
    files = [
        (
            "input_files",
            ("test/example.txt", open(example_file_path, "rb"), "text/plain"),
        ),
        (
            "input_files",
            ("test/nested/another.txt", open(another_file_path, "rb"), "text/plain"),
        ),
    ]

    data = {
        "cli_tool": "ls",
        "arguments": json.dumps(["-la"]),
        "output_files": json.dumps([]),  # No output files requested in this example
    }

    # Send request to API
    response = requests.post(API_URL, data=data, files=files)

    # Print response
    print(f"Status code: {response.status_code}")
    response_data = response.json()
    print(json.dumps(response_data, indent=2))

    # Process any output files if present
    if "output_files" in response_data and response_data["output_files"]:
        print("\nOutput files:")
        for file_data in response_data["output_files"]:
            print(f"File: {file_data['relative_path']}")
            content = base64.b64decode(file_data["content_base64"]).decode("utf-8")
            print(f"Content: {content[:100]}{'...' if len(content) > 100 else ''}")
