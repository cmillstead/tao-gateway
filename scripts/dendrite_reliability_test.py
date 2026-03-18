#!/usr/bin/env python3
"""Dendrite Reliability Test — Non-Validator Query Success Rate

Tests whether miners on target subnets respond to Dendrite queries
from a non-validator hotkey. This determines whether TaoGateway can
use Dendrite-first routing or needs to fall back to subnet APIs.

Usage:
    uv run python scripts/dendrite_reliability_test.py

    # Override wallet/network:
    uv run python scripts/dendrite_reliability_test.py \
        --wallet-name default \
        --hotkey-name default \
        --network finney

    # Test specific subnets only:
    uv run python scripts/dendrite_reliability_test.py --subnets 1 23

    # More queries per miner:
    uv run python scripts/dendrite_reliability_test.py --queries-per-miner 10

What this measures:
    - Metagraph miner count (total vs reachable)
    - Dendrite query success rate from a non-validator
    - Response latency (p50, p95)
    - Response quality (non-empty, valid content)
    - Whether miners reject, ignore, or serve non-validator queries

Thresholds:
    >95% response rate  →  Dendrite-first is viable (Path A)
    80-95%              →  Viable with retry logic
    <80%                →  Need hybrid/API routing (Path B)
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from dataclasses import dataclass, field

import bittensor as bt


# ---------------------------------------------------------------------------
# Synapse definitions — one per target subnet
# ---------------------------------------------------------------------------

class SN1TextSynapse(bt.Synapse):
    """SN1 Apex — text generation. Parallel role/message arrays."""
    roles: list[str] = []
    messages: list[str] = []
    completion: str = ""
    required_hash_fields: list[str] = ["roles", "messages"]


class SN23ImageSynapse(bt.Synapse):
    """SN23 NicheImage — image generation request.

    Based on SocialTensorSubnet protocol. Miners run image gen models
    and return base64 image data.
    """
    prompt: str = ""
    model_name: str = "FluxSchnell"  # Most common category
    size: str = "1024x1024"
    # Response fields (populated by miner)
    image_data: str = ""
    required_hash_fields: list[str] = ["prompt"]


class SN22SearchSynapse(bt.Synapse):
    """SN22 Desearch — search query.

    Based on Desearch subnet protocol. Miners perform search
    across web, X, Reddit, Arxiv and return results.
    """
    query: str = ""
    source: str = "web"  # web, twitter, reddit, arxiv
    max_results: int = 5
    # Response fields (populated by miner)
    results: list[dict] = []
    completion: str = ""
    required_hash_fields: list[str] = ["query"]


# ---------------------------------------------------------------------------
# Test prompts / queries per subnet
# ---------------------------------------------------------------------------

SUBNET_TEST_CONFIGS: dict[int, dict] = {
    1: {
        "name": "SN1 Apex (Text Generation)",
        "synapse_factory": lambda: SN1TextSynapse(
            roles=["user"],
            messages=["What is the capital of France? Reply in one sentence."],
        ),
        "timeout": 30,
        "check_response": lambda s: bool(getattr(s, "completion", "")),
        "extract_content": lambda s: getattr(s, "completion", "")[:200],
    },
    23: {
        "name": "SN23 NicheImage (Image Generation)",
        "synapse_factory": lambda: SN23ImageSynapse(
            prompt="A simple red circle on white background",
            model_name="FluxSchnell",
        ),
        "timeout": 90,
        "check_response": lambda s: bool(getattr(s, "image_data", "")),
        "extract_content": lambda s: f"[image data: {len(getattr(s, 'image_data', ''))} chars]",
    },
    22: {
        "name": "SN22 Desearch (Search)",
        "synapse_factory": lambda: SN22SearchSynapse(
            query="Bittensor network",
            source="web",
            max_results=3,
        ),
        "timeout": 30,
        "check_response": lambda s: bool(
            getattr(s, "results", []) or getattr(s, "completion", "")
        ),
        "extract_content": lambda s: (
            str(getattr(s, "results", []))[:200]
            or getattr(s, "completion", "")[:200]
            or "[empty]"
        ),
    },
}


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    miner_uid: int
    hotkey: str
    success: bool
    latency_ms: float
    has_content: bool
    content_preview: str = ""
    error: str = ""
    is_timeout: bool = False
    status_code: int | None = None
    status_message: str = ""


@dataclass
class SubnetReport:
    netuid: int
    name: str
    total_miners: int = 0
    reachable_miners: int = 0  # valid IP + port
    tested_miners: int = 0
    results: list[QueryResult] = field(default_factory=list)

    @property
    def successes(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def content_successes(self) -> int:
        return sum(1 for r in self.results if r.success and r.has_content)

    @property
    def response_rate(self) -> float:
        return (self.successes / len(self.results) * 100) if self.results else 0.0

    @property
    def content_rate(self) -> float:
        return (self.content_successes / len(self.results) * 100) if self.results else 0.0

    @property
    def latencies(self) -> list[float]:
        return [r.latency_ms for r in self.results if r.success]

    @property
    def p50_latency(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 0.0

    @property
    def p95_latency(self) -> float:
        if not self.latencies:
            return 0.0
        sorted_l = sorted(self.latencies)
        idx = int(len(sorted_l) * 0.95)
        return sorted_l[min(idx, len(sorted_l) - 1)]


# ---------------------------------------------------------------------------
# Core test logic
# ---------------------------------------------------------------------------

def get_eligible_miners(
    metagraph: bt.Metagraph,
    top_n: int = 10,
) -> list[bt.AxonInfo]:
    """Get top miners by incentive that have reachable axons."""
    eligible = []
    for uid in range(metagraph.n):
        axon = metagraph.axons[uid]
        incentive = float(metagraph.incentive[uid])

        # Skip miners with no incentive (not actively mining)
        if incentive <= 0:
            continue

        # Skip miners with no valid endpoint
        ip = getattr(axon, "ip", "")
        port = getattr(axon, "port", 0)
        if not ip or not port or ip in ("0.0.0.0", "127.0.0.1", ""):
            continue

        eligible.append((uid, axon, incentive))

    # Sort by incentive descending, take top N
    eligible.sort(key=lambda x: x[2], reverse=True)
    return [(uid, axon) for uid, axon, _ in eligible[:top_n]]


async def test_miner(
    dendrite: bt.Dendrite,
    axon: bt.AxonInfo,
    uid: int,
    config: dict,
) -> QueryResult:
    """Send a single Dendrite query to one miner and record the result."""
    synapse = config["synapse_factory"]()
    timeout = config["timeout"]
    start = time.monotonic()

    try:
        responses = await dendrite.forward(
            axons=[axon],
            synapse=synapse,
            timeout=timeout,
        )
    except TimeoutError:
        elapsed_ms = round((time.monotonic() - start) * 1000)
        return QueryResult(
            miner_uid=uid,
            hotkey=axon.hotkey[:12],
            success=False,
            latency_ms=elapsed_ms,
            has_content=False,
            error="timeout",
            is_timeout=True,
        )
    except Exception as exc:
        elapsed_ms = round((time.monotonic() - start) * 1000)
        return QueryResult(
            miner_uid=uid,
            hotkey=axon.hotkey[:12],
            success=False,
            latency_ms=elapsed_ms,
            has_content=False,
            error=f"{type(exc).__name__}: {exc}",
        )

    elapsed_ms = round((time.monotonic() - start) * 1000)

    if not responses:
        return QueryResult(
            miner_uid=uid,
            hotkey=axon.hotkey[:12],
            success=False,
            latency_ms=elapsed_ms,
            has_content=False,
            error="empty response list",
        )

    resp = responses[0]

    # Check Bittensor response flags
    is_timeout = getattr(resp, "is_timeout", False)
    is_success = getattr(resp, "is_success", False)
    status_code = getattr(resp.dendrite, "status_code", None) if hasattr(resp, "dendrite") else None
    status_msg = getattr(resp.dendrite, "status_message", "") if hasattr(resp, "dendrite") else ""

    if is_timeout:
        return QueryResult(
            miner_uid=uid,
            hotkey=axon.hotkey[:12],
            success=False,
            latency_ms=elapsed_ms,
            has_content=False,
            error="synapse timeout flag",
            is_timeout=True,
            status_code=status_code,
            status_message=status_msg,
        )

    has_content = config["check_response"](resp)
    content_preview = config["extract_content"](resp) if has_content else ""

    return QueryResult(
        miner_uid=uid,
        hotkey=axon.hotkey[:12],
        success=is_success or has_content,  # Some miners return content without setting success flag
        latency_ms=elapsed_ms,
        has_content=has_content,
        content_preview=content_preview,
        status_code=status_code,
        status_message=status_msg,
    )


async def test_subnet(
    dendrite: bt.Dendrite,
    subtensor: bt.Subtensor,
    netuid: int,
    config: dict,
    queries_per_miner: int = 5,
    max_miners: int = 10,
) -> SubnetReport:
    """Test Dendrite reliability for one subnet."""
    report = SubnetReport(netuid=netuid, name=config["name"])

    print(f"\n{'='*60}")
    print(f"Testing {config['name']} (netuid={netuid})")
    print(f"{'='*60}")

    # 1. Sync metagraph
    print("  Syncing metagraph...", end=" ", flush=True)
    try:
        metagraph = subtensor.metagraph(netuid=netuid)
        report.total_miners = metagraph.n
        print(f"done. {metagraph.n} total neurons")
    except Exception as exc:
        print(f"FAILED: {exc}")
        return report

    # 2. Find eligible miners
    miners = get_eligible_miners(metagraph, top_n=max_miners)
    report.reachable_miners = len(miners)
    print(f"  Eligible miners (incentive > 0, valid endpoint): {len(miners)}")

    if not miners:
        print("  ⚠ No eligible miners found. Skipping.")
        return report

    # 3. Print top miners
    print(f"\n  Top {min(5, len(miners))} by incentive:")
    for i, (uid, axon) in enumerate(miners[:5]):
        inc = float(metagraph.incentive[uid])
        print(f"    #{i+1}: UID {uid} | {axon.ip}:{axon.port} | incentive={inc:.6f}")

    # 4. Query miners
    report.tested_miners = len(miners)
    total_queries = len(miners) * queries_per_miner
    print(f"\n  Running {total_queries} queries ({queries_per_miner} per miner, {len(miners)} miners)...")

    for round_num in range(queries_per_miner):
        print(f"\n  Round {round_num + 1}/{queries_per_miner}:")
        for uid, axon in miners:
            result = await test_miner(dendrite, axon, uid, config)
            report.results.append(result)

            status = "✓" if result.success else "✗"
            content = "content" if result.has_content else "empty"
            detail = result.content_preview[:60] if result.has_content else result.error
            print(f"    {status} UID {uid:>4} | {result.latency_ms:>5}ms | {content:>7} | {detail}")

        # Brief pause between rounds to avoid hammering
        if round_num < queries_per_miner - 1:
            await asyncio.sleep(1)

    return report


def print_report(reports: list[SubnetReport]) -> None:
    """Print final summary across all tested subnets."""
    print(f"\n\n{'='*70}")
    print("DENDRITE RELIABILITY TEST — SUMMARY")
    print(f"{'='*70}")

    for r in reports:
        print(f"\n{'─'*50}")
        print(f"  {r.name} (netuid={r.netuid})")
        print(f"{'─'*50}")
        print(f"  Metagraph:       {r.total_miners} neurons, {r.reachable_miners} eligible")
        print(f"  Tested:          {r.tested_miners} miners, {len(r.results)} total queries")
        print(f"  Response rate:   {r.response_rate:.1f}% ({r.successes}/{len(r.results)})")
        print(f"  Content rate:    {r.content_rate:.1f}% ({r.content_successes}/{len(r.results)})")

        if r.latencies:
            print(f"  Latency p50:     {r.p50_latency:.0f}ms")
            print(f"  Latency p95:     {r.p95_latency:.0f}ms")

        # Count error types
        errors = {}
        for result in r.results:
            if not result.success:
                key = result.error.split(":")[0] if result.error else "unknown"
                errors[key] = errors.get(key, 0) + 1
        if errors:
            print(f"  Errors:")
            for err, count in sorted(errors.items(), key=lambda x: -x[1]):
                print(f"    {err}: {count}")

        # Verdict
        if r.content_rate >= 95:
            verdict = "EXCELLENT — Dendrite-first is viable"
        elif r.content_rate >= 80:
            verdict = "GOOD — viable with retry logic"
        elif r.content_rate >= 50:
            verdict = "MARGINAL — consider hybrid routing"
        elif r.results:
            verdict = "POOR — use subnet API instead"
        else:
            verdict = "UNTESTABLE — no eligible miners"
        print(f"\n  Verdict: {verdict}")

    # Overall recommendation
    print(f"\n{'='*70}")
    print("ROUTING RECOMMENDATION")
    print(f"{'='*70}")

    all_good = all(r.content_rate >= 80 for r in reports if r.results)
    all_bad = all(r.content_rate < 50 for r in reports if r.results)

    if all_good:
        print("  → Path A: Dendrite-first for all subnets. Your existing architecture works.")
    elif all_bad:
        print("  → Path B: Hybrid routing. Use subnet APIs where available.")
    else:
        print("  → Mixed: Dendrite works for some subnets but not others.")
        print("    Use Dendrite where it works, subnet APIs where it doesn't.")
        for r in reports:
            if r.results:
                mode = "Dendrite" if r.content_rate >= 80 else "API/hybrid"
                print(f"    {r.name}: {mode} ({r.content_rate:.0f}% content rate)")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test Dendrite reliability for TaoGateway subnet candidates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--wallet-name", default="default",
        help="Bittensor wallet name (default: 'default')",
    )
    parser.add_argument(
        "--wallet-path", default="~/.bittensor/wallets",
        help="Path to wallets directory",
    )
    parser.add_argument(
        "--hotkey-name", default="default",
        help="Hotkey name (default: 'default')",
    )
    parser.add_argument(
        "--network", default="finney",
        help="Subtensor network (default: finney)",
    )
    parser.add_argument(
        "--subnets", nargs="+", type=int, default=[1, 23, 22],
        help="Subnet netuids to test (default: 1 23 22)",
    )
    parser.add_argument(
        "--queries-per-miner", type=int, default=5,
        help="Number of queries per miner (default: 5)",
    )
    parser.add_argument(
        "--max-miners", type=int, default=10,
        help="Max miners to test per subnet (default: 10)",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    print("Dendrite Reliability Test for TaoGateway")
    print(f"  Wallet: {args.wallet_name}/{args.hotkey_name}")
    print(f"  Network: {args.network}")
    print(f"  Subnets: {args.subnets}")
    print(f"  Queries per miner: {args.queries_per_miner}")
    print(f"  Max miners per subnet: {args.max_miners}")

    # Validate subnet choices
    for netuid in args.subnets:
        if netuid not in SUBNET_TEST_CONFIGS:
            print(f"\n  ⚠ No test config for SN{netuid}. Available: {list(SUBNET_TEST_CONFIGS.keys())}")
            sys.exit(1)

    # Initialize wallet
    print("\nInitializing wallet...", end=" ", flush=True)
    try:
        wallet = bt.wallet(
            name=args.wallet_name,
            path=args.wallet_path,
            hotkey=args.hotkey_name,
        )
        # Verify hotkey exists
        _ = wallet.hotkey
        print(f"done. Hotkey: {wallet.hotkey.ss58_address[:12]}...")
    except Exception as exc:
        print(f"FAILED: {exc}")
        print("\n  You need a Bittensor wallet with a hotkey to run this test.")
        print("  Create one with: btcli wallet new_coldkey --wallet.name default")
        print("                    btcli wallet new_hotkey --wallet.name default --wallet.hotkey default")
        sys.exit(1)

    # Connect to subtensor
    print(f"Connecting to {args.network}...", end=" ", flush=True)
    try:
        subtensor = bt.Subtensor(network=args.network)
        print("done.")
    except Exception as exc:
        print(f"FAILED: {exc}")
        sys.exit(1)

    # Initialize Dendrite
    print("Creating Dendrite client...", end=" ", flush=True)
    dendrite = bt.Dendrite(wallet=wallet)
    print("done.")

    # Run tests
    reports = []
    for netuid in args.subnets:
        config = SUBNET_TEST_CONFIGS[netuid]
        report = await test_subnet(
            dendrite=dendrite,
            subtensor=subtensor,
            netuid=netuid,
            config=config,
            queries_per_miner=args.queries_per_miner,
            max_miners=args.max_miners,
        )
        reports.append(report)

    # Print summary
    print_report(reports)

    # Cleanup
    dendrite.close()


if __name__ == "__main__":
    asyncio.run(main())
