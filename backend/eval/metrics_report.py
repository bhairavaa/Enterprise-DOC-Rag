METRIC_NAMES = ["faithfulness", "context_precision", "context_recall", "answer_relevancy"]


def print_report(results: list[dict]) -> None:
    if not results:
        print("No results.")
        return

    col_width = 18
    header = f"{'Question':<50} " + " ".join(f"{m:>{col_width}}" for m in METRIC_NAMES)
    print(header)
    print("-" * len(header))

    for r in results:
        question = r["question"]
        label = question[:47] + "..." if len(question) > 50 else question
        row = f"{label:<50} " + " ".join(f"{r[m]:>{col_width}.3f}" for m in METRIC_NAMES)
        print(row)

    print()
    print("Averages:")
    for m in METRIC_NAMES:
        avg = sum(r[m] for r in results) / len(results)
        print(f"  {m}: {avg:.3f}")
