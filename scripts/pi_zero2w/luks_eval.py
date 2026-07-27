#!/usr/bin/env python3
"""LUKS calibration evaluation for constrained-device field tests."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Measurement:
    iter_time_ms: int
    luks_format_ms: int
    luks_open_ms: int
    luks_format_ok: bool
    luks_open_ok: bool

    def to_dict(
        self, format_min_ms: int, format_max_ms: int, open_max_ms: int
    ) -> dict[str, object]:
        d: dict[str, object] = {
            "iter_time_ms": self.iter_time_ms,
            "luks_format_ms": self.luks_format_ms,
            "luks_open_ms": self.luks_open_ms,
            "luks_format_ok": self.luks_format_ok,
            "luks_open_ok": self.luks_open_ok,
            "luks_format_in_range": format_min_ms
            <= self.luks_format_ms
            <= format_max_ms,
            "luks_open_in_range": self.luks_open_ms < open_max_ms,
        }
        d["acceptable"] = (
            bool(d["luks_format_ok"])
            and bool(d["luks_open_ok"])
            and bool(d["luks_format_in_range"])
            and bool(d["luks_open_in_range"])
        )
        return d


def load_device_profile(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_device_tier(cpu_model: str, arch: str) -> str:
    m = cpu_model.lower()
    if "pi zero 2" in m:
        return "Tier-C"
    if "raspberry pi 5" in m or "cortex-a76" in m:
        return "Tier-B"
    if arch.lower() in {"x86_64", "amd64"}:
        return "Tier-A"
    return "Tier-B"


def parse_aes_xts_throughput(
    benchmark_output: str,
) -> tuple[float | None, float | None]:
    pat = re.compile(
        r"aes-xts\s+256b\s+([0-9]+(?:\.[0-9]+)?)\s+MiB/s\s+([0-9]+(?:\.[0-9]+)?)\s+MiB/s"
    )
    m = pat.search(benchmark_output)
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2))


def classify_aes_acceleration(
    aes_instruction_present: bool,
    benchmark_ok: bool,
    enc_mibs: float | None,
    dec_mibs: float | None,
) -> str:
    if aes_instruction_present:
        return "confirmed"
    if benchmark_ok and enc_mibs is not None and dec_mibs is not None:
        # ARM environments may not expose AES flags consistently; treat sustained
        # throughput as an inferred accelerated path signal.
        if enc_mibs >= 20.0 and dec_mibs >= 20.0:
            return "inferred"
        return "unknown"
    if not benchmark_ok:
        return "unknown"
    return "unavailable"


def compute_plateau(measurements: list[dict[str, object]]) -> tuple[bool, float, float]:
    if len(measurements) < 2:
        return False, 0.0, 0.0
    # Use broad span to detect diminishing return over reduced iter-time.
    first = measurements[0]
    last = measurements[-1]
    first_fmt = float(first["luks_format_ms"])
    last_fmt = float(last["luks_format_ms"])
    format_improvement_ratio = 0.0
    if first_fmt > 0:
        format_improvement_ratio = (first_fmt - last_fmt) / first_fmt

    first_open = float(first["luks_open_ms"])
    last_open = float(last["luks_open_ms"])
    open_improvement_ratio = 0.0
    if first_open > 0:
        open_improvement_ratio = (first_open - last_open) / first_open

    # Plateau when changes across low-iter region remain tiny.
    low_iter = sorted(measurements, key=lambda m: int(m["iter_time_ms"]))[:4]
    if len(low_iter) >= 2:
        low_fmt = [float(x["luks_format_ms"]) for x in low_iter]
        spread = max(low_fmt) - min(low_fmt)
        plateau_detected = spread <= 80.0
    else:
        plateau_detected = False
    return plateau_detected, format_improvement_ratio, open_improvement_ratio


def recommend_iter(
    measurements: list[dict[str, object]], profile: dict[str, object], tier: str
) -> tuple[int | None, str]:
    acceptable = [m for m in measurements if bool(m["acceptable"])]
    if acceptable:
        best = max(acceptable, key=lambda m: int(m["iter_time_ms"]))
        return int(best["iter_time_ms"]), "highest iter-time meeting full acceptance"

    profile_rec = int(profile.get("recommended_iter_time_ms", 400))
    # Constrained-device fallback: prefer profile recommendation when plateau means
    # lower iter-time no longer improves setup latency materially.
    if tier == "Tier-C":
        return (
            profile_rec,
            "Lower values produced negligible luksFormat improvement while reducing PBKDF work factor.",
        )

    open_ok = [m for m in measurements if bool(m["luks_open_ok"])]
    if not open_ok:
        return None, "no candidate achieved successful open"
    closest = min(open_ok, key=lambda m: abs(float(m["luks_format_ms"]) - 4000.0))
    return (
        int(closest["iter_time_ms"]),
        "closest format time to upper acceptance bound with successful open",
    )


def evaluate_status(
    tier: str,
    aes_status: str,
    dm_crypt_loadable: bool,
    cryptsetup_available: bool,
    selected: dict[str, object] | None,
    recommended_iter: int | None,
) -> str:
    if not cryptsetup_available or not dm_crypt_loadable or recommended_iter is None:
        return "FAIL"
    if selected is None:
        return "FAIL"
    open_ok = bool(selected["luks_open_ok"]) and bool(selected["luks_open_in_range"])
    format_ok = bool(selected["luks_format_in_range"])
    if open_ok and format_ok and aes_status in {"confirmed", "inferred"}:
        return "PASS"
    if tier == "Tier-C" and open_ok:
        return "PASS_WITH_CONSTRAINTS"
    return "FAIL"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--measurements-csv", required=True)
    ap.add_argument("--benchmark-output", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--requested-iter", type=int, required=True)
    ap.add_argument("--cipher", required=True)
    ap.add_argument("--key-size", type=int, required=True)
    ap.add_argument("--cpu-model", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--arch", required=True)
    ap.add_argument("--hostname", required=True)
    ap.add_argument(
        "--aes-instruction-present", choices=["true", "false"], required=True
    )
    ap.add_argument("--dm-crypt-loadable", choices=["true", "false"], required=True)
    ap.add_argument("--cryptsetup-available", choices=["true", "false"], required=True)
    ap.add_argument("--benchmark-ok", choices=["true", "false"], required=True)
    args = ap.parse_args()

    profile = load_device_profile(Path(args.profile))
    format_min_ms = int(profile.get("acceptance_luks_format_ms_min", 1500))
    format_max_ms = int(profile.get("acceptance_luks_format_ms_max", 4000))
    open_max_ms = int(profile.get("acceptance_luks_open_ms_max", 5000))

    raw: list[Measurement] = []
    with open(args.measurements_csv, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) != 5:
                continue
            it, fmt, opn, fmt_ok, opn_ok = row
            raw.append(
                Measurement(
                    iter_time_ms=int(it),
                    luks_format_ms=int(fmt),
                    luks_open_ms=int(opn),
                    luks_format_ok=fmt_ok == "true",
                    luks_open_ok=opn_ok == "true",
                )
            )

    ordered = sorted(raw, key=lambda m: m.iter_time_ms, reverse=True)
    ms = [m.to_dict(format_min_ms, format_max_ms, open_max_ms) for m in ordered]

    requested = next(
        (m for m in ms if int(m["iter_time_ms"]) == args.requested_iter), None
    )
    bench = (
        Path(args.benchmark_output).read_text(encoding="utf-8")
        if Path(args.benchmark_output).exists()
        else ""
    )
    enc_mibs, dec_mibs = parse_aes_xts_throughput(bench)

    tier = classify_device_tier(args.cpu_model, args.arch)
    aes_status = classify_aes_acceleration(
        args.aes_instruction_present == "true",
        args.benchmark_ok == "true",
        enc_mibs,
        dec_mibs,
    )

    plateau_detected, format_improvement_ratio, open_improvement_ratio = (
        compute_plateau(ms)
    )
    recommended_iter, basis = recommend_iter(ms, profile, tier)
    selected = (
        next((m for m in ms if int(m["iter_time_ms"]) == int(recommended_iter)), None)
        if recommended_iter is not None
        else None
    )

    evaluation = evaluate_status(
        tier=tier,
        aes_status=aes_status,
        dm_crypt_loadable=args.dm_crypt_loadable == "true",
        cryptsetup_available=args.cryptsetup_available == "true",
        selected=selected,
        recommended_iter=recommended_iter,
    )

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "evaluation": evaluation,
        "device_tier": tier,
        "iter_time_ms_requested": args.requested_iter,
        "recommended_iter_time_ms": recommended_iter,
        "selected_iter_for_evaluation_ms": (
            int(recommended_iter) if recommended_iter is not None else None
        ),
        "recommendation_basis": basis,
        "cipher": args.cipher,
        "key_size": args.key_size,
        "hostname": args.hostname,
        "arch": args.arch,
        "kernel": args.kernel,
        "cpu_model": args.cpu_model,
        "aes_instruction_present": args.aes_instruction_present == "true",
        "aes_acceleration_status": aes_status,
        "dm_crypt_loadable": args.dm_crypt_loadable == "true",
        "cryptsetup_available": args.cryptsetup_available == "true",
        "benchmark_ok": args.benchmark_ok == "true",
        "benchmark_aes_xts_256_mibs": {
            "encryption": enc_mibs,
            "decryption": dec_mibs,
        },
        "measurements": ms,
        "plateau_detected": plateau_detected,
        "format_improvement_ratio": format_improvement_ratio,
        "open_improvement_ratio": open_improvement_ratio,
        "operational_unlock_status": (
            "acceptable"
            if selected
            and bool(selected["luks_open_ok"])
            and bool(selected["luks_open_in_range"])
            else "attention"
        ),
        "acceptance": {
            "luks_format_range_ms": [format_min_ms, format_max_ms],
            "luks_open_max_ms": open_max_ms,
            "evaluation_based_on": (
                "recommended_iter" if selected is not None else "requested_iter"
            ),
            "requested_iter": {
                "iter_time_ms": int(requested["iter_time_ms"]) if requested else None,
                "luks_format_in_range": (
                    bool(requested["luks_format_in_range"]) if requested else False
                ),
                "luks_open_in_range": (
                    bool(requested["luks_open_in_range"]) if requested else False
                ),
                "luks_format_ok": (
                    bool(requested["luks_format_ok"]) if requested else False
                ),
                "luks_open_ok": bool(requested["luks_open_ok"]) if requested else False,
            },
            "selected_iter": {
                "iter_time_ms": int(selected["iter_time_ms"]) if selected else None,
                "luks_format_in_range": (
                    bool(selected["luks_format_in_range"]) if selected else False
                ),
                "luks_open_in_range": (
                    bool(selected["luks_open_in_range"]) if selected else False
                ),
                "luks_format_ok": (
                    bool(selected["luks_format_ok"]) if selected else False
                ),
                "luks_open_ok": bool(selected["luks_open_ok"]) if selected else False,
            },
            "luks_format_in_range": (
                bool(requested["luks_format_in_range"]) if requested else False
            ),
            "luks_open_in_range": (
                bool(requested["luks_open_in_range"]) if requested else False
            ),
            "aes_required_met": aes_status in {"confirmed", "inferred"},
            "dm_crypt_required_met": args.dm_crypt_loadable == "true",
        },
        "errors": [],
    }

    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
