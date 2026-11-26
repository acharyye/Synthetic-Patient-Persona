"""Run Synthea against a jar pinned BY CONTENT, and write the MANIFEST that names the run.

    python scripts/run_synthea.py --jar /path/synthea-with-dependencies.jar \
        --sha256 <expected> --population 1000 --seed 20260827 \
        --purpose calibration --out data/synthea/calibration_seed20260827

Synthea publishes its jar at a mutable tag. This script never fetches it: it is
handed a file and an expected sha256, and **refuses to run on a mismatch**. A
calibration target that cannot name the generator code that produced it cannot
be reproduced, and "generated from Synthea" names nothing.

`--purpose` is `structural` or `calibration`, and it is written into the
MANIFEST. `synthea_derive` reads it: a structural export feeds no target.

Only the tables the loader reads are kept in full (patients, conditions,
medications). The others are recorded by row count and sha256 and not copied —
the same recorded-not-silent rule as the truncation in the first export.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

KEPT = ("patients", "conditions", "medications")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rows(path: Path) -> int:
    with path.open("rb") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--sha256", required=True, help="the jar's expected sha256")
    parser.add_argument("--population", type=int, required=True, help="Synthea -p")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--purpose", choices=("structural", "calibration"), required=True)
    parser.add_argument("--keep-module", type=Path, help="Synthea -k criteria module")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    actual = sha256(args.jar)
    if actual != args.sha256:
        print(f"REFUSED: jar sha256 is {actual}, expected {args.sha256}.\n"
              "The jar is pinned by content. A different jar is different generator code; "
              "amend the registration on the record before running it.")
        return 2
    if args.out.exists() and any(args.out.iterdir()):
        print(f"REFUSED: {args.out} is not empty. An export is never overwritten in place.")
        return 2

    java = subprocess.run(["java", "-version"], capture_output=True, text=True)
    java_version = (java.stderr or java.stdout).splitlines()[0] if java.returncode == 0 else "unknown"

    with tempfile.TemporaryDirectory() as work:
        command = [
            "java", "-jar", str(args.jar.resolve()),
            "-p", str(args.population), "-s", str(args.seed), "-cs", str(args.seed),
            "--exporter.csv.export", "true", "--exporter.fhir.export", "false",
            "--exporter.hospital.fhir.export", "false",
            "--exporter.practitioner.fhir.export", "false",
            "--exporter.baseDirectory", str(Path(work) / "output"),
        ]
        if args.keep_module:
            command += ["-k", str(args.keep_module.resolve())]
        print(" ".join(command))
        result = subprocess.run(command, cwd=work, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout[-2000:], result.stderr[-2000:], sep="\n")
            return result.returncode

        csv_dir = Path(work) / "output" / "csv"
        files = sorted(csv_dir.glob("*.csv"))
        if not files:
            print("Synthea produced no CSV output.")
            return 1

        args.out.mkdir(parents=True, exist_ok=True)
        tables = {}
        for path in files:
            kept = path.stem in KEPT
            tables[path.stem] = {"rows": rows(path), "sha256": sha256(path), "kept": kept}
            if kept:
                shutil.copy(path, args.out / path.name)
        patients = tables["patients"]["rows"]

    purpose = {
        "structural": "structural-validation run ONLY — feeds NO calibration target",
        "calibration": "calibration run — feeds the Synthea-vs-prior table",
    }[args.purpose]
    manifest = {
        "tool": "synthea-with-dependencies.jar",
        "jar_sha256": actual,
        "population_flag": f"-p {args.population}",
        "seed": args.seed,
        "clinician_seed": args.seed,
        "keep_module": args.keep_module.name if args.keep_module else None,
        "patients_generated": patients,
        "generated_on": date.today().isoformat(),
        "java": java_version,
        "purpose": purpose,
        "tables": tables,
        "note": "only the tables the loader reads are kept; the rest are recorded by row "
                "count and sha256 so their absence is stated rather than silent",
    }
    (args.out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {args.out}: {patients} patients, purpose={args.purpose}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
