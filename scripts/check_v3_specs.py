#!/usr/bin/env python3
"""Check V3 spec navigation and review evidence; does not prove semantics."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/specs/v3/contract_registry.json"
HEADING = re.compile(r"^#{1,6} (.+)$", re.MULTILINE)
LOCAL_LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")
ISSUE = re.compile(r"^#### (CA4-\d+)\b[^\n]*\n(?P<body>.*?)(?=^#### CA4-\d+\b|\Z)", re.MULTILINE | re.DOTALL)
STATUS = re.compile(r"\*\*Status:\*\*\s*([A-Z_]+)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", help="show the mapped contract dependency closure")
    parser.add_argument("--open", action="store_true", help="list open CA4 issues from live backlog statuses")
    args = parser.parse_args()
    errors: list[str] = []
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        errors.append("unsupported registry schema_version")

    def read_file(relative: str) -> str:
        path = ROOT / relative
        if path.is_absolute() and path.resolve().is_relative_to(ROOT) and path.is_file():
            return path.read_text(encoding="utf-8")
        errors.append(f"missing or invalid repository path: {relative}")
        return ""

    def check_local_links(relative: str) -> None:
        for target in LOCAL_LINK.findall(read_file(relative)):
            if "://" in target or target.startswith("#"):
                continue
            destination = (ROOT / relative).parent / target.split("#", 1)[0]
            if not destination.is_file():
                errors.append(f"broken local link in {relative}: {target}")

    check_local_links("docs/specs/v3/spec_workflow.md")

    categories = ("authoritative_layers", "orientation_only", "historical_only")
    listed = {category: set(data.get(category, [])) for category in categories}
    for category, paths in listed.items():
        for path in sorted(paths):
            read_file(path)
        if len(paths) != len(data.get(category, [])):
            errors.append(f"duplicate file in {category}")
    for first in categories:
        for second in categories:
            if first < second and listed[first] & listed[second]:
                errors.append(f"file has conflicting authority: {listed[first] & listed[second]}")

    constraint_ids: set[str] = set()
    for constraint in data.get("design_constraints", []):
        identifier = constraint["id"]
        if identifier in constraint_ids:
            errors.append(f"duplicate design constraint: {identifier}")
        constraint_ids.add(identifier)
        if constraint["text"] not in read_file(constraint["source"]):
            errors.append(f"design constraint source drift: {identifier}")

    contracts = data.get("contracts", [])
    contract_ids = [contract["id"] for contract in contracts]
    if len(contract_ids) != len(set(contract_ids)):
        errors.append("duplicate contract ID")
    by_id = {contract["id"]: contract for contract in contracts}
    for contract in contracts:
        owner = contract["owner"]
        if owner not in listed["authoritative_layers"]:
            errors.append(f"contract owner is not authoritative: {contract['id']}")
        headings = HEADING.findall(read_file(owner))
        if headings.count(contract["heading"]) != 1:
            errors.append(f"missing or ambiguous owner heading: {contract['id']}")
        for dependency in contract.get("depends_on", []):
            if dependency not in by_id or dependency == contract["id"]:
                errors.append(f"invalid dependency: {contract['id']} -> {dependency}")

    def visit(identifier: str, active: set[str], done: set[str]) -> None:
        if identifier in active:
            errors.append(f"contract dependency cycle at {identifier}")
            return
        if identifier in done:
            return
        active.add(identifier)
        for dependency in by_id[identifier].get("depends_on", []):
            if dependency in by_id:
                visit(dependency, active, done)
        active.remove(identifier)
        done.add(identifier)

    done: set[str] = set()
    for identifier in by_id:
        visit(identifier, set(), done)

    issues = list(ISSUE.finditer(read_file("docs/v3_backlog.md")))
    issue_ids = [match.group(1) for match in issues]
    if len(issue_ids) != len(set(issue_ids)):
        errors.append("duplicate CA4 issue heading in backlog")
    by_issue = {match.group(1): match.group("body") for match in issues}
    statuses: dict[str, str] = {}
    for match in issues:
        status = STATUS.search(match.group("body"))
        if not status:
            errors.append(f"CA4 issue has no status: {match.group(1)}")
        elif status.group(1) not in {"TODO", "DONE", "NOT_APPLICABLE"}:
            errors.append(f"unknown CA4 status: {match.group(1)} = {status.group(1)}")
        else:
            statuses[match.group(1)] = status.group(1)
    for slice_ in data.get("reviewed_slices", []):
        issue = slice_["issue"]
        if slice_["backlog"] != "docs/v3_backlog.md":
            errors.append(f"unexpected backlog source: {issue}")
        body = by_issue.get(issue, "")
        if not body:
            errors.append(f"reviewed issue absent from backlog: {issue}")
        elif slice_["status"] == "specification_reviewed" and not re.search(
            r"\*\*Status:\*\*\s*DONE\b", body
        ):
            errors.append(f"reviewed issue is not DONE in backlog: {issue}")
        review = read_file(slice_["review"])
        check_local_links(slice_["review"])
        if issue not in review:
            errors.append(f"review issue ID mismatch: {issue}")
        if slice_["evidence"] != "textual_contract_and_scenario_review":
            errors.append(f"unknown evidence type: {issue}")
        if f"**Evidence type:** `{slice_['evidence']}`" not in review:
            errors.append(f"review evidence mismatch: {issue}")
        if not slice_.get("runtime_test"):
            errors.append(f"missing runtime-test status: {issue}")
        elif f"**Runtime test:** `{slice_['runtime_test']}`" not in review:
            errors.append(f"review runtime-test status mismatch: {issue}")
        for identifier in slice_["contracts"]:
            if identifier not in by_id:
                errors.append(f"unknown contract in {issue}: {identifier}")
        for identifier in slice_["design_constraints"]:
            if identifier not in constraint_ids:
                errors.append(f"unknown design constraint in {issue}: {identifier}")
        for term in slice_.get("forbidden_terms", []):
            for owner in listed["authoritative_layers"]:
                if term in read_file(owner):
                    errors.append(f"retired term in authoritative V3 contract: {term} in {owner}")
        for path in slice_["orientation"]:
            if path not in listed["orientation_only"]:
                errors.append(f"unknown orientation reference in {issue}: {path}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        f"V3 spec map valid: {len(listed['authoritative_layers'])} layers, "
        f"{len(by_id)} mapped contracts, {len(by_issue)} CA4 issues "
        f"({sum(value == 'TODO' for value in statuses.values())} open), "
        f"{len(data.get('reviewed_slices', []))} reviewed slice(s)."
    )
    print("Structural check only; semantic scenarios and runtime results require separate review.")
    if args.open:
        print("Open CA4 issues: " + ", ".join(
            sorted((key for key, value in statuses.items() if value == "TODO"),
                   key=lambda key: int(key.split("-")[1]))
        ))
    if args.issue:
        slice_ = next(
            (item for item in data.get("reviewed_slices", []) if item["issue"] == args.issue),
            None,
        )
        if slice_ is None:
            print(f"ERROR: no contract map for {args.issue}")
            return 1
        closure: set[str] = set()

        def include(identifier: str) -> None:
            if identifier in closure:
                return
            closure.add(identifier)
            for dependency in by_id[identifier].get("depends_on", []):
                include(dependency)

        for identifier in slice_["contracts"]:
            include(identifier)
        print(f"{args.issue} contract closure:")
        for identifier in sorted(closure):
            item = by_id[identifier]
            print(f"  {identifier}: {item['owner']} — {item['heading']}")
        print(f"  decision/history: {slice_['backlog']}")
        print(f"  review: {slice_['review']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
