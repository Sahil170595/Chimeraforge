"""Run the local, bounded HTTP planning interface."""

import typer
from chimeraforge.rest_server import DEFAULT_PORT


def serve(
    host: str = typer.Option("127.0.0.1", help="Loopback address: 127.0.0.1 or localhost."),
    port: int = typer.Option(DEFAULT_PORT, min=1, max=65535, help="Local TCP port."),
    allow_network: bool = typer.Option(False, help="Allow HF metadata resolution on the server."),
) -> None:
    """Expose the validated Python planner over local HTTP; offline by default."""
    from chimeraforge.rest_server import make_server

    try:
        server = make_server(host=host, port=port, allow_network=allow_network)
    except (ValueError, OSError) as exc:
        typer.echo(f"Cannot start planning server: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Planning API: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", err=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        typer.echo("Planning API stopped", err=True)
    finally:
        server.server_close()
