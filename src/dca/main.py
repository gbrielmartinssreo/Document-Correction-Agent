from dca.agent.agent import create_dca_agent

from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.live import Live
from rich.spinner import Spinner
from rich.panel import Panel


def main():
    agent, _ = create_dca_agent()
    console = Console()

    config = {
        "configurable": {
            "thread_id": "default",
        },
    }

    while True:
        console.rule(style="black")

        user_input = Prompt.ask("\n[bold cyan]User[/bold cyan]").strip()

        if user_input.lower() in ("sair", "exit", "quit"):
            console.print("\n[dim]Encerrando[/dim]")
            break

        if not user_input:
            continue

        with Live(
            Spinner("dots", text="[bold blue]Pensando...[/bold blue]"),
            console=console,
            refresh_per_second=10,
            transient=True,
        ):
            result = agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": user_input,
                        }
                    ]
                },
                config=config,
            )

        mensagens = result["messages"]

        response = mensagens[-1].content

        if isinstance(response, list):
            response = "\n".join(
                bloco.get("text", "")
                for bloco in response
                if isinstance(bloco, dict)
                and bloco.get("type") == "text"
            )

        if not isinstance(response, str):
            response = str(response)

        if not response.strip():
            response = "O agente encerrou a execução sem produzir uma resposta."

        console.print(
            Panel(
                Markdown(response),
                title="[bold]Chat[/bold]",
                border_style="black",
                padding=(1, 2),
            )
        )


if __name__ == "__main__":
    main()
