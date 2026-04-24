"""
main.py — Entry point
Usage:
    python main.py          # interactive chat
    python main.py bench    # run benchmark
    python main.py demo     # quick 3-turn smoke test
"""

import sys
import os

# Make the package importable when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from multi_memory_agent.agent import MemoryAgent
from multi_memory_agent.benchmark.runner import run_all, generate_markdown_report


DEMO_KNOWLEDGE = [
    "Python list comprehension syntax: [expr for item in iterable if condition].",
    "Docker: use service name (not localhost) when calling between containers.",
    "LangGraph: nodes are pure functions that take state and return partial updates.",
    "ChromaDB stores embeddings locally; no server needed for in-process mode.",
    "Rate limit for demo API: 60 requests/minute.",
]


def run_demo():
    print("\n=== DEMO: 3-turn smoke test ===\n")
    agent = MemoryAgent(session_id="demo")
    agent.seed_knowledge(DEMO_KNOWLEDGE)

    turns = [
        "Tên tôi là Huy, tôi dị ứng sữa bò.",
        "À nhầm, tôi dị ứng đậu nành chứ không phải sữa bò.",
        "Bạn có nhớ tên tôi và dị ứng của tôi không?",
    ]
    for t in turns:
        print(f"User: {t}")
        resp = agent.chat(t)
        print(f"Agent: {resp}\n")
        print(f"Memory state: {agent.memory_summary()}\n")


def run_interactive():
    print("\n=== Multi-Memory Agent — Interactive Mode ===")
    print("Type 'quit' to exit, 'status' to see memory summary\n")

    agent = MemoryAgent(session_id="interactive")
    agent.seed_knowledge(DEMO_KNOWLEDGE)

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "status":
            print(f"Memory: {agent.memory_summary()}")
            print(f"Profile: {agent.long_term.get_all()}")
            continue

        response = agent.chat(user_input)
        print(f"Agent: {response}\n")


def run_benchmark():
    print("\n=== BENCHMARK: No-memory vs With-memory ===\n")
    results = run_all()
    report = generate_markdown_report(results)

    # Save to file
    out_path = os.path.join(os.path.dirname(__file__), "BENCHMARK.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n✅ Benchmark report saved to {out_path}")

    # Print summary
    print("\n=== SUMMARY ===")
    for r in results:
        nm = r.no_memory_pass_rate
        wm = r.with_memory_pass_rate
        print(f"Scenario {r.scenario_id:2d} [{r.group:8s}] | No-mem: {nm:.0%} | With-mem: {wm:.0%}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "interactive"

    if mode == "bench":
        run_benchmark()
    elif mode == "demo":
        run_demo()
    else:
        run_interactive()