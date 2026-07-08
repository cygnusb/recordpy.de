def main() -> None:
    """Start the web server (entrypoint for the `wetterrekord` command)."""
    import uvicorn

    uvicorn.run("wetterrekord.app:app", host="127.0.0.1", port=8000)
