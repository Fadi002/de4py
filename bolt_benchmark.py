
import time
import sys
import os
from de4py.engines.onyx.pipeline import Pipeline

def main():
    if len(sys.argv) < 2:
        print("Usage: python bolt_benchmark.py <sample_file>")
        return

    sample = sys.argv[1]
    with open(sample, "r", encoding="utf-8") as f:
        source = f.read()

    pipeline = Pipeline(use_llm=False)

    start = time.perf_counter()
    result = pipeline.run(source, sample)
    end = time.perf_counter()

    print(f"Time taken: {end - start:.4f} seconds")
    print(f"Result success: {result.success}")
    print(f"Log: {result.log}")

if __name__ == "__main__":
    main()
