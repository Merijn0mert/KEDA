#!/usr/bin/env python3
"""
Klein script om de producer te testen.

Gebruik:
    python load_test.py --count 1
    python load_test.py --count 100
    python load_test.py --count 200 --url http://localhost:8080
"""
import argparse
import time
import requests


def main():
    parser = argparse.ArgumentParser(description="Stuur jobs naar de producer")
    parser.add_argument("--count", type=int, default=1, help="Aantal jobs (default: 1)")
    parser.add_argument("--url", type=str, default="http://localhost:8080", help="Producer URL")
    args = parser.parse_args()

    start = time.time()
    response = requests.post(f"{args.url}/add-job", json={"count": args.count})
    elapsed = time.time() - start

    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print(f"Tijd: {elapsed:.3f}s")
    print(f"Timestamp (voor scaling latency meting): {start:.3f}")


if __name__ == "__main__":
    main()
