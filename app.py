import os
import subprocess
import tempfile
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

app = FastAPI(title="CLI Tool Wrapper API")

# Create a thread pool with the number of CPU cores
MAX_WORKERS = multiprocessing.cpu_count()
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)


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
    output_files: List[str] = []  # List of relative paths to return after execution


class CommandResponse(BaseModel):
    """Model for command response with stdout, stderr, exit code and output files."""

    stdout: str
    stderr: str
    exit_code: int
    command: str
    output_files: List[FileData] = []  # List of output files with their contents


def execute_command(request: CommandRequest) -> Dict[str, Any]:
    """
    Execute a CLI command in a temporary directory with the provided files.
    This function is designed to be run in a separate thread.
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

            # Collect requested output files
            output_files = []
            for file_path in request.output_files:
                full_path = os.path.join(temp_dir, file_path)
                try:
                    with open(full_path, "r") as f:
                        content = f.read()
                        output_files.append(FileData(relative_path=file_path, content=content))
                except FileNotFoundError:
                    # File doesn't exist, log it but don't include in results
                    print(f"Requested output file not found: {file_path}")
                except Exception as e:
                    # Other errors (permission, etc.), log error
                    print(f"Error reading output file {file_path}: {str(e)}")

            # Prepare the response
            return {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "exit_code": process.returncode,
                "command": " ".join(command),
                "output_files": output_files,
            }
        except FileNotFoundError:
            raise HTTPException(
                status_code=400, detail=f"CLI tool '{request.cli_tool}' not found"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error running command: {str(e)}"
            )


@app.post("/run-command", response_model=CommandResponse)
async def run_command(
    request: CommandRequest, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Run a CLI tool with the provided arguments and files.

    The API will:
    1. Create a temporary directory
    2. Recreate the directory structure based on relative paths
    3. Write file contents to the appropriate locations
    4. Run the CLI tool with the provided arguments
    5. Return the command output

    Requests are processed in parallel up to the number of CPU cores.
    """
    # Submit the task to the thread pool and wait for the result
    result = await app.state.loop.run_in_executor(executor, execute_command, request)

    return result


@app.get("/health")
async def health():
    """Health check endpoint that returns the service status."""
    return {
        "status": "healthy",
        "workers": MAX_WORKERS,
        "active_threads": len(executor._threads),
    }


@app.on_event("startup")
async def startup_event():
    """Store the event loop on startup for use with the executor."""
    import asyncio

    app.state.loop = asyncio.get_event_loop()


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown the thread pool executor when the application stops."""
    executor.shutdown(wait=True)
