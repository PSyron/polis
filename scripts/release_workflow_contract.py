from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

EXPECTED_MATRIX: Final = (
    ("macos-15", "3.12"),
    ("macos-15", "3.14"),
    ("ubuntu-24.04", "3.12"),
    ("ubuntu-24.04", "3.13"),
    ("ubuntu-24.04", "3.14"),
    ("windows-2025", "3.12"),
    ("windows-2025", "3.14"),
)


@dataclass(frozen=True, slots=True)
class ContractSection:
    name: str
    digest: str


@dataclass(frozen=True, slots=True)
class WorkflowValidation:
    errors: tuple[str, ...]
    matrix: tuple[tuple[str, str], ...]


EXPECTED_SECTIONS: Final = (
    ContractSection(
        "root", "6967fdaf837b83c1db57f58f23a9db8cfe99caf3caf2d2e60fdf6a003f51a861"
    ),
    ContractSection(
        "dispatch",
        "fd02095751949baaf2c87f02c160e46935a07ffe8b6e621c8e28d6b4c73751b7",
    ),
    ContractSection(
        "concurrency",
        "07d4224a1041381dad0afce70a9de7a31f6f7f5c5a824f80ec898c6856417f64",
    ),
    ContractSection(
        "permissions",
        "b6f128a05c751fea08f38887abc670d16781a993d348b10566c1c099e4948f44",
    ),
    ContractSection(
        "job inventory",
        "5097eafbd50f1f150fa1fc02adf56064ba1b42f1d7cf0904804c6addf90509b9",
    ),
    ContractSection(
        "validate_inputs job",
        "bcc0f8fa9bfaa1c7a169dd3a160027e02f0a396f67108dfa716f6d90c9f46bd2",
    ),
    ContractSection(
        "validate_inputs steps",
        "f5b9bcbb8fec19968dfce64f7a7bf25c68ed7a35b459468002e6a9845934cf27",
    ),
    ContractSection(
        "qualify job",
        "8962b520c5927c47ead8d3729d4aa8b9e93316b26c6ed0af159bcc2800646e32",
    ),
    ContractSection(
        "qualify steps",
        "f594537d81e240e0777ffc702fcde6db025aa3290d76f1fdbfb398f5f021d13e",
    ),
    ContractSection(
        "verify_bundle job",
        "f872f73a5bf0eb600ad4c4e146ce455135f3e4c0c9fab3c330760c78e43e82e3",
    ),
    ContractSection(
        "verify_bundle matrix",
        "ad7554ff7fd1457e6a9ca9203aebba36517874292e56dcec51f44fa0b9cc7ad1",
    ),
    ContractSection(
        "verify_bundle steps",
        "e73689369d2d99348859b89ceed13ad663140bfb00c642163fe0f34a53b8b523",
    ),
    ContractSection(
        "upload job",
        "1ebb81be374eec4fea71deb00d584aa48a556d7466d4163412ca1d4078437448",
    ),
    ContractSection(
        "upload steps",
        "fe3e4f29f10ad25b21c3fb2cac64042bb71085ec9a80ff163ea62055783e35a5",
    ),
)

_SECTION_PATTERN: Final = re.compile(r"^([^|]+)\|([0-9a-f]{64})$")
_RUBY_CONTRACT: Final = r"""
encode = nil
encode = lambda do |value|
  case value
  when Hash
    encoded = value.map do |key, item|
      encode.call(key) + encode.call(item)
    end
    "H#{value.length}:" + encoded.join
  when Array
    "A#{value.length}:" + value.map { |item| encode.call(item) }.join
  when String
    "S#{value.bytesize}:#{value}"
  when Integer
    "I#{value}"
  when TrueClass
    "T"
  when FalseClass
    "F"
  when NilClass
    "N"
  else
    abort "unsupported YAML value #{value.class}"
  end
end
workflow = YAML.safe_load(File.read(ARGV.fetch(0)), aliases: true)
abort "workflow must be a mapping" unless workflow.is_a?(Hash)
jobs = workflow["jobs"]
abort "jobs must be a mapping" unless jobs.is_a?(Hash)
job = lambda do |name|
  value = jobs[name]
  value.is_a?(Hash) ? value : {}
end
config = lambda do |name|
  job.call(name).reject do |key, _|
    key == "steps" || (name == "verify_bundle" && key == "strategy")
  end
end
root_keys = [true, "concurrency", "permissions", "jobs"]
sections = [
  ["root", workflow.reject { |key, _| root_keys.include?(key) }],
  ["dispatch", workflow[true]],
  ["concurrency", workflow["concurrency"]],
  ["permissions", workflow["permissions"]],
  ["job inventory", jobs.keys],
  ["validate_inputs job", config.call("validate_inputs")],
  ["validate_inputs steps", job.call("validate_inputs")["steps"]],
  ["qualify job", config.call("qualify")],
  ["qualify steps", job.call("qualify")["steps"]],
  ["verify_bundle job", config.call("verify_bundle")],
  ["verify_bundle matrix", job.call("verify_bundle")["strategy"]],
  ["verify_bundle steps", job.call("verify_bundle")["steps"]],
  ["upload job", config.call("upload")],
  ["upload steps", job.call("upload")["steps"]]
]
sections.each do |name, value|
  puts "#{name}|#{Digest::SHA256.hexdigest(encode.call(value))}"
end
"""


def _parse_sections(output: str) -> tuple[ContractSection, ...] | None:
    sections: list[ContractSection] = []
    for line in output.splitlines():
        match = _SECTION_PATTERN.fullmatch(line)
        if match is None:
            return None
        sections.append(ContractSection(match.group(1), match.group(2)))
    return tuple(sections)


def validate_workflow(path: Path) -> WorkflowValidation:
    if not path.is_file():
        return WorkflowValidation((f"release workflow does not exist: {path}",), ())
    ruby = shutil.which("ruby")
    if ruby is None:
        return WorkflowValidation(("Ruby is required for workflow validation",), ())
    try:
        result = subprocess.run(
            [ruby, "-ryaml", "-rdigest/sha2", "-e", _RUBY_CONTRACT, str(path)],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return WorkflowValidation(("workflow parsing exceeded 10 seconds",), ())
    if result.returncode:
        details = result.stderr.strip().splitlines()
        detail = details[-1] if details else "Ruby parser failed without a diagnostic"
        return WorkflowValidation((f"release workflow YAML is invalid: {detail}",), ())
    actual = _parse_sections(result.stdout)
    if actual is None or len(actual) != len(EXPECTED_SECTIONS):
        return WorkflowValidation(("release parsed semantic result is invalid",), ())
    errors = tuple(
        f"release {expected.name} semantic contract is invalid"
        for expected, observed in zip(EXPECTED_SECTIONS, actual, strict=True)
        if observed != expected
    )
    return WorkflowValidation(errors, EXPECTED_MATRIX if not errors else ())
