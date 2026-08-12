# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Corpus scan/baseline/compare tool for the Onyx build-logs/ gauntlet.

    python -m de4py.engines.onyx.tools.corpus scan
    python -m de4py.engines.onyx.tools.corpus baseline --tag mytag
    python -m de4py.engines.onyx.tools.corpus compare old.json new.json

build-logs/ is untrusted; nothing here ever eval/exec/imports sample content. Ground-truth
originals are trusted (authored demo files from public obfuscator-tool repos) and the three
marked safe_to_execute run only via subprocess with no network access.
"""

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from de4py.engines.onyx.pipeline import Pipeline
from de4py.engines.onyx.vm_lifter import VMLifter
from de4py.engines.onyx.tools import scoring

REPO_ROOT = Path(__file__).resolve().parents[4]
CORPUS_DIR = REPO_ROOT / "build-logs"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

PER_SAMPLE_TIMEOUT_S = 420

ENCRYPTED_LOADERS = {
    "rat_enc.py": "Scrypt+PBKDF2+AES-CBC, key not present in file",
    "main.py": "SHA-512 derived XOR key(s), key material not present in file",
    "test-obf.py": "AES via pycryptodome, key not present in file",
    "run.py": "RSA-PSS + AES-GCM, key not present in file",
}

DE4PY_OWN_OUTPUT = {"t1 (2).py", "t1 (4).py"}
DUPLICATES = {"to_obfuscate-dcff (2).py": "to_obfuscate-dcff.py"}

TOOL_REPO_DIRS = {
    "AbuDabu-pythonObf", "Dor-CFF", "If-Junker", "SalusObf-python",
    "SkariorObf-2.0", "SkariorObf-python", "control-flow-flattening", "kolali",
}


@dataclass
class GroundTruthPair:
    name: str
    original: str
    obfuscated: str
    safe_to_execute: bool = False


GROUND_TRUTH_PAIRS: List[GroundTruthPair] = [
    GroundTruthPair(
        "control_flow_flattening",
        "control-flow-flattening/input.py",
        "control-flow-flattening/out.py",
        safe_to_execute=True,
    ),
    GroundTruthPair(
        "dor_cff",
        "Dor-CFF/to_obfuscate.py",
        "Dor-CFF/to_obfuscate-dcff.py",
    ),
    GroundTruthPair(
        "abudabu",
        "AbuDabu-pythonObf/examples/source_code.py",
        "AbuDabu-pythonObf/examples/obf_code.py",
        safe_to_execute=True,
    ),
    GroundTruthPair(
        "salusobf",
        "SalusObf-python/examples/input.py",
        "SalusObf-python/examples/out.py",
    ),
    GroundTruthPair(
        "skiarobf2_no_compile",
        "SkariorObf-2.0/example/source_code.py",
        "SkariorObf-2.0/example/source_code-NO_compile_method.py",
    ),
    GroundTruthPair(
        "skiarobf2_compile_mod",
        "SkariorObf-2.0/example/source_code.py",
        "SkariorObf-2.0/example/source_code-compile_mod.py",
    ),
    GroundTruthPair(
        "skiarobf_python_no_compile",
        "SkariorObf-python/example/testing.py",
        "SkariorObf-python/example/testing-no_compile.py",
        safe_to_execute=True,
    ),
    GroundTruthPair(
        "skiarobf_python_compile",
        "SkariorObf-python/example/testing.py",
        "SkariorObf-python/example/testing-compile.py",
        safe_to_execute=True,
    ),
    GroundTruthPair(
        "if_junker",
        "If-Junker/tester.py",
        "If-Junker/obf.py",
    ),
]


@dataclass
class SampleResult:
    name: str
    kind: str
    status: str
    composite_score: float = 0.0
    detail: dict = field(default_factory=dict)
    failure_class: str = ""
    error: str = ""
    duration_s: float = 0.0
    unscored: bool = False


def _run_with_timeout(fn, timeout_s: float):
    result = {}

    def worker():
        try:
            result["value"] = fn()
        except Exception as exc:
            result["error"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive():
        return None, TimeoutError(f"exceeded {timeout_s}s")
    if "error" in result:
        return None, result["error"]
    return result.get("value"), None


def _run_pipeline(source: str, filename: str):
    return Pipeline(use_llm=False).run(source, filename)


def _run_behavioral(script_path: Path) -> Optional[str]:
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-S", str(script_path)],
            capture_output=True,
            text=True,
            timeout=30,
            env={},
        )
        return proc.stdout
    except Exception:
        return None


def discover_wild_samples() -> List[Path]:
    if not CORPUS_DIR.is_dir():
        return []
    out = []
    for p in sorted(CORPUS_DIR.iterdir()):
        if p.is_dir():
            continue
        if p.suffix != ".py":
            continue
        if p.name in DE4PY_OWN_OUTPUT or p.name in DUPLICATES:
            continue
        if p.name in ENCRYPTED_LOADERS:
            continue
        out.append(p)
    return out


def scan() -> dict:
    catalog = {"ground_truth_pairs": [], "wild_samples": [], "encrypted_loaders": [], "excluded": []}

    for pair in GROUND_TRUTH_PAIRS:
        orig_path = CORPUS_DIR / pair.original
        obf_path = CORPUS_DIR / pair.obfuscated
        entry = {
            "name": pair.name,
            "original": pair.original,
            "obfuscated": pair.obfuscated,
            "safe_to_execute": pair.safe_to_execute,
            "original_exists": orig_path.is_file(),
            "obfuscated_exists": obf_path.is_file(),
        }
        if obf_path.is_file():
            entry["obfuscated_size"] = obf_path.stat().st_size
            entry["obfuscated_sha256"] = hashlib.sha256(obf_path.read_bytes()).hexdigest()
        catalog["ground_truth_pairs"].append(entry)

    for p in discover_wild_samples():
        data = p.read_bytes()
        try:
            ast.parse(data.decode("utf-8", errors="replace"))
            parses = True
        except SyntaxError:
            parses = False
        catalog["wild_samples"].append({
            "name": p.name,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "parses": parses,
        })

    for name, reason in ENCRYPTED_LOADERS.items():
        p = CORPUS_DIR / name
        catalog["encrypted_loaders"].append({
            "name": name,
            "exists": p.is_file(),
            "reason": reason,
            "classification": scoring.REQUIRES_DYNAMIC_ANALYSIS,
        })

    for name in sorted(DE4PY_OWN_OUTPUT | set(DUPLICATES)):
        catalog["excluded"].append({"name": name, "reason": "de4py's own output or byte-identical duplicate"})

    return catalog


def _score_ground_truth_pair(pair: GroundTruthPair) -> SampleResult:
    orig_path = CORPUS_DIR / pair.original
    obf_path = CORPUS_DIR / pair.obfuscated

    if not orig_path.is_file() or not obf_path.is_file():
        return SampleResult(pair.name, "ground_truth", "MISSING", error="original or obfuscated file not found")

    original_source = orig_path.read_text(encoding="utf-8", errors="replace")
    obfuscated_source = obf_path.read_text(encoding="utf-8", errors="replace")

    t0 = time.time()
    res, err = _run_with_timeout(lambda: _run_pipeline(obfuscated_source, pair.obfuscated), PER_SAMPLE_TIMEOUT_S)
    dt = time.time() - t0

    if err is not None:
        return SampleResult(pair.name, "ground_truth", "ERROR", error=str(err), duration_s=dt,
                             failure_class=scoring.ENGINE_BUG)
    assert res is not None

    behavioral: Optional[bool] = None
    if pair.safe_to_execute:
        import tempfile
        orig_out = _run_behavioral(orig_path)
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(res.cleaned)
            tmp_path = Path(f.name)
        try:
            rec_out = _run_behavioral(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)
        if orig_out is not None and rec_out is not None:
            behavioral = (orig_out == rec_out)

    score = scoring.score_ground_truth(pair.name, original_source, res.cleaned, behavioral)
    if score.blocked_on_decompiler:
        status, cls = "BLOCKED", scoring.PYTHON_VERSION_LIMITATION
    elif score.composite >= 90.0:
        status, cls = "OK", ""
    else:
        status, cls = "PARTIAL", scoring.NEEDS_TRIAGE
    return SampleResult(
        pair.name, "ground_truth", status,
        composite_score=score.composite,
        detail=asdict(score),
        failure_class=cls,
        duration_s=dt,
    )


def _score_wild_sample(path: Path) -> SampleResult:
    original_source = path.read_text(encoding="utf-8", errors="replace")

    t0 = time.time()
    res, err = _run_with_timeout(lambda: _run_pipeline(original_source, path.name), PER_SAMPLE_TIMEOUT_S)
    dt = time.time() - t0

    if err is not None:
        return SampleResult(path.name, "wild", "TIMEOUT" if isinstance(err, TimeoutError) else "ERROR",
                             error=str(err), duration_s=dt, failure_class=scoring.ENGINE_BUG)
    assert res is not None

    vm_log = ""
    try:
        vm_out, vm_err = _run_with_timeout(lambda: VMLifter().deobfuscate(original_source), 60)
        if vm_err is None and vm_out:
            vm_log = vm_out
    except Exception:
        pass

    score = scoring.score_wild_sample(path.name, original_source, res.cleaned, vm_log)
    blocked = bool(re.search(r"no decompiler backend available", res.cleaned))
    cls = scoring.classify_failure(score.composite, score.parses, blocked_on_decompiler=blocked)
    if score.unscored:
        status = "UNSCORED"
    elif blocked:
        status = "BLOCKED"
    elif score.composite >= 90.0:
        status = "OK"
    elif score.composite > 0:
        status = "PARTIAL"
    else:
        status = "FAIL"
    return SampleResult(
        path.name, "wild", status,
        composite_score=score.composite,
        detail=asdict(score),
        failure_class=cls,
        duration_s=dt,
        unscored=score.unscored,
    )


def baseline(tag: str = "baseline") -> dict:
    results: List[SampleResult] = []

    for pair in GROUND_TRUTH_PAIRS:
        results.append(_score_ground_truth_pair(pair))

    for path in discover_wild_samples():
        results.append(_score_wild_sample(path))

    for name, reason in ENCRYPTED_LOADERS.items():
        results.append(SampleResult(
            name, "encrypted_loader", "EXCLUDED",
            failure_class=scoring.REQUIRES_DYNAMIC_ANALYSIS,
            detail={"reason": reason},
        ))

    report = {
        "tag": tag,
        "sample_count": len(results),
        "results": [asdict(r) for r in results],
        "summary": _summarize(results),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"{tag}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _summarize(results: List[SampleResult]) -> dict:
    non_excluded = [r for r in results if r.kind != "encrypted_loader"]
    # A sample with no measurable axis (`unscored`) or one blocked on a real,
    # documented limitation (`BLOCKED`) is neither a pass nor a fail - folding
    # either into the average would misrepresent what was actually measured.
    scored = [r for r in non_excluded if not r.unscored and r.status != "BLOCKED"]
    unscored = [r for r in non_excluded if r.unscored]
    blocked = [r for r in non_excluded if r.status == "BLOCKED"]
    ok = sum(1 for r in scored if r.status == "OK")
    partial = sum(1 for r in scored if r.status == "PARTIAL")
    failed = sum(1 for r in scored if r.status in ("FAIL", "ERROR", "TIMEOUT", "MISSING"))
    avg_score = round(sum(r.composite_score for r in scored) / len(scored), 1) if scored else 0.0
    return {
        "scored_samples": len(scored),
        "ok": ok,
        "partial": partial,
        "failed": failed,
        "unscored": len(unscored),
        "unscored_samples": [r.name for r in unscored],
        "blocked_on_python_version_limitation": len(blocked),
        "blocked_samples": [r.name for r in blocked],
        "excluded_encrypted_loaders": len(results) - len(non_excluded),
        "average_composite_score": avg_score,
    }


def compare(old_path: Path, new_path: Path) -> dict:
    old = json.loads(old_path.read_text(encoding="utf-8"))
    new = json.loads(new_path.read_text(encoding="utf-8"))

    old_by_name = {r["name"]: r for r in old["results"]}
    new_by_name = {r["name"]: r for r in new["results"]}

    deltas = []
    regressions = []
    for name, new_r in new_by_name.items():
        old_r = old_by_name.get(name)
        if old_r is None:
            deltas.append({"name": name, "old": None, "new": new_r["composite_score"], "delta": None})
            continue
        delta = round(new_r["composite_score"] - old_r["composite_score"], 1)
        entry = {"name": name, "old": old_r["composite_score"], "new": new_r["composite_score"], "delta": delta}
        deltas.append(entry)
        if delta < -0.5:
            regressions.append(entry)

    return {
        "old_tag": old.get("tag"),
        "new_tag": new.get("tag"),
        "old_average": old["summary"]["average_composite_score"],
        "new_average": new["summary"]["average_composite_score"],
        "deltas": deltas,
        "regressions": regressions,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="onyx-corpus")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scan")

    p_baseline = sub.add_parser("baseline")
    p_baseline.add_argument("--tag", default="baseline")

    p_compare = sub.add_parser("compare")
    p_compare.add_argument("old")
    p_compare.add_argument("new")

    args = parser.parse_args(argv)

    if args.command == "scan":
        print(json.dumps(scan(), indent=2))
    elif args.command == "baseline":
        report = baseline(args.tag)
        print(json.dumps(report["summary"], indent=2))
    elif args.command == "compare":
        result = compare(Path(args.old), Path(args.new))
        print(json.dumps(result, indent=2))
        if result["regressions"]:
            print(f"\n{len(result['regressions'])} REGRESSION(S) DETECTED", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
