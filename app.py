import os
import subprocess
import tempfile
import multiprocessing
import json
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="CLI Tool Wrapper API")

# Create a thread pool with the number of CPU cores
MAX_WORKERS = multiprocessing.cpu_count()
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)


class FileData(BaseModel):
    """Model for file data with relative path and content."""

    relative_path: str
    content: str


class CommandResponse(BaseModel):
    """Model for command response with stdout, stderr, exit code."""

    stdout: str
    stderr: str
    exit_code: int
    command: str


async def execute_command(
    cli_tool: str,
    arguments: List[str],
    input_files: List[UploadFile],
    working_directory: Optional[str],
    output_files: List[str]
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

        # Prepare the command
        command = [cli_tool] + arguments

        # Set the working directory
        working_dir = os.path.join(temp_dir, working_directory or "")

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
                        output_file_data.append({
                            "relative_path": file_path,
                            "content": content
                        })
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
            raise HTTPException(
                status_code=400, detail=f"CLI tool '{cli_tool}' not found"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error running command: {str(e)}"
            )


@app.post("/run-command")
async def run_command(
    cli_tool: str = Form(...),
    arguments: str = Form("[]"),
    working_directory: Optional[str] = Form(None),
    output_files: str = Form("[]"),
    input_files: List[UploadFile] = File([])
):
    """
    Run a CLI tool with the provided arguments and files.

    The API will:
    1. Create a temporary directory
    2. Save uploaded files to the appropriate locations
    3. Run the CLI tool with the provided arguments
    4. Return the command output and requested output files

    Requests are processed in parallel up to the number of CPU cores.
    
    Form parameters:
    - cli_tool: The CLI tool to run
    - arguments: JSON string array of arguments to pass to the tool
    - working_directory: Optional subdirectory to run the command from
    - output_files: JSON string array of relative paths to return after execution
    - input_files: Multipart file uploads with filenames as relative paths
    """
    try:
        # Parse JSON strings to Python lists
        arguments_list = json.loads(arguments)
        output_files_list = json.loads(output_files)
        
        if not isinstance(arguments_list, list) or not isinstance(output_files_list, list):
            raise HTTPException(status_code=400, detail="Arguments and output_files must be JSON arrays")
            
        # Execute the command
        result = await execute_command(
            cli_tool=cli_tool,
            arguments=arguments_list,
            input_files=input_files,
            working_directory=working_directory,
            output_files=output_files_list
        )
        
        # Prepare response with base64 encoded output files
        response_data = {
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exit_code": result["exit_code"],
            "command": result["command"],
            "output_files": []
        }
        
        # Add output files to response
        for file_data in result["output_files"]:
            import base64
            encoded_content = base64.b64encode(file_data["content"]).decode('utf-8')
            response_data["output_files"].append({
                "relative_path": file_data["relative_path"],
                "content_base64": encoded_content
            })
            
        return JSONResponse(content=response_data)
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in arguments or output_files")


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
