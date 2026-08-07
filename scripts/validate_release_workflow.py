from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from release_workflow_contract import validate_workflow

_SHELL_INPUT_SCAN: Final = r"""
workflow = YAML.safe_load(File.read(ARGV.fetch(0)), aliases: true)
jobs = workflow.is_a?(Hash) ? workflow["jobs"] : nil
if jobs.is_a?(Hash)
  jobs.each do |job_name, job|
    next unless job.is_a?(Hash) && job["steps"].is_a?(Array)
    job["steps"].each_with_index do |step, index|
      next unless step.is_a?(Hash) && step["run"].is_a?(String)
      step["run"].scan(/\$\{\{\s*inputs\.([A-Za-z_][A-Za-z0-9_-]*)\s*\}\}/) do |match|
        puts "jobs.#{job_name}.steps[#{index}].run\t#{match.fetch(0)}"
      end
    end
  end
end
"""


def _validate_shell_input_boundary(path: Path) -> tuple[str, ...]:
    ruby = shutil.which("ruby")
    if ruby is None:
        return ()
    try:
        result = subprocess.run(
            [ruby, "-ryaml", "-e", _SHELL_INPUT_SCAN, str(path)],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return ("release shell input scan exceeded 10 seconds",)
    if result.returncode:
        return ("release shell input scan failed",)
    errors: list[str] = []
    for line in result.stdout.splitlines():
        location, separator, input_name = line.partition("\t")
        if not separator or not location or not input_name:
            return ("release shell input scan produced an invalid result",)
        errors.append(
            "release shell run uses direct dispatch input at "
            f"{location}: inputs.{input_name}"
        )
    return tuple(errors)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the protected release workflow contract."
    )
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--print-matrix", action="store_true")
    args = parser.parse_args(argv)
    validation = validate_workflow(args.workflow)
    errors = validation.errors + _validate_shell_input_boundary(args.workflow)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("release workflow contract is valid")
    if args.print_matrix:
        for os_name, version in validation.matrix:
            print(f"{os_name}|{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
