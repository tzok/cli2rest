import os
import shutil
import subprocess
import tempfile
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="CLI Tool Wrapper API")


class FileData(BaseModel):
    """Model for file data with relative path and content."""

    relative_path: str
    content: str


class CommandRequest(BaseModel):
    """Model for command request with CLI tool, arguments and files."""

    cli_tool: str
    arguments: List[str] = []
    files: List[FileData] = []
    working_directory: Optional[str] = None


class CommandResponse(BaseModel):
    """Model for command response with stdout, stderr and exit code."""

    stdout: str
    stderr: str
    exit_code: int
    command: str


@app.post("/run-command", response_model=CommandResponse)
async def run_command(request: CommandRequest) -> Dict[str, Any]:
    """
    Run a CLI tool with the provided arguments and files.

    The API will:
    1. Create a temporary directory
    2. Recreate the directory structure based on relative paths
    3. Write file contents to the appropriate locations
    4. Run the CLI tool with the provided arguments
    5. Return the command output
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create files with their directory structure
        for file_data in request.files:
            # Get the full path for the file
            file_path = os.path.join(temp_dir, file_data.relative_path)

            # Create directory structure if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Write file content
            with open(file_path, "w") as f:
                f.write(file_data.content)

        # Prepare the command
        command = [request.cli_tool] + request.arguments

        # Set the working directory
        working_dir = os.path.join(temp_dir, request.working_directory or "")

        try:
            # Run the command
            process = subprocess.run(
                command, cwd=working_dir, capture_output=True, text=True, check=False
            )

            # Prepare the response
            return {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "exit_code": process.returncode,
                "command": " ".join(command),
            }
        except FileNotFoundError:
            raise HTTPException(
                status_code=400, detail=f"CLI tool '{request.cli_tool}' not found"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error running command: {str(e)}"
            )


@app.get("/")
async def root():
    """Root endpoint that returns a welcome message."""
    return {"message": "Welcome to CLI Tool Wrapper API"}


@app.get("/health")
async def health():
    """Health check endpoint that returns the service status."""
    return {"status": "healthy"}
