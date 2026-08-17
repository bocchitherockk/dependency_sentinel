from __future__ import annotations

import argparse
import sys

import httpx

from common.schemas import StartScanRequest
from common.config import services

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Start a scan by posting to the gateway')
    parser.add_argument('--url', required=True, help='Repository URL to send to the gateway')
    return parser.parse_args(argv)


def request_scan(repository_url: str, gateway_url: str) -> dict:
    start_scan_request: StartScanRequest = StartScanRequest(repository_url=repository_url)
    response = httpx.post(
        gateway_url,
        json=start_scan_request.model_dump(mode='json'),
    )
    response.raise_for_status()
    return response.json()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    gateway_url: str = f"{services['gateway']['endpoint']}/start_scan"

    try:
        payload = request_scan(args.url, gateway_url)
    except Exception as exc:
        print(f'Request failed: {exc}', file=sys.stderr)
        return 1

    print(f'Scan requested for {args.url}')
    print(payload)
    return 0


# if __name__ == '__main__':
#     raise SystemExit(main())
