import json
import multiprocessing
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="CLI Tool Wrapper API")

# Create a thread pool with the number of CPU cores
MAX_WORKERS = multiprocessing.cpu_count()
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)


class CommandResponse(BaseModel):
    """Model for command response with stdout, stderr, exit code."""

    stdout: str
    stderr: str
    exit_code: int
    command: str


async def execute_command(
    arguments: List[str],
    input_files: List[UploadFile],
    output_files: List[str],
) -> Dict[str, Any]:
    """
    Execute a CLI command in a temporary directory with the provided files.
    This function is designed to be run in a separate thread.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create files with their directory structure
        for upload_file in input_files:
            # Extract relative path from filename
            relative_path = upload_file.filename
            if not relative_path:
                continue

            # Get the full path for the file
            file_path = os.path.join(temp_dir, relative_path)

            # Create directory structure if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Write file content
            content = await upload_file.read()
            with open(file_path, "wb") as f:
                f.write(content)

        # Use the command as provided
        command = arguments

        # Use the temp directory as working directory
        working_dir = temp_dir

        try:
            # Run the command
            process = subprocess.run(
                command, cwd=working_dir, capture_output=True, text=True, check=False
            )

            # Collect requested output files
            output_file_data = []
            for file_path in output_files:
                full_path = os.path.join(temp_dir, file_path)
                try:
                    with open(full_path, "rb") as f:
                        content = f.read()
                        output_file_data.append(
                            {"relative_path": file_path, "content": content}
                        )
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
                "output_files": output_file_data,
            }
        except FileNotFoundError:
            raise HTTPException(status_code=400, detail=f"Command not found")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error running command: {str(e)}"
            )


@app.post("/run-command")
async def run_command(
    arguments: str = Form(...),
    output_files: str = Form("[]"),
    input_files: List[UploadFile] = File([]),
):
    """
    Run a command with the provided arguments and files.

    The API will:
    1. Create a temporary directory
    2. Save uploaded files to the appropriate locations
    3. Run the command with the provided arguments
    4. Return the command output and requested output files

    Requests are processed in parallel up to the number of CPU cores.

    Form parameters:
    - arguments: JSON string array representing the command and its arguments
    - output_files: JSON string array of relative paths to return after execution
    - input_files: Multipart file uploads with filenames as relative paths
    """
    try:
        # Parse JSON strings to Python lists
        arguments_list = json.loads(arguments)
        output_files_list = json.loads(output_files)

        if not isinstance(arguments_list, list) or not isinstance(
            output_files_list, list
        ):
            raise HTTPException(
                status_code=400, detail="Arguments and output_files must be JSON arrays"
            )

        # Execute the command
        result = await execute_command(
            arguments=arguments_list,
            input_files=input_files,
            output_files=output_files_list,
        )

        # Prepare response with base64 encoded output files
        response_data = {
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exit_code": result["exit_code"],
            "command": result["command"],
            "output_files": [],
        }

        # Add output files to response
        for file_data in result["output_files"]:
            import base64

            encoded_content = base64.b64encode(file_data["content"]).decode("utf-8")
            response_data["output_files"].append(
                {
                    "relative_path": file_data["relative_path"],
                    "content_base64": encoded_content,
                }
            )

        return JSONResponse(content=response_data)

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400, detail="Invalid JSON in arguments or output_files"
        )


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
