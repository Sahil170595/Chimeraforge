"""Built-in evaluation tasks with hardcoded QA pairs.

Provides small, curated prompt-reference sets for quick quality evaluation
without requiring external benchmark datasets. Three built-in tasks:

- ``general_knowledge``: 10 factual QA pairs
- ``summarization``: 5 text-to-summary pairs
- ``code``: 5 code-generation pairs
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalTask:
    """Definition of an evaluation task with prompts and reference answers.

    Attributes:
        name: Short identifier for the task.
        description: Human-readable description of what the task evaluates.
        prompts: Input prompts to send to the model.
        references: Gold-standard expected outputs (one per prompt).
    """

    name: str
    description: str
    prompts: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


BUILTIN_TASKS: dict[str, EvalTask] = {
    "general_knowledge": EvalTask(
        name="general_knowledge",
        description="10 factual question-answer pairs covering science, geography, and history.",
        prompts=[
            "What is the chemical symbol for water?",
            "What planet is closest to the Sun?",
            "What year did World War II end?",
            "What is the speed of light in vacuum in meters per second?",
            "What is the capital of France?",
            "Who wrote the play Romeo and Juliet?",
            "What is the largest organ in the human body?",
            "How many continents are there on Earth?",
            "What gas do plants absorb from the atmosphere during photosynthesis?",
            "What is the boiling point of water in degrees Celsius at sea level?",
        ],
        references=[
            "H2O",
            "Mercury",
            "1945",
            "299792458",
            "Paris",
            "William Shakespeare",
            "The skin",
            "7",
            "Carbon dioxide",
            "100",
        ],
    ),
    "summarization": EvalTask(
        name="summarization",
        description="5 short passages with expected one-sentence summaries.",
        prompts=[
            (
                "Summarize in one sentence: The mitochondria are membrane-bound "
                "organelles found in the cytoplasm of eukaryotic cells. They "
                "generate most of the cell's supply of adenosine triphosphate "
                "(ATP), which is used as a source of chemical energy."
            ),
            (
                "Summarize in one sentence: Python is a high-level, general-purpose "
                "programming language. Its design philosophy emphasizes code "
                "readability with the use of significant indentation. Python is "
                "dynamically typed and garbage-collected."
            ),
            (
                "Summarize in one sentence: The Great Wall of China is a series "
                "of fortifications built along the historical northern borders "
                "of China to protect against various nomadic groups. Several "
                "walls were built from as early as the 7th century BC."
            ),
            (
                "Summarize in one sentence: Machine learning is a subset of "
                "artificial intelligence that enables systems to learn and "
                "improve from experience without being explicitly programmed. "
                "It focuses on developing algorithms that can access data and "
                "use it to learn for themselves."
            ),
            (
                "Summarize in one sentence: The Amazon rainforest produces "
                "approximately 20 percent of the world's oxygen and is home "
                "to 10 percent of all species on Earth, making it the most "
                "biodiverse place on the planet."
            ),
        ],
        references=[
            (
                "Mitochondria are organelles in eukaryotic cells that produce "
                "ATP as the cell's main energy source."
            ),
            (
                "Python is a readable, high-level programming language that "
                "is dynamically typed and garbage-collected."
            ),
            (
                "The Great Wall of China is a series of ancient fortifications "
                "built to defend against northern nomadic invasions."
            ),
            (
                "Machine learning is an AI subset where systems learn from "
                "data and improve without explicit programming."
            ),
            (
                "The Amazon rainforest is the most biodiverse place on Earth, "
                "producing about 20 percent of the world's oxygen."
            ),
        ],
    ),
    "code": EvalTask(
        name="code",
        description="5 short code-generation tasks with reference solutions.",
        prompts=[
            "Write a Python function that returns the factorial of n.",
            "Write a Python function that checks if a string is a palindrome.",
            "Write a Python function that returns the nth Fibonacci number.",
            "Write a Python function that flattens a nested list.",
            "Write a Python function that counts vowels in a string.",
        ],
        references=[
            (
                "def factorial(n):\n"
                "    if n <= 1:\n"
                "        return 1\n"
                "    return n * factorial(n - 1)"
            ),
            ("def is_palindrome(s):\n    s = s.lower().strip()\n    return s == s[::-1]"),
            (
                "def fibonacci(n):\n"
                "    if n <= 0:\n"
                "        return 0\n"
                "    if n == 1:\n"
                "        return 1\n"
                "    a, b = 0, 1\n"
                "    for _ in range(2, n + 1):\n"
                "        a, b = b, a + b\n"
                "    return b"
            ),
            (
                "def flatten(lst):\n"
                "    result = []\n"
                "    for item in lst:\n"
                "        if isinstance(item, list):\n"
                "            result.extend(flatten(item))\n"
                "        else:\n"
                "            result.append(item)\n"
                "    return result"
            ),
            ("def count_vowels(s):\n    return sum(1 for c in s.lower() if c in 'aeiou')"),
        ],
    ),
}


def get_task(name: str) -> EvalTask:
    """Get a built-in evaluation task by name.

    Args:
        name: Task identifier (e.g., ``"general_knowledge"``).

    Returns:
        The corresponding ``EvalTask``.

    Raises:
        KeyError: If the task name is not found in ``BUILTIN_TASKS``.
    """
    if name not in BUILTIN_TASKS:
        available = ", ".join(sorted(BUILTIN_TASKS.keys()))
        raise KeyError(f"Unknown eval task '{name}'. Available: {available}")
    return BUILTIN_TASKS[name]


def list_tasks() -> list[str]:
    """Return names of all built-in evaluation tasks.

    Returns:
        Sorted list of task name strings.
    """
    return sorted(BUILTIN_TASKS.keys())
