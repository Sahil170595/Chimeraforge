"""`eval` command — quality evaluation with text-similarity metrics."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def eval_cmd(
    predictions: str = typer.Option(
        None,
        "--predictions",
        "-p",
        help="Path to predictions file (one per line).",
    ),
    references: str = typer.Option(
        None,
        "--references",
        "-r",
        help="Path to references file (one per line).",
    ),
    task: str = typer.Option(
        None,
        "--task",
        "-t",
        help="Built-in task name (general_knowledge, summarization, code).",
    ),
    model: str = typer.Option(
        "unknown",
        "--model",
        "-m",
        help="Model name identifier.",
    ),
    quant: str = typer.Option(
        None,
        "--quant",
        "-q",
        help="Quantization level (e.g., Q4_K_M).",
    ),
    list_tasks_flag: bool = typer.Option(
        False,
        "--list-tasks",
        help="List available built-in evaluation tasks.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Evaluate LLM output quality with text-similarity metrics."""
    import logging

    from chimeraforge.eval.runner import format_eval_json, format_eval_table, run_eval
    from chimeraforge.eval.tasks import get_task, list_tasks

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    if list_tasks_flag:
        for name in list_tasks():
            console.print(f"  {name}")
        raise typer.Exit()

    if task:
        try:
            t = get_task(task)
        except KeyError as exc:
            console.print(f"[red]Error:[/] {exc}")
            raise typer.Exit(code=1)
        refs = t.references
        task_name = t.name
        if predictions:
            from pathlib import Path as _Path

            pred_path = _Path(predictions)
            if not pred_path.is_file():
                console.print(f"[red]Error:[/] predictions file '{predictions}' not found.")
                raise typer.Exit(code=1)
            preds = pred_path.read_text(encoding="utf-8").strip().splitlines()
        else:
            if not output_json:
                console.print(
                    "[yellow]Note:[/] No --predictions file; "
                    "using task prompts as placeholder (scores will be low)."
                )
            preds = t.prompts
    elif predictions and references:
        from pathlib import Path

        pred_path = Path(predictions)
        ref_path = Path(references)
        if not pred_path.is_file():
            console.print(f"[red]Error:[/] predictions file '{predictions}' not found.")
            raise typer.Exit(code=1)
        if not ref_path.is_file():
            console.print(f"[red]Error:[/] references file '{references}' not found.")
            raise typer.Exit(code=1)
        preds = pred_path.read_text(encoding="utf-8").strip().splitlines()
        refs = ref_path.read_text(encoding="utf-8").strip().splitlines()
        task_name = f"file:{pred_path.name}"
    else:
        console.print("[red]Error:[/] provide --task or both --predictions and --references.")
        raise typer.Exit(code=1)

    result = run_eval(
        predictions=preds,
        references=refs,
        model=model,
        quant=quant,
        task=task_name,
    )

    if output_json:
        console.print(format_eval_json([result]))
    else:
        format_eval_table([result], console)
