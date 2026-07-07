def main() -> None:
    """Startet den Webserver (Entrypoint für das `recordpy`-Kommando)."""
    import uvicorn

    uvicorn.run("recordpy.app:app", host="127.0.0.1", port=8000)
