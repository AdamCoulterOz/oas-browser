#!/usr/bin/env python3
"""Validate a coverage mapping against the contract this repository defines.

A coverage mapping is a content repository's file, published by that repository,
saying "this external artifact maps to these API operations". The browser reads
it and renders a coverage view. This checker is published *here* and run *there*,
in each content repository's own CI, because that is where the data is and where
a violation has to block a merge. The definition of conformance stays in the
browser: if each content repository wrote its own checker, the next invariant
added here would have to be independently rediscovered by every one of them, and
the moment one lagged the browser would be consuming a corpus checked against an
older contract.

WHICH WAY IT FAILS WHEN IT IS WRONG
-----------------------------------
It over-fires. Where this checker is wrong it rejects a mapping the browser could
in fact have rendered, rather than passing one it could not.

That is the deliberate choice, and it is the expensive direction, so it is worth
saying why. A conformance gate that under-fires reports clean on a broken corpus,
and the defect then surfaces to a *reader*, as a coverage view missing rows or
citing a grade that was never declared, with nothing anywhere pointing at the
cause. A red build in the content repository is at least legible and at least
addressed to someone who can fix it.

The cost of that direction is real and is named in this repository's handover: a
check that rejects correct data reads as a *data* defect, so the corpus gets
edited to match the checker, and that is worse than no check at all. Two things
hold it off:

- Every vocabulary is derived from the document's own declarations. Grade ids
  come from `grades`, kind ids come from `artifacts.kinds`, spec ids come from
  the catalogue when one is passed. None of them can go stale, because there is
  nothing here to be stale.
- Where the format states no rule, this checker states none either. It does not
  police the HTTP method vocabulary, does not require `items` to be non-empty,
  does not require an item to carry `calls`, `name` or `source`, and does not
  reject unknown keys anywhere. Inventing a rule is exactly how a checker starts
  rejecting correct data.

The only remembered value in the file is `full` / `partial`, and it says so in
its own failure message, because a rotted literal produces a failure that reads
as a data defect and the message is the only part of a check read by somebody who
does not already know how it works.

Every check here is proved by making it fail. tests/test_validate_coverage.py
feeds one document per invariant that violates exactly that invariant, and
asserts both the rejection and the JSON path named. A check that has never failed
is indistinguishable from a check that cannot fail.

Usage:
    python3 tools/validate_coverage.py coverage.json
    python3 tools/validate_coverage.py coverage.json --catalogue specs.json

Exit 0 when clean, 1 when there are findings, which go to stderr.
"""

import argparse
import json
import re
import sys

# The one remembered vocabulary in this file. Everything else is derived from
# the document. See COVERAGE_HEDGE, which is attached to its failure message so
# a reader meeting the failure is told that staleness is a possible cause.
COVERAGE_VALUES = ("full", "partial")

COVERAGE_HEDGE = (
    'either this value is wrong or this checker is out of date: "full" and '
    '"partial" are the only coverage values this checker knows, and unlike '
    "every other vocabulary here they are not declared by the document"
)

ROOT = "(root)"


class _Missing:
    """Distinguishes an absent key from a present null, which are different
    findings and would otherwise report the same message."""

    def __repr__(self):
        return "absent"


MISSING = _Missing()


class Verbatim(str):
    """A description of what was found, rather than the found value itself.

    Some findings are about a shape rather than a value: two grades claiming to
    be the observed one, a call naming its operation twice over. Rendering those
    through the value formatter would quote them like a string the document
    contained, which is exactly the wrong thing to tell a reader who is about to
    search their file for it.
    """


# --------------------------------------------------------------------------
# Failure messages.
#
# A finding names the file, the JSON path to the offending value, what was
# expected and what was found, in that order and always all four. The audience
# of a failure message is the least informed one: somebody in another repository
# whose build just went red and who has never opened this file.
# --------------------------------------------------------------------------

def at(path, key):
    """Path of a named child."""
    return f"{path}.{key}" if path and path != ROOT else str(key)


def nth(path, i):
    """Path of an array element."""
    return f"{path}[{i}]"


def shown(value):
    """How a value is reported back to the reader in `found ...`."""
    if isinstance(value, Verbatim):
        return str(value)
    if isinstance(value, _Missing):
        return "absent"
    if value is None or isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return f"{json.dumps(value)}, a number" if isinstance(value, float) else json.dumps(value)
    if isinstance(value, list):
        if not value:
            return "an empty array"
        return f"an array of {len(value)} entries" if len(value) > 1 else "an array of 1 entry"
    if isinstance(value, dict):
        if not value:
            return "an empty object"
        keys = list(value)
        if len(keys) <= 6:
            return "an object with keys " + ", ".join(keys)
        return f"an object with {len(keys)} keys"
    return repr(value)


class Report:
    """Collects every finding rather than stopping at the first.

    A validator that reports one error per run transfers triage to whoever is
    running it: they fix one, run again, find the next, and learn the true size
    of the problem only after N runs.
    """

    def __init__(self, filename):
        self.filename = filename
        self.findings = []

    def fail(self, path, expected, value, note=None):
        message = f"{self.filename}: {path}: expected {expected}; found {shown(value)}"
        if note:
            message += f" ({note})"
        self.findings.append(message)
        return False

    def extend(self, other):
        self.findings.extend(other.findings)


def get(container, key):
    """Fetch a key, or MISSING, without assuming the container is an object."""
    if isinstance(container, dict):
        return container.get(key, MISSING)
    return MISSING


def require_object(report, path, value, what):
    if not isinstance(value, dict):
        return report.fail(path, what, value)
    return True



# --------------------------------------------------------------------------
# grades
# --------------------------------------------------------------------------

def check_grades(report, document):
    """Returns the set of declared grade ids, or None when `grades` is so broken
    that nothing downstream can be judged against it.

    Returning None matters. If a broken `grades` block yielded an empty set
    instead, every call in the document would then be reported for naming an
    undeclared grade, and several hundred consequences would bury the one cause.
    """
    grades = get(document, "grades")
    if isinstance(grades, _Missing) or not isinstance(grades, list) or not grades:
        report.fail(
            "grades",
            "a non-empty array of grade declarations, since every call cites a "
            "grade and there is nothing to cite otherwise",
            grades,
        )
        return None

    ids = {}
    orders = {}
    observed = []
    for i, grade in enumerate(grades):
        path = nth("grades", i)
        if not require_object(report, path, grade, "a grade declaration object"):
            continue

        gid = get(grade, "id")
        if not isinstance(gid, str) or not gid.strip():
            report.fail(at(path, "id"), "a non-empty string grade id", gid)
        elif gid in ids:
            report.fail(
                at(path, "id"),
                f"a grade id not already declared; {json.dumps(gid)} was declared "
                f"at {at(nth('grades', ids[gid]), 'id')}",
                gid,
            )
        else:
            ids[gid] = i

        for key, what in (("title", "a non-empty string title"),
                          ("caveat", "a non-empty string caveat line")):
            value = get(grade, key)
            if not isinstance(value, str) or not value.strip():
                report.fail(at(path, key), what, value)

        order = get(grade, "order")
        if isinstance(order, bool) or not isinstance(order, int):
            report.fail(at(path, "order"), "an integer order", order)
        elif order in orders:
            report.fail(
                at(path, "order"),
                f"an order not already taken; {order} was taken at "
                f"{at(nth('grades', orders[order]), 'order')}, and two grades "
                "sharing an order have no defined relative weight",
                order,
            )
        else:
            orders[order] = i

        flag = get(grade, "observed")
        if not isinstance(flag, bool):
            report.fail(at(path, "observed"), "a boolean observed flag", flag)
        elif flag:
            observed.append(i)

    if len(observed) != 1:
        where = ", ".join(
            f"{at(nth('grades', i), 'observed')} ({shown(get(grades[i], 'id'))})"
            for i in observed
        )
        report.fail(
            "grades",
            "exactly one grade with observed true, since the browser renders "
            "attested evidence differently from every other kind and cannot do "
            "so with none or with several",
            Verbatim(f"{len(observed)} such grades" + (f": {where}" if where else "")),
        )

    return set(ids)


# --------------------------------------------------------------------------
# artifacts
# --------------------------------------------------------------------------

def check_artifacts(report, document):
    """Returns the set of declared kind ids, or None when the declaration cannot
    be read at all. As with grades, None suppresses the consequent findings."""
    artifacts = get(document, "artifacts")
    if not require_object(report, "artifacts", artifacts,
                          "an object declaring what this mapping's artifacts are"):
        return None

    kind = get(artifacts, "kind")
    if not isinstance(kind, str) or not kind.strip():
        report.fail(
            "artifacts.kind",
            "a non-empty string naming what one artifact is, used as a label "
            "wherever the browser has to say it in prose",
            kind,
        )

    kinds = get(artifacts, "kinds")
    if not isinstance(kinds, dict) or not kinds:
        report.fail(
            "artifacts.kinds",
            "a non-empty object mapping each kind id to its display label",
            kinds,
        )
        return None

    declared = set()
    for kid, label in kinds.items():
        path = at("artifacts.kinds", kid if kid else '""')
        if not kid.strip():
            report.fail(path, "a non-empty kind id as the key", kid)
            continue
        if not isinstance(label, str) or not label.strip():
            report.fail(path, "a non-empty string display label", label)
            continue
        declared.add(kid)

    return declared


# --------------------------------------------------------------------------
# items
# --------------------------------------------------------------------------

def check_source(report, path, source):
    """`source` is optional. The format does not require an item to say where in
    the implementation it lives, so its absence is not a finding. What it says
    when it does say it is checked."""
    if isinstance(source, _Missing):
        return
    if not require_object(report, path, source, "an object locating the artifact in the repository"):
        return

    where = get(source, "path")
    if not isinstance(where, str) or not where.strip():
        report.fail(at(path, "path"), "a non-empty repository-relative string path", where)
    else:
        segments = re.split(r"[\\/]", where)
        if where.startswith("/") or where.startswith("\\") or re.match(r"^[A-Za-z]:[\\/]", where):
            report.fail(
                at(path, "path"),
                "a repository-relative path, since this is read by a browser "
                "that has no filesystem and resolves it against the repository",
                where,
                "the path is absolute",
            )
        elif ".." in segments:
            report.fail(
                at(path, "path"),
                'a repository-relative path with no ".." segment, since a path '
                "that walks out of the repository names nothing the browser can link to",
                where,
            )

    line = get(source, "line")
    if isinstance(line, _Missing):
        return
    if isinstance(line, bool) or not isinstance(line, int) or line < 1:
        report.fail(at(path, "line"), "a positive integer line number, or no line at all", line)


def call_identity(report, path, call):
    """The operation identity of one call, or None if it does not have one.

    A call names its operation exactly one of two ways: by `operation`, when the
    spec gives operations ids, or by `method` and `path` together, when it does
    not. Both forms at once is not redundancy, it is two claims that can drift
    apart with nothing to reconcile them.
    """
    operation = get(call, "operation")
    method = get(call, "method")
    where = get(call, "path")

    has_operation = not isinstance(operation, _Missing)
    has_method = not isinstance(method, _Missing)
    has_where = not isinstance(where, _Missing)

    if has_operation and (has_method or has_where):
        named = ", ".join(k for k in ("method", "path") if not isinstance(get(call, k), _Missing))
        report.fail(
            path,
            'a call naming its operation exactly one way: either "operation", '
            'or "method" and "path" together',
            Verbatim(f"both forms, an operation and {named}"),
        )
        return None

    if not has_operation and not has_method and not has_where:
        report.fail(
            path,
            'a call naming its operation exactly one way: either "operation", '
            'or "method" and "path" together',
            Verbatim("neither form"),
        )
        return None

    if has_operation:
        if not isinstance(operation, str) or not operation.strip():
            report.fail(at(path, "operation"), "a non-empty string operation id", operation)
            return None
        return ("operation", operation)

    if not has_method:
        report.fail(
            at(path, "method"),
            'a method, since this call names its operation by method and path '
            'and half of that form identifies nothing',
            MISSING,
        )
        return None
    if not has_where:
        report.fail(
            at(path, "path"),
            'a path, since this call names its operation by method and path '
            'and half of that form identifies nothing',
            MISSING,
        )
        return None

    ok = True
    if not isinstance(method, str) or not method.strip():
        report.fail(at(path, "method"), "a non-empty string HTTP method", method)
        ok = False
    if not isinstance(where, str) or not where.strip():
        report.fail(at(path, "path"), "a non-empty string operation path", where)
        ok = False
    if not ok:
        return None

    # Case-folded on the method alone. GET and get are the same operation, and
    # a duplicate spelled differently is still a duplicate. The path is left
    # alone because URL paths are case-sensitive.
    return ("method-path", method.lower(), where)


def check_call(report, path, call, grade_ids, spec_ids, catalogue_name):
    if not require_object(report, path, call, "a call object"):
        return None

    spec = get(call, "spec")
    if not isinstance(spec, str) or not spec.strip():
        report.fail(at(path, "spec"), "a non-empty string spec id", spec)
    elif spec_ids is not None and spec not in spec_ids:
        report.fail(
            at(path, "spec"),
            f"a spec id declared in {catalogue_name}, one of "
            + ", ".join(json.dumps(s) for s in sorted(spec_ids)),
            spec,
        )

    identity = call_identity(report, path, call)

    coverage = get(call, "coverage")
    if coverage not in COVERAGE_VALUES:
        report.fail(
            at(path, "coverage"),
            " or ".join(json.dumps(v) for v in COVERAGE_VALUES),
            coverage,
            COVERAGE_HEDGE,
        )

    grade = get(call, "grade")
    if not isinstance(grade, str) or not grade.strip():
        report.fail(at(path, "grade"), "a non-empty string naming a declared grade", grade)
    elif grade_ids is not None and grade not in grade_ids:
        report.fail(
            at(path, "grade"),
            "a grade this document declares, one of "
            + ", ".join(json.dumps(g) for g in sorted(grade_ids))
            + " (declared under grades)",
            grade,
        )

    note = get(call, "note")
    if not isinstance(note, _Missing) and not isinstance(note, str):
        report.fail(at(path, "note"), "a string note, or no note at all", note)

    if identity is None:
        return None
    if not isinstance(spec, str) or not spec.strip():
        return None
    return (spec,) + identity


def describe_identity(identity):
    if identity[1] == "operation":
        return f"spec {json.dumps(identity[0])} operation {json.dumps(identity[2])}"
    return f"spec {json.dumps(identity[0])} {identity[2].upper()} {json.dumps(identity[3])}"


def check_items(report, document, grade_ids, kind_ids, spec_ids, catalogue_name):
    items = get(document, "items")
    if isinstance(items, _Missing) or not isinstance(items, list):
        report.fail("items", "an array of mapped artifacts", items)
        return

    seen = {}
    for i, item in enumerate(items):
        path = nth("items", i)
        if not require_object(report, path, item, "an item object"):
            continue

        iid = get(item, "id")
        if not isinstance(iid, str) or not iid.strip():
            report.fail(at(path, "id"), "a non-empty string item id", iid)
        elif iid in seen:
            report.fail(
                at(path, "id"),
                f"an item id not already used; {json.dumps(iid)} was used at "
                f"{at(nth('items', seen[iid]), 'id')}",
                iid,
            )
        else:
            seen[iid] = i

        kind = get(item, "kind")
        if kind_ids is not None:
            if not isinstance(kind, str) or kind not in kind_ids:
                report.fail(
                    at(path, "kind"),
                    "a kind this document declares, one of "
                    + ", ".join(json.dumps(k) for k in sorted(kind_ids))
                    + " (declared under artifacts.kinds)",
                    kind,
                )
        elif not isinstance(kind, str) or not kind.strip():
            report.fail(at(path, "kind"), "a non-empty string kind id", kind)

        check_source(report, at(path, "source"), get(item, "source"))

        calls = get(item, "calls")
        if isinstance(calls, _Missing):
            continue
        if not isinstance(calls, list):
            report.fail(at(path, "calls"), "an array of calls", calls)
            continue

        identities = {}
        for j, call in enumerate(calls):
            call_path = nth(at(path, "calls"), j)
            identity = check_call(report, call_path, call, grade_ids, spec_ids, catalogue_name)
            if identity is None:
                continue
            if identity in identities:
                report.fail(
                    call_path,
                    "a call this item does not already make; "
                    + describe_identity(identity)
                    + f" is already mapped at {nth(at(path, 'calls'), identities[identity])}",
                    Verbatim("a duplicate"),
                )
            else:
                identities[identity] = j


# --------------------------------------------------------------------------
# catalogue
# --------------------------------------------------------------------------

def catalogue_spec_ids(report, catalogue):
    """The spec ids a catalogue declares, or None when it cannot be read.

    Both shapes are supported deliberately, and this repository's routing work
    settled why: a bare top-level array is the legacy form with no version field
    to detect, and the object form exists because a bare array has nowhere to put
    a default, an index, or a corpus's declarations. Detecting the shape is
    derived where a version field would be remembered.
    """
    if isinstance(catalogue, list):
        entries, base = catalogue, ""
    elif isinstance(catalogue, dict):
        entries = get(catalogue, "specs")
        base = "specs"
        if not isinstance(entries, list):
            report.fail(
                "specs",
                'an array of spec entries, since this catalogue is in the object '
                'form; the other accepted form is a bare top-level array',
                entries,
            )
            return None
    else:
        report.fail(
            ROOT,
            "either a bare array of spec entries or an object carrying a specs array",
            catalogue,
        )
        return None

    ids = set()
    for i, entry in enumerate(entries):
        path = nth(base, i)
        if not isinstance(entry, dict):
            report.fail(path, "a spec entry object", entry)
            continue
        sid = get(entry, "id")
        if not isinstance(sid, str) or not sid.strip():
            report.fail(at(path, "id"), "a non-empty string spec id", sid)
            continue
        ids.add(sid)

    if not ids:
        report.fail(
            base or ROOT,
            "at least one spec entry carrying an id, since a catalogue "
            "declaring no specs can validate nothing",
            entries,
        )
        return None
    return ids


# --------------------------------------------------------------------------
# entry points
# --------------------------------------------------------------------------

def validate(document, filename, spec_ids=None, catalogue_name=None):
    """Every finding in one document, in document order. Empty means conformant."""
    report = Report(filename)
    if not isinstance(document, dict):
        report.fail(ROOT, "a coverage mapping object", document)
        return report.findings

    grade_ids = check_grades(report, document)
    kind_ids = check_artifacts(report, document)
    check_items(report, document, grade_ids, kind_ids, spec_ids,
                catalogue_name or "the catalogue")
    return report.findings


def load(path):
    """(value, findings). A file that cannot be read is a finding like any other,
    reported in the same shape rather than as a traceback."""
    report = Report(path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), report.findings
    except OSError as exc:
        report.fail(ROOT, "a readable file", Verbatim(f"{exc.strerror or exc}"))
        return None, report.findings
    except json.JSONDecodeError as exc:
        report.fail(ROOT, "well-formed JSON", Verbatim(
            f"a parse error at line {exc.lineno} column {exc.colno}: {exc.msg}"))
        return None, report.findings


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate a coverage mapping against the browser's contract.")
    parser.add_argument("file", help="the coverage mapping to validate")
    parser.add_argument("--catalogue", metavar="specs.json",
                        help="a spec catalogue; every call's spec must name an "
                             "id it declares")
    args = parser.parse_args(argv)

    findings = []
    spec_ids = None

    if args.catalogue:
        catalogue, problems = load(args.catalogue)
        findings.extend(problems)
        if not problems:
            report = Report(args.catalogue)
            spec_ids = catalogue_spec_ids(report, catalogue)
            findings.extend(report.findings)

    document, problems = load(args.file)
    findings.extend(problems)
    if not problems:
        findings.extend(validate(document, args.file, spec_ids, args.catalogue))

    if not findings:
        print(f"{args.file}: conformant")
        return 0

    for finding in findings:
        print(finding, file=sys.stderr)
    print(f"\n{len(findings)} finding{'' if len(findings) == 1 else 's'}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
