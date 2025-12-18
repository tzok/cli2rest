import json
import os
import tempfile

import requests
from requests_toolbelt.multipart import decoder

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
        "arguments": ["ls", "-la"],
        "output_files": [],  # No output files requested in this example
    }

    # Send request to API
    response = requests.post(API_URL, data=data, files=files)
    # Note: This is correct - 'data' is the parameter name for form fields in requests
    # and 'files' is the parameter for file uploads. These are requests library parameters,
    # not the FastAPI endpoint parameter names.

    # Print response
    print(f"Status code: {response.status_code}")

    if response.status_code == 200:
        # Decode the multipart response
        multipart_data = decoder.MultipartDecoder.from_response(response)

        for part in multipart_data.parts:
            # Check the headers of each part
            disposition = part.headers.get(b"Content-Disposition", b"").decode()

            if 'name="metadata"' in disposition:
                metadata = json.loads(part.text)
                print("Metadata received:")
                print(json.dumps(metadata, indent=2))

            elif "filename=" in disposition:
                # Extract filename from header
                filename = disposition.split("filename=")[-1].strip('"')
                print(f"Received file: {filename} ({len(part.content)} bytes)")

                # Save the file to the current directory or a specific path
                output_path = os.path.join(temp_dir, f"output_{filename}")
                with open(output_path, "wb") as f:
                    f.write(part.content)
                print(f"Saved to: {output_path}")
    else:
        print(f"Error: {response.text}")
