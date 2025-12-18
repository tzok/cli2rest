import asyncio
import json
import logging
import multiprocessing
import os
import resource
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse


class HealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/health") == -1


# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.DEBUG),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


# Create a thread pool with the number of CPU cores
MAX_WORKERS = multiprocessing.cpu_count()
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.loop = asyncio.get_event_loop()
    yield
    # Shutdown
    executor.shutdown(wait=True)


app = FastAPI(title="CLI Tool Wrapper API", lifespan=lifespan)


def create_multipart_generator(
    metadata: Dict[str, Any], output_files: List[Dict[str, str]]
):
    boundary = "frame_boundary"

    # 1. Send the JSON Metadata part
    yield f"--{boundary}\r\n".encode()
    yield b"Content-Type: application/json\r\n"
    yield b'Content-Disposition: form-data; name="metadata"\r\n\r\n'
    yield json.dumps(metadata).encode()
    yield b"\r\n"

    # 2. Send the Files
    for file_info in output_files:
        rel_path = file_info["relative_path"]
        abs_path = file_info["absolute_path"]
        yield f"--{boundary}\r\n".encode()
        yield b"Content-Type: application/octet-stream\r\n"
        yield f'Content-Disposition: attachment; filename="{rel_path}"\r\n\r\n'.encode()

        with open(abs_path, "rb") as f:
            while chunk := f.read(65536):  # 64KB chunks
                yield chunk
        yield b"\r\n"

    # 3. Closing boundary
    yield f"--{boundary}--\r\n".encode()


class CleanupStreamingResponse(StreamingResponse):
    """StreamingResponse that cleans up a directory after completion."""

    def __init__(self, *args, cleanup_dir: str, **kwargs):  # type: ignore
        super().__init__(*args, **kwargs)  # type: ignore
        self.cleanup_dir = cleanup_dir

    async def __call__(self, scope, receive, send):  # type: ignore
        try:
            await super().__call__(scope, receive, send)
        finally:
            import shutil

            shutil.rmtree(self.cleanup_dir, ignore_errors=True)


def execute_command_sync(
    arguments: List[str],
    input_files: List[UploadFile],
    output_files: List[str],
    temp_dir: str,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Execute a CLI command in a temporary directory with the provided files.
    This function runs synchronously and is designed to be run in a separate thread.
    """
    logger.debug("Processing %d input files...", len(input_files))

    for upload_file in input_files:
        # Extract relative path from filename
        relative_path = upload_file.filename
        if not relative_path:
            logger.warning("Skipping file with empty filename")
            continue

        # Get the full path for the file
        file_path = os.path.join(temp_dir, relative_path)
        logger.debug("Processing input file: %s -> %s", relative_path, file_path)

        # Create directory structure if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Write file content (note: upload_file.file is already read at this point)
        content = upload_file.file.read()
        content_size = len(content)
        with open(file_path, "wb") as f:
            f.write(content)
        logger.debug("Saved %d bytes to %s", content_size, relative_path)

    # Use the command as provided
    command = arguments

    # Use the temp directory as working directory
    working_dir = temp_dir

    start_time = datetime.now(timezone.utc)
    start_perf = time.perf_counter()

    stdout, stderr = "", ""
    exit_code = None
    status = "COMPLETED"

    try:
        process = subprocess.run(
            command,
            cwd=working_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        stdout = process.stdout
        stderr = process.stderr
        exit_code = process.returncode

        if exit_code != 0:
            status = "FAILED"
    except subprocess.TimeoutExpired as e:
        status = "TIMEOUT"
        stdout = e.stdout.decode() if e.stdout else ""
        stderr = e.stderr.decode() if e.stderr else ""
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Command not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running command: {str(e)}")

    end_time = datetime.now(timezone.utc)
    duration = time.perf_counter() - start_perf
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)

    # Collect requested output files
    output_file_data: List[Dict[str, str]] = []
    missing_files: List[str] = []
    for file_path in output_files:
        full_path = os.path.join(temp_dir, file_path)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            output_file_data.append(
                {"relative_path": file_path, "absolute_path": full_path}
            )
        else:
            missing_files.append(file_path)

    if missing_files:
        status = "MISSING_OUTPUT_FILES"

    result = {
        "status": status,
        "exit_code": exit_code,
        "missing_files": missing_files,
        "execution_stats": {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "max_rss_kb": usage.ru_maxrss,
            "cpu_user_seconds": usage.ru_utime,
        },
        "stdout": stdout,
        "stderr": stderr,
        "command": " ".join(command),
        "output_files": output_file_data,
    }

    logger.info("Command execution finished with status: %s", status)
    logger.debug("Execution result: %s", json.dumps(result, default=str))
    return result


@app.post("/run-command")
async def run_command(
    arguments: List[str] = Form(...),
    input_files: List[UploadFile] = File(None),
    output_files: List[str] = Form([]),
    timeout: Optional[float] = Form(None),
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
    - arguments: List of strings representing the command and its arguments
    - output_files: List of relative paths to return after execution
    - input_files: Multipart file uploads with filenames as relative paths
    - timeout: Optional timeout in seconds for the command execution
    """
    assert isinstance(arguments, list), "Arguments must be a list of strings"

    try:
        # Read file contents into memory first (async operation)
        for upload_file in input_files:
            if upload_file.filename:
                content = await upload_file.read()
                # Reset file pointer and store content
                upload_file.file.seek(0)
                upload_file.file.truncate()
                upload_file.file.write(content)
                upload_file.file.seek(0)

        # Get the current event loop
        loop = asyncio.get_event_loop()

        # Create the temp directory here so we can manage its lifecycle
        temp_dir = tempfile.mkdtemp()

        # Execute the command in a thread pool
        result = await loop.run_in_executor(
            executor,
            execute_command_sync,
            arguments,
            input_files,
            output_files,
            temp_dir,
            timeout,
        )

        # Separate metadata from binary files
        metadata = result.copy()
        output_files_data = metadata.pop("output_files")

        return CleanupStreamingResponse(
            create_multipart_generator(metadata, output_files_data),
            media_type="multipart/form-data; boundary=frame_boundary",
            cleanup_dir=temp_dir,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )


@app.get("/health")
async def health() -> Dict[str, Any]:
    """Health check endpoint that returns the service status."""
    return {
        "status": "healthy",
        "workers": MAX_WORKERS,
        "active_threads": len(executor._threads),
    }
