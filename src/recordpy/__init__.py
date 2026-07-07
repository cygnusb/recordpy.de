def main() -> None:
    """Start the web server (entrypoint for the `recordpy` command)."""
    import uvicorn

    uvicorn.run("recordpy.app:app", host="127.0.0.1", port=8000)
