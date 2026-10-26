#!/usr/bin/env python3
"""Download one of NeDM Study 4's fine-tuned Go2 policies and export it to ``policy.onnx`` here.

Study 4 (Kyle Sha; uwsbel/NeDM branch ``kyle/quadruped-pipeline``) fine-tunes the NRDLab base
policy (``../../nrdlab_base/velocity``) with PPO inside a neural reduced model of the Go2 on
Chrono CRM soil. Its fine-tuned policies are in the GATED Hugging Face dataset
``ksha23/nedm-study4-go2-crm``: request access on the dataset page, then log in
(``hf auth login``) or set ``HF_TOKEN``. This script

1. downloads ``policies/recipe_iteration1000/<run>/policy_ft.pt`` at the pinned dataset
   revision (or takes a local file with ``--pt``) and checks its sha256,
2. exports it with ``scripts/pt_to_onnx.py --check`` to ``policy.onnx`` next to this script
   (TorchScript, same 45 -> 12 interface as the base policy, so ``config.yaml`` here is the
   base config with only ``model_path`` changed),
3. writes ``policy_source.json`` (run, sha256 of both files).

The files stay out of git (``.gitignore``): the dataset is gated by its author.

Usage (needs ``pip install huggingface_hub torch onnx onnxruntime``; CPU torch is enough)::

    python3 get_policy.py                      # the default run (standard_s9)
    python3 get_policy.py --run standard_s8
    python3 get_policy.py --pt /path/to/policy_ft.pt --run standard_s8
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PT_TO_ONNX = HERE.parents[3] / "scripts" / "pt_to_onnx.py"
REPO = "ksha23/nedm-study4-go2-crm"
REVISION = "66caa72be7118c78a13262d0fb90d14a393980fe"  # 2026-09-29
DEFAULT_RUN = "standard_s9"  # best of the ten in unitree_mujoco (README.md)
# sha256 of policies/recipe_iteration1000/<run>/policy_ft.pt (the dataset's MANIFEST.tsv):
# the recipe (2 s branches, 1024 rollouts, PPO to iteration 1000) in each of the ten
# standard surrogates; the study's headline result.
RUNS = {
    "standard_s6": "f1744d424fb96446e11f2a9fcf636a683d40b0f1223f43f1344adea94f3cebb4",
    "standard_s7": "48b92a2fe44fbff837f63bbfe5efcff39a943d06027921d4347630866573c37b",
    "standard_s8": "228719be43a721cc99f6121b0c83b1e2a3ae8bf06f1c47a2a933eda866c6f9e1",
    "standard_s9": "4c1c90c028fa0d06bc725629ddc0df2d5f33a997b728339d6ad6009dfd2853f4",
    "standard_north_s0": "940969823e13d6e888348492bdcb820d98632db6b83da5b9e5a5f38c6942e7fc",
    "standard_north_s1": "956e19a30863295fb6adc90f6151d10ebd1f6908505b92b313609896b3b2e446",
    "standard_euler_s2": "2ea3e1e74553f2ae4ae5c1895c249d457aa9a37f833b400eb30570ec13ed4d2b",
    "standard_euler_s3": "69630012e8834455ac967c4ac68ac90b64bd5be3a19d5b6651967362efefbbff",
    "standard_euler_s4": "1ade642b15f8ea57b56389104c342517fefd481f5c477310db290f8d1f1a2bee",
    "standard_euler_s5": "6f6982dbc457cd8c22a0a4be6706e5a1e80b9e0fb01845f526f43dd0dd2cc7f0",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", default=DEFAULT_RUN, choices=sorted(RUNS))
    ap.add_argument("--pt", type=Path, help="use this local policy_ft.pt instead of downloading it")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="nrdlab_ft_") as tmp:
        if args.pt:
            pt = args.pt.resolve()
        else:
            from huggingface_hub import hf_hub_download

            path = f"policies/recipe_iteration1000/{args.run}/policy_ft.pt"
            print(f"downloading {REPO}@{REVISION[:8]}:{path}", flush=True)
            pt = Path(hf_hub_download(REPO, path, repo_type="dataset", revision=REVISION, local_dir=tmp))
        digest = sha256_file(pt)
        if digest != RUNS[args.run]:
            print(f"sha256 {digest} of {pt} is not the one of {args.run} ({RUNS[args.run]})", file=sys.stderr)
            return 1
        staged = HERE / ".policy.onnx.tmp"
        subprocess.run([sys.executable, str(PT_TO_ONNX), "--pt", str(pt), "--onnx", str(staged),
                        "--config", str(HERE / "config.yaml"), "--opset", "17", "--check",
                        "--check-trials", "20"], check=True)
        shutil.move(str(staged), HERE / "policy.onnx")
    record = {
        "dataset": REPO, "revision": REVISION, "run": f"policies/recipe_iteration1000/{args.run}/policy_ft.pt",
        "policy_ft_sha256": digest, "policy_onnx_sha256": sha256_file(HERE / "policy.onnx"),
    }
    (HERE / "policy_source.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"wrote {HERE / 'policy.onnx'} ({args.run})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
