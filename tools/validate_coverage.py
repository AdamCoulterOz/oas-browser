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
  come from `grades.vocabulary`, kind ids from `artifacts.kinds`, entrypoint ids
  from `artifacts.entrypoints`, uncatalogued reason ids from `uncatalogued`, and
  spec ids and operations from the catalogue the document itself names. None of
  them can go stale, because there is nothing here to be stale.
- Where the format states no rule, this checker states none either. It does not
  police the HTTP method vocabulary, does not police the `tone` vocabulary, does
  not require `items` to be non-empty, does not require an item to carry `calls`,
  `name` or `source`, and does not reject unknown keys anywhere. Inventing a rule
  is exactly how a checker starts rejecting correct data.

One vocabulary is not derived, `full` / `partial`, and that is now a statement
about the format rather than a hedge about this file. See COVERAGE_CLOSED.

THE ONE INVARIANT THAT SPANS TWO REPOSITORIES
---------------------------------------------
Every other check reads one document and answers from it. The catalogue checks do
not: a call's `spec` has to name something a *catalogue* declares, and the
operation it names has to be one that spec describes, and both of those live in
the corpus repository. Those checks therefore have to be able to run, so
`catalogue` is a required field naming the URL the mapping was written against,
and they are no longer contingent on somebody remembering a flag. `--catalogue`
is a local override for a run with no network, not the only way to get the check
at all.

When the declared catalogue, or a spec it names, cannot be fetched, this exits 2
rather than 0 or 1. See main(): a run that quietly skips the only cross-repository
invariant is the under-firing direction on exactly the checks that have no other
guard.

Every check here is proved by making it fail. tests/test_validate_coverage.py
feeds one document per invariant that violates exactly that invariant, and
asserts both the rejection and the JSON path named. A check that has never failed
is indistinguishable from a check that cannot fail.

Usage:
    python3 tools/validate_coverage.py coverage.json
    python3 tools/validate_coverage.py coverage.json --catalogue specs.json

Exit 0 when clean, 1 when there are findings, which go to stderr, and 2 when the
document is clean but something it named could not be reached.
"""

import argparse
import collections
import http.client
import json
import os.path
import re
import sys
import urllib.parse
import urllib.request

# The one vocabulary in this file that the document does not declare, and the
# only one that never will.
COVERAGE_VALUES = ("full", "partial")

# This message used to hedge: it told the reader that either the value was wrong
# or this checker had gone stale, because a remembered literal that rots rejects
# correct data while reading as a data defect.
#
# That hedge is now withdrawn, deliberately and in the other direction. `full`
# and `partial` are not an enum awaiting members. They are the two halves of one
# closed binary: a call either exercises the whole of an operation or some of it,
# and there is no third answer to that question. A corpus reaching for a third
# value has not found a missing member, it has found a second question, and the
# fix is a new axis carrying it rather than a wider enum quietly collapsing two
# questions onto one word. Saying "this checker may be out of date" here would
# invite exactly the wrong repair, which is why the hedge is worse than nothing
# for this particular value even though it was the right instinct in general.
COVERAGE_CLOSED = (
    'this is not a vocabulary awaiting members: "full" and "partial" are the two '
    "halves of one closed binary, so a third value is a second axis asking to be "
    "declared and not a wider enum"
)

# The operation-bearing keys of an OpenAPI path item. Remembered, and it is the
# second remembered vocabulary in this file, which is worth a sentence. It is not
# the *mapping's* method vocabulary, which stays unpoliced: it is the set of keys
# OpenAPI itself gives meaning to, so reading a spec document at all requires
# knowing it. A method a mapping invents is still accepted; it simply will not be
# found in any spec, which is the true thing to report about it.
OPENAPI_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")

ROOT = "(root)"


class _Missing:
    """Distinguishes an absent key from a present null, which are different
    findings and would otherwise report the same message."""

    def __repr__(self):
        return "absent"


MISSING = _Missing()


class Verbatim(str):
    """A description of what was found, rather than the found value itself.

    Some findings are about a shape rather than a value: a call naming its
    operation twice over, a call this item already makes. Rendering those through
    the value formatter would quote them like a string the document contained,
    which is exactly the wrong thing to tell a reader who is about to search
    their file for it.
    """


# Every vocabulary the document declares, in one bundle, because four separate
# parameters threaded through three functions is four chances to pass the wrong
# one. Each field has three states and they are not interchangeable:
#
#   a set   the declaration was read; ids outside it are findings
#   None    the declaration is present and unreadable, or required and absent;
#           the cause has already been reported and the consequences are
#           suppressed so that one cause does not arrive buried under hundreds
#   MISSING the declaration is optional and simply absent, which is itself the
#           answer: a call naming an entrypoint in a document that declares none
#           is a finding about that, not about the id it chose
Declared = collections.namedtuple("Declared", "grades kinds entrypoints reasons")

# What the catalogue contributed, which is the other repository's half. `name` is
# what to call it in a message, `spec_ids` is None when no catalogue was resolved,
# and `operations` maps a spec id to an OperationIndex for the specs whose
# documents could be read. A spec absent from `operations` is one this run could
# not index, and its calls go operation-unchecked rather than reported.
Catalogue = collections.namedtuple("Catalogue", "name spec_ids operations")

# The operations one spec document describes: the set of operation ids it gives,
# and each templated path mapped to {method: operation id or None}. The id is
# kept per method rather than only in the set because a finding about two paths
# that match equally well has to name the operations, and a reader given two
# paths and told to work out which operations they are has been handed the
# checker's job.
OperationIndex = collections.namedtuple("OperationIndex", "ids paths")


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


def listed(ids):
    """A declared vocabulary, spelled out. The reader is told the answer rather
    than sent to look for it."""
    return ", ".join(json.dumps(i) for i in sorted(ids))


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


def declared_ids(report, path, value, what, label_of):
    """The ids a declaration map declares, or None when it cannot be read.

    `artifacts.kinds`, `artifacts.entrypoints` and the top-level `uncatalogued`
    are one shape wearing three names: an id mapped to the display label the
    browser prints wherever it has to say that id in prose. They are checked
    together because three copies of this loop is three places for them to drift
    apart, and the format's own argument for accepting the two newer ones was
    that they reuse a pattern already here rather than adding a concept.
    """
    if not isinstance(value, dict) or not value:
        report.fail(path, what, value)
        return None

    ids = set()
    for key, display in value.items():
        entry = at(path, key if key else '""')
        if not key.strip():
            report.fail(entry, f"a non-empty {label_of} as the key", key)
            continue
        if not isinstance(display, str) or not display.strip():
            report.fail(entry, "a non-empty string display label", display)
            continue
        ids.add(key)
    return ids


# --------------------------------------------------------------------------
# catalogue url
# --------------------------------------------------------------------------

def check_catalogue_url(report, document):
    """The mapping names the catalogue it was written against.

    Required, and required to be absolute, because this is the field that makes
    the cross-repository checks runnable at all. A relative reference has no base
    once the mapping is read anywhere other than beside the catalogue, and the
    browser will not follow any scheme but http and https (SpecStore.cs), so a
    mapping naming another one names a catalogue nothing downstream can reach.
    """
    url = get(document, "catalogue")
    if not isinstance(url, str) or not url.strip():
        report.fail(
            "catalogue",
            "a non-empty string URL naming the catalogue this mapping was "
            "written against, since a call's spec id means nothing except "
            "against a catalogue and this is the only thing that says which one",
            url,
        )
        return

    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        report.fail(
            "catalogue",
            "an absolute http or https URL",
            url,
            "a relative reference has no base outside the directory this file "
            "happens to sit in, and the browser follows no other scheme",
        )


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
    if not isinstance(grades, dict):
        report.fail(
            "grades",
            "an object naming the observed grade and carrying the vocabulary of "
            "grade declarations",
            grades,
            "an array is the older shape of this block: the observed grade is "
            "now named once, by grades.observed, and the declarations moved "
            "under grades.vocabulary"
            if isinstance(grades, list) else None,
        )
        return None

    vocabulary = get(grades, "vocabulary")
    if not isinstance(vocabulary, list) or not vocabulary:
        report.fail(
            "grades.vocabulary",
            "a non-empty array of grade declarations, since every call cites a "
            "grade and there is nothing to cite otherwise",
            vocabulary,
        )
        return None

    ids = {}
    for i, grade in enumerate(vocabulary):
        path = nth("grades.vocabulary", i)
        if not require_object(report, path, grade, "a grade declaration object"):
            continue

        gid = get(grade, "id")
        if not isinstance(gid, str) or not gid.strip():
            report.fail(at(path, "id"), "a non-empty string grade id", gid)
        elif gid in ids:
            report.fail(
                at(path, "id"),
                f"a grade id not already declared; {json.dumps(gid)} was declared "
                f"at {at(nth('grades.vocabulary', ids[gid]), 'id')}",
                gid,
            )
        else:
            ids[gid] = i

        for key, what in (("title", "a non-empty string title"),
                          ("caveat", "a non-empty string caveat line")):
            value = get(grade, key)
            if not isinstance(value, str) or not value.strip():
                report.fail(at(path, key), what, value)

        # `tone` is optional and its vocabulary is not this format's to police.
        # It names a keel treatment, keel owns the set, and a list of tones here
        # would be a second remembered vocabulary rotting against a repository
        # that has no reason to tell this one when it grows.
        tone = get(grade, "tone")
        if not isinstance(tone, _Missing) and not isinstance(tone, str):
            report.fail(at(path, "tone"), "a string tone, or no tone at all", tone)

        # `order` is retired, and a retired key is not an unknown key. Unknown
        # keys pass here on purpose, because a corpus ahead of this checker must
        # not be rejected for it. This one is different in the direction that
        # matters: a file carrying an `order` was written against the shape where
        # it decided the ranking, so its author believes it still means
        # something, and it does not. Position in the array is the order now.
        # Silence would leave that belief intact, and the ranking the key asks
        # for is not necessarily the one the array gives.
        order = get(grade, "order")
        if not isinstance(order, _Missing):
            report.fail(
                at(path, "order"),
                "no order at all, since position in grades.vocabulary is the order",
                order,
                "a grade carrying one was written against the shape where order "
                "decided the ranking; here it decides nothing",
            )

    # The old shape put a boolean `observed` on every grade and this checker then
    # asserted that exactly one of them was true. That cardinality rule existed
    # because "exactly one" is a property of the *set* and it was encoded on a
    # *member*, which is a shape that can represent none and can represent five,
    # so the checker had to spend a rule forbidding what the format allowed.
    # Naming the observed grade once, from the set, makes both unrepresentable,
    # and the rule disappears rather than being enforced better. What is left is
    # a reference check, which is the same check every other id in this file gets.
    observed = get(grades, "observed")
    if not isinstance(observed, str) or not observed.strip():
        report.fail(
            "grades.observed",
            "a non-empty string naming which declared grade counts as attested, "
            "since the browser renders attested evidence differently from every "
            "other kind and cannot do so without being told which it is",
            observed,
        )
    elif observed not in ids:
        report.fail(
            "grades.observed",
            "a grade declared in this document, one of " + listed(ids)
            + " (declared under grades.vocabulary)",
            observed,
        )

    return set(ids)


# --------------------------------------------------------------------------
# artifacts
# --------------------------------------------------------------------------

def check_artifacts(report, document):
    """Returns (kind ids, entrypoint ids), each per the Declared convention.

    Entrypoints are optional, so their absence is MISSING rather than None. The
    difference is load-bearing: a call naming an entrypoint in a document that
    declares no entrypoints at all needs to be told that fact, and it is a
    different finding from naming one the document does not happen to list.
    """
    artifacts = get(document, "artifacts")
    if not require_object(report, "artifacts", artifacts,
                          "an object declaring what this mapping's artifacts are"):
        return None, None

    kind = get(artifacts, "kind")
    if not isinstance(kind, str) or not kind.strip():
        report.fail(
            "artifacts.kind",
            "a non-empty string naming what one artifact is, used as a label "
            "wherever the browser has to say it in prose",
            kind,
        )

    kind_ids = declared_ids(
        report, "artifacts.kinds", get(artifacts, "kinds"),
        "a non-empty object mapping each kind id to its display label",
        "kind id")

    entrypoints = get(artifacts, "entrypoints")
    if isinstance(entrypoints, _Missing):
        entrypoint_ids = MISSING
    else:
        entrypoint_ids = declared_ids(
            report, "artifacts.entrypoints", entrypoints,
            "a non-empty object mapping each entrypoint id to its display label",
            "entrypoint id")

    return kind_ids, entrypoint_ids


# --------------------------------------------------------------------------
# uncatalogued
# --------------------------------------------------------------------------

def first_uncatalogued_reason(document):
    """The path of the first item entry citing an uncatalogued reason, or None.

    Read ahead of the items themselves so that a missing top-level declaration is
    reported once, at the declaration, before the entries that need it. The
    alternative is one finding per entry, and a producer whose extractor emits a
    few hundred of these would get a few hundred copies of one sentence.
    """
    items = get(document, "items")
    if not isinstance(items, list):
        return None
    for i, item in enumerate(items):
        entries = get(item, "uncatalogued")
        if not isinstance(entries, list):
            continue
        for j, entry in enumerate(entries):
            if isinstance(entry, dict) and not isinstance(get(entry, "reason"), _Missing):
                return nth(at(nth("items", i), "uncatalogued"), j)
    return None


def check_uncatalogued_declaration(report, document):
    """The declared uncatalogued reason ids, or None per the Declared convention.

    The map is optional in a document whose items cite no reasons, and required
    the moment one does. That is not the format being coy: a mapping listing no
    uncatalogued calls has nothing to declare, and requiring it anyway would
    reject every mapping written before this axis existed.
    """
    declared = get(document, "uncatalogued")
    if isinstance(declared, _Missing):
        cited = first_uncatalogued_reason(document)
        if cited is None:
            return None
        report.fail(
            "uncatalogued",
            "an object mapping each uncatalogued reason id to its display label, "
            "since an item cites a reason and a reason naming no declaration is "
            "a word this document never defines",
            MISSING,
            f"first cited at {at(cited, 'reason')}",
        )
        return None

    return declared_ids(
        report, "uncatalogued", declared,
        "a non-empty object mapping each uncatalogued reason id to its display label",
        "reason id")


def check_uncatalogued(report, path, entries, reason_ids):
    """Calls the artifact makes that no catalogue operation names.

    A URL returned in a Location header and polled, a URL the user supplies in
    configuration, a path whose segments are runtime values. These have no
    operation identity and never will, so they carry no spec, no coverage and no
    grade: there is nothing for those to be about. What they carry is why, and
    the point of recording them at all is that a coverage view silently omitting
    a fifth of what an artifact does looks exactly like a complete one.
    """
    if isinstance(entries, _Missing):
        return
    if not isinstance(entries, list):
        report.fail(path, "an array of uncatalogued calls", entries)
        return

    for j, entry in enumerate(entries):
        entry_path = nth(path, j)
        if not require_object(report, entry_path, entry, "an uncatalogued call object"):
            continue

        reason = get(entry, "reason")
        if not isinstance(reason, str) or not reason.strip():
            report.fail(
                at(entry_path, "reason"),
                "a non-empty string naming a declared uncatalogued reason, since "
                "an uncatalogued call records nothing except why it is one",
                reason,
            )
        elif reason_ids is not None and reason not in reason_ids:
            report.fail(
                at(entry_path, "reason"),
                "a reason this document declares, one of " + listed(reason_ids)
                + " (declared under uncatalogued)",
                reason,
            )

        count = get(entry, "count")
        if not isinstance(count, _Missing):
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                report.fail(
                    at(entry_path, "count"),
                    "a positive integer count of call sites, or no count at all",
                    count,
                )

        note = get(entry, "note")
        if not isinstance(note, _Missing) and not isinstance(note, str):
            report.fail(at(entry_path, "note"), "a string note, or no note at all", note)


# --------------------------------------------------------------------------
# matching a call's path against a spec's paths
#
# A spec templates the segments it parameterises and a caller fills them in, so
# the two spell the same operation differently and the difference is not a
# defect. `/api/data/{apiVersion}/EntityDefinitions` in the spec and
# `/api/data/v9.2/EntityDefinitions` in the call are one operation; without this
# rule the checker reports a gap that is not there, and in the first corpus to
# hit it that is twenty-two operations rather than an anecdote.
#
# The comparison is otherwise case-sensitive, and that is the load-bearing half.
# The same corpus has a caller sending `POST /licensing/BillingPolicies` where
# the spec says `/licensing/billingPolicies`, which is a real defect in the
# caller: that request does not reach that operation. So a templated segment
# matching a literal is a spelling convention to absorb, and a case difference is
# a bug to surface, and the rule has to hold those apart. Folding case to be
# forgiving would hide a genuine defect in the one file whose entire job is
# describing what the code actually does. Case is folded in exactly one place,
# to *phrase* the failure, never to excuse it.
#
# Once templates match literals, one call path can match several spec paths, and
# a corpus documenting a generic surface alongside specific ones does exactly
# that:
#
#     GET /api/data/{apiVersion}/{entitySetName}    records_query
#     GET /api/data/{apiVersion}/publishers         publishers_list
#
# `GET /api/data/v9.2/publishers` matches both, legitimately, and the first real
# run of this rule left twenty-five rows ambiguous that way, every specific
# operation shadowed by the catch-all. So candidates are ranked by how many
# segments they matched *literally* and the most specific wins: `publishers_list`
# spends a literal on `publishers` where `records_query` spends a template.
#
# The ranking belongs in the contract rather than in each consumer, and that is
# the part worth stating rather than assuming. Two consumers ranking differently
# would resolve one row to two different operations, and by the rule as stated
# without this neither would be wrong, so there would be no way to adjudicate
# which coverage view was right. Ambiguity in a shared contract is worse than a
# strict rule somebody disagrees with, because a rule can be argued and a
# disagreement with no rule behind it cannot be settled at all. For the same
# reason a genuine tie is reported rather than broken: picking one would be this
# checker inventing the missing half of the contract in private.
# --------------------------------------------------------------------------

TEMPLATE = re.compile(r"\{[^{}]*\}")


def segment_pattern(segment):
    """A spec segment as a regex, with every braced run standing for one value.

    Braces that enclose the whole segment are the ordinary case. Braces inside a
    segment, as in `EntityDefinitions(LogicalName='{}')`, are treated the same
    way rather than as literal text. That is deliberate and it is the less
    obvious call: it is the same phenomenon, a value the spec declined to spell
    out, and reading those braces literally would reject
    `EntityDefinitions(LogicalName='account')` for the identical reason the whole
    rule exists to stop. The alternative, calling the partial case too clever and
    matching it literally, buys simplicity by failing on real data.
    """
    out, last = [], 0
    for match in TEMPLATE.finditer(segment):
        out.append(re.escape(segment[last:match.start()]))
        out.append("[^/]+")
        last = match.end()
    out.append(re.escape(segment[last:]))
    return "".join(out)


def literal_segments(spec_path):
    """How specific a spec path is: the segments it spells out rather than
    templates. Every candidate matched the same call path, so they all have the
    same segment count and this is the whole of the ranking."""
    return sum(1 for segment in spec_path.split("/") if TEMPLATE.search(segment) is None)


def path_matches(spec_path, call_path, fold=False):
    """Whether one spec path describes the path a call names."""
    spec_segments = spec_path.split("/")
    call_segments = call_path.split("/")
    if len(spec_segments) != len(call_segments):
        return False
    for spec_segment, call_segment in zip(spec_segments, call_segments):
        if TEMPLATE.search(spec_segment) is None:
            if fold:
                if spec_segment.casefold() != call_segment.casefold():
                    return False
            elif spec_segment != call_segment:
                return False
        else:
            flags = re.IGNORECASE if fold else 0
            if not re.fullmatch(segment_pattern(spec_segment), call_segment, flags):
                return False
    return True


def most_specific(candidates):
    """The winners of the specificity ranking: one path, or several tied.

    Sorted, so that a tie is reported in the same order whatever order the spec
    document happened to declare its paths in. A finding whose wording depends on
    dictionary order is a finding that changes between two runs over one file.
    """
    best = max(literal_segments(p) for p in candidates)
    return sorted(p for p in candidates if literal_segments(p) == best)


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

    # Lowercase is the normal form, and the finding names it rather than merely
    # refusing what was written. This is not the duplicate check in disguise:
    # that comparison case-folds below and would pass either spelling. It is the
    # file being consistent with itself, so that a reader grepping for `get` and
    # a reader grepping for `GET` find the same rows, and so that a diff of two
    # mappings is a diff of what they claim rather than of how they shout.
    if method != method.lower():
        report.fail(
            at(path, "method"),
            f"a lowercase HTTP method; the normal form of {json.dumps(method)} is "
            f"{json.dumps(method.lower())}",
            method,
            "the duplicate check case-folds already, so this is about the file "
            "agreeing with itself rather than about the comparison",
        )

    # Case-folded on the method alone. GET and get are the same operation, and
    # a duplicate spelled differently is still a duplicate. The path is left
    # alone because URL paths are case-sensitive.
    return ("method-path", method.lower(), where)


def check_entrypoint(report, path, call, entrypoint_ids):
    """The entrypoint this call was reached from, checked, and returned so that
    it can take part in the call's identity."""
    entrypoint = get(call, "entrypoint")
    if isinstance(entrypoint, _Missing):
        return None

    if isinstance(entrypoint_ids, _Missing):
        report.fail(
            at(path, "entrypoint"),
            "no entrypoint, since this document declares none under "
            "artifacts.entrypoints and there is nothing here for this to name",
            entrypoint,
            "declare the entrypoints this artifact has, or drop the key",
        )
    elif not isinstance(entrypoint, str) or not entrypoint.strip():
        report.fail(
            at(path, "entrypoint"),
            "a non-empty string naming a declared entrypoint, or no entrypoint at all",
            entrypoint,
        )
    elif entrypoint_ids is not None and entrypoint not in entrypoint_ids:
        report.fail(
            at(path, "entrypoint"),
            "an entrypoint this document declares, one of " + listed(entrypoint_ids)
            + " (declared under artifacts.entrypoints)",
            entrypoint,
        )

    return entrypoint if isinstance(entrypoint, str) else None


def check_operation_exists(report, path, identity, index, spec):
    """The other repository's half: the operation this call names is one the spec
    describes.

    Only reached when that spec's document could be read. A call naming an
    `operation` resolves by id and never touches the path matching below: those
    are two different ways of naming an operation and running one through the
    other would answer a question nobody asked.
    """
    if identity[0] == "operation":
        if identity[1] in index.ids:
            return
        near = [i for i in index.ids if i.casefold() == identity[1].casefold()]
        report.fail(
            at(path, "operation"),
            f"an operation id spec {json.dumps(spec)} declares, of the "
            f"{len(index.ids)} it gives",
            identity[1],
            f"the spec spells this {json.dumps(near[0])}, differing only in case"
            if near else None,
        )
        return

    _, method, where = identity
    matching = [p for p in index.paths if path_matches(p, where)]
    if not matching:
        folded = [p for p in index.paths if path_matches(p, where, fold=True)]
        report.fail(
            at(path, "path"),
            f"a path spec {json.dumps(spec)} describes, of the "
            f"{len(index.paths)} it gives",
            where,
            f"the spec spells this {json.dumps(sorted(folded)[0])}, differing only "
            "in case, and a request to the spelling written here does not reach "
            "that operation" if folded else None,
        )
        return

    carrying = [p for p in matching if method in index.paths[p]]
    if not carrying:
        nearest = most_specific(matching)[0]
        report.fail(
            at(path, "method"),
            f"a method spec {json.dumps(spec)} declares on {json.dumps(nearest)}, "
            "one of " + listed(index.paths[nearest]),
            method,
            f"matched against {json.dumps(nearest)}" if nearest != where else None,
        )
        return

    winners = most_specific(carrying)
    if len(winners) > 1:
        named = ", ".join(json.dumps(index.paths[p][method] or p) for p in winners)
        report.fail(
            at(path, "path"),
            f"a path resolving to one operation in spec {json.dumps(spec)}",
            where,
            f"it matches {len(winners)} equally specific operations, {named}; "
            "the specificity ranking cannot separate them and this checker will "
            "not pick one, since two consumers picking differently is the "
            "disagreement the ranking exists to prevent",
        )


def check_call(report, path, call, declared, catalogue):
    if not require_object(report, path, call, "a call object"):
        return None

    spec = get(call, "spec")
    named_spec = isinstance(spec, str) and bool(spec.strip())
    if not named_spec:
        report.fail(at(path, "spec"), "a non-empty string spec id", spec)
    elif catalogue.spec_ids is not None and spec not in catalogue.spec_ids:
        report.fail(
            at(path, "spec"),
            f"a spec id declared in {catalogue.name}, one of " + listed(catalogue.spec_ids),
            spec,
        )

    identity = call_identity(report, path, call)
    entrypoint = check_entrypoint(report, path, call, declared.entrypoints)

    if identity is not None and named_spec:
        index = catalogue.operations.get(spec)
        if index is not None:
            check_operation_exists(report, path, identity, index, spec)

    coverage = get(call, "coverage")
    if coverage not in COVERAGE_VALUES:
        report.fail(
            at(path, "coverage"),
            " or ".join(json.dumps(v) for v in COVERAGE_VALUES),
            coverage,
            COVERAGE_CLOSED,
        )

    grade = get(call, "grade")
    if not isinstance(grade, str) or not grade.strip():
        report.fail(at(path, "grade"), "a non-empty string naming a declared grade", grade)
    elif declared.grades is not None and grade not in declared.grades:
        report.fail(
            at(path, "grade"),
            "a grade this document declares, one of " + listed(declared.grades)
            + " (declared under grades.vocabulary)",
            grade,
        )

    # `apiVersion` is an annotation and not a disambiguator. It records which
    # version of an API the artifact asked for, it is never required, and its
    # absence means the operation's default rather than an omission. It is
    # deliberately absent from the identity built below: two calls to one
    # operation at two api-versions are two calls to one operation, and a mapping
    # asserting the artifact calls it twice is asserting something about the
    # artifact that is either true of one row or of neither.
    api_version = get(call, "apiVersion")
    if not isinstance(api_version, _Missing):
        if not isinstance(api_version, str) or not api_version.strip():
            report.fail(
                at(path, "apiVersion"),
                "a non-empty string api version, or no apiVersion at all, whose "
                "absence means the operation's default",
                api_version,
            )

    # `approximate` marks a row the producer could not resolve with certainty:
    # a path built by conditional reassignment, say, where a key segment is
    # appended on one branch and the analysis does not track which branch ran.
    # Flagging beats inferring, and the producer's own count of defects caused by
    # inferring is the argument.
    #
    # It deliberately does not touch anything else here, and in particular it
    # does not soften the catalogue checks. An approximate row that fails to
    # resolve is still a finding and an approximate row that resolves is still
    # resolved, because this is a claim about the producer's confidence and not
    # about the data's validity. Let it suppress findings and it becomes a way to
    # silence a real failure by declaring uncertainty about it, which is a worse
    # instrument than no flag at all.
    approximate = get(call, "approximate")
    if not isinstance(approximate, _Missing) and not isinstance(approximate, bool):
        report.fail(
            at(path, "approximate"),
            "true or false, or no approximate at all, whose absence means false",
            approximate,
        )

    note = get(call, "note")
    if not isinstance(note, _Missing) and not isinstance(note, str):
        report.fail(at(path, "note"), "a string note, or no note at all", note)

    if identity is None or not named_spec:
        return None

    # The identity is (spec, entrypoint, operation). The entrypoint is in it
    # because the producer's unit is (artifact, entrypoint, operation) and
    # collapsing it here would reject the exact data the axis was added for: one
    # component reaching one operation from four lifecycle entrypoints is four
    # rows, and the useful fact is which phase. An absent entrypoint is its own
    # value rather than a wildcard, so it collides with other absent ones and
    # with nothing else. A wildcard would make the first row to omit the key
    # collide with every row that names one, which is the same rejection of
    # correct data by a different route.
    return (spec, entrypoint) + identity


def describe_identity(identity):
    spec, entrypoint = identity[0], identity[1]
    if identity[2] == "operation":
        what = f"operation {json.dumps(identity[3])}"
    else:
        what = f"{identity[3].upper()} {json.dumps(identity[4])}"
    via = f" from entrypoint {json.dumps(entrypoint)}" if entrypoint is not None else ""
    return f"spec {json.dumps(spec)} {what}{via}"


def check_items(report, document, declared, catalogue):
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
        if declared.kinds is not None:
            if not isinstance(kind, str) or kind not in declared.kinds:
                report.fail(
                    at(path, "kind"),
                    "a kind this document declares, one of " + listed(declared.kinds)
                    + " (declared under artifacts.kinds)",
                    kind,
                )
        elif not isinstance(kind, str) or not kind.strip():
            report.fail(at(path, "kind"), "a non-empty string kind id", kind)

        check_source(report, at(path, "source"), get(item, "source"))
        check_uncatalogued(report, at(path, "uncatalogued"),
                           get(item, "uncatalogued"), declared.reasons)

        calls = get(item, "calls")
        if isinstance(calls, _Missing):
            continue
        if not isinstance(calls, list):
            report.fail(at(path, "calls"), "an array of calls", calls)
            continue

        identities = {}
        for j, call in enumerate(calls):
            call_path = nth(at(path, "calls"), j)
            identity = check_call(report, call_path, call, declared, catalogue)
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
# reading the catalogue, and the spec documents it names
# --------------------------------------------------------------------------

def catalogue_entries(report, catalogue):
    """[(id, url)] for the specs a catalogue declares, or None when it cannot be
    read.

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

    declared = []
    for i, entry in enumerate(entries):
        path = nth(base, i)
        if not isinstance(entry, dict):
            report.fail(path, "a spec entry object", entry)
            continue
        sid = get(entry, "id")
        if not isinstance(sid, str) or not sid.strip():
            report.fail(at(path, "id"), "a non-empty string spec id", sid)
            continue
        url = get(entry, "url")
        declared.append((sid, url if isinstance(url, str) and url.strip() else None))

    if not declared:
        report.fail(
            base or ROOT,
            "at least one spec entry carrying an id, since a catalogue "
            "declaring no specs can validate nothing",
            entries,
        )
        return None
    return declared


def operation_index(document):
    """The operations one spec document describes, or None if it describes none
    in a shape this can read.

    Path items behind a `$ref` are not followed. That is a gap and it is the
    honest kind: following them means resolving references across documents, and
    a half-resolved index would report a call as naming an operation the spec
    does not have, which is the over-firing direction on the one check whose
    subject lives in another repository.
    """
    paths = get(document, "paths")
    if not isinstance(paths, dict):
        return None

    ids = set()
    declared = {}
    for where, item in paths.items():
        if not isinstance(item, dict):
            continue
        methods = {}
        for method in OPENAPI_METHODS:
            operation = item.get(method)
            if not isinstance(operation, dict):
                continue
            oid = operation.get("operationId")
            oid = oid if isinstance(oid, str) and oid.strip() else None
            methods[method] = oid
            if oid is not None:
                ids.add(oid)
        if methods:
            declared[where] = methods

    return OperationIndex(ids, declared)


def catalogue_operations(declared, read):
    """({spec id: OperationIndex}, [(subject, reason)]).

    `read` takes a spec entry's url and returns (document, reason), so that the
    local and the fetched cases differ in one function rather than throughout.
    A spec that cannot be read is not a finding against the mapping: the mapping's
    author did not write it and cannot fix it. It comes back as a reason, and the
    run says which checks did not happen rather than passing as though they had.
    """
    operations = {}
    unchecked = []
    for sid, url in declared:
        if url is None:
            unchecked.append((f"spec {json.dumps(sid)}",
                              "the catalogue entry names no url"))
            continue
        document, reason = read(url)
        if reason is not None:
            unchecked.append((f"spec {json.dumps(sid)}", reason))
            continue
        index = operation_index(document)
        if index is None:
            unchecked.append((f"spec {json.dumps(sid)}",
                              "the document it names has no paths object"))
            continue
        operations[sid] = index
    return operations, unchecked


def fetch_json(url, timeout=10):
    """(value, reason). The reason is None on success and a sentence saying why
    not otherwise.

    A separate function so that the tests can substitute it. A conformance
    checker whose own suite needs a network is a checker that goes red for
    reasons that have nothing to do with the data it checks, which is the shape
    this repository's handover files under errors anti-correlated with the truth.

    A document that arrives and does not parse comes back here as a reason rather
    than as a finding. It is a real defect and it is a defect in somebody else's
    repository: the author of this mapping cannot fix it and should not have
    their build report it as a fault in their file. What their build should say
    is that the check did not run.
    """
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https"):
        return None, (f"{json.dumps(parsed.scheme)} is not a scheme this fetches, "
                      "and http and https are")

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except (OSError, ValueError, http.client.HTTPException) as exc:
        return None, f"{type(exc).__name__}: {exc}"

    try:
        return json.loads(body), None
    except json.JSONDecodeError as exc:
        return None, (f"a parse error at line {exc.lineno} column {exc.colno}: {exc.msg}")


def read_beside(catalogue_path):
    """A reader for spec documents named by a local catalogue.

    Entry urls resolve against the catalogue rather than against the working
    directory, for the reason SpecStore.cs already carries: the catalogue is the
    document that names them, and its own location is the only thing they can
    sensibly be relative to.
    """
    base = os.path.dirname(os.path.abspath(catalogue_path))

    def read(url):
        if urllib.parse.urlsplit(url).scheme in ("http", "https"):
            return fetch_json(url)
        document, findings = load(os.path.join(base, url))
        if findings:
            return None, findings[0].split(": ", 1)[-1]
        return document, None

    return read


def read_from(catalogue_url):
    """A reader for spec documents named by a fetched catalogue."""

    def read(url):
        return fetch_json(urllib.parse.urljoin(catalogue_url, url))

    return read


# --------------------------------------------------------------------------
# entry points
# --------------------------------------------------------------------------

def validate(document, filename, spec_ids=None, catalogue_name=None, operations=None):
    """Every finding in one document, in document order. Empty means conformant."""
    report = Report(filename)
    if not isinstance(document, dict):
        report.fail(ROOT, "a coverage mapping object", document)
        return report.findings

    catalogue = Catalogue(catalogue_name or "the catalogue", spec_ids, operations or {})

    check_catalogue_url(report, document)
    grade_ids = check_grades(report, document)
    kind_ids, entrypoint_ids = check_artifacts(report, document)
    reason_ids = check_uncatalogued_declaration(report, document)
    declared = Declared(grade_ids, kind_ids, entrypoint_ids, reason_ids)
    check_items(report, document, declared, catalogue)
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


UNCHECKED = 2

Resolved = collections.namedtuple("Resolved", "spec_ids name operations findings unchecked")


def resolve_catalogue(document, override):
    """Everything the other repository contributes to this run.

    `unchecked` is a list of (subject, reason) for the things this run was asked
    to check against and could not reach. They are not findings, because they are
    not claims about the document.
    """
    if override:
        catalogue, findings = load(override)
        if findings:
            return Resolved(None, override, {}, findings, [])
        report = Report(override)
        declared = catalogue_entries(report, catalogue)
        if declared is None:
            return Resolved(None, override, {}, report.findings, [])
        operations, unchecked = catalogue_operations(declared, read_beside(override))
        return Resolved({sid for sid, _ in declared}, override, operations,
                        report.findings, unchecked)

    url = get(document, "catalogue")
    if not isinstance(url, str) or not url.strip():
        # Already a finding from check_catalogue_url, and there is nothing to
        # fetch. Reporting it a second time here as "could not check" would tell
        # the reader their run was inconclusive when in fact it concluded.
        return Resolved(None, None, {}, [], [])

    catalogue, reason = fetch_json(url)
    if reason is not None:
        return Resolved(None, url, {}, [], [(f"catalogue {json.dumps(url)}", reason)])

    report = Report(url)
    declared = catalogue_entries(report, catalogue)
    if declared is None:
        return Resolved(None, url, {}, report.findings, [])
    operations, unchecked = catalogue_operations(declared, read_from(url))
    return Resolved({sid for sid, _ in declared}, url, operations,
                    report.findings, unchecked)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate a coverage mapping against the browser's contract.")
    parser.add_argument("file", help="the coverage mapping to validate")
    parser.add_argument("--catalogue", metavar="specs.json",
                        help="a local catalogue to check spec ids and operations "
                             "against, instead of fetching the one this mapping "
                             "declares; for a run with no network")
    args = parser.parse_args(argv)

    document, findings = load(args.file)
    unchecked = []

    if not findings:
        resolved = resolve_catalogue(document, args.catalogue)
        findings.extend(resolved.findings)
        findings.extend(validate(document, args.file, resolved.spec_ids,
                                 resolved.name, resolved.operations))
        unchecked = resolved.unchecked

    for finding in findings:
        print(finding, file=sys.stderr)
    if findings:
        print(f"\n{len(findings)} finding{'' if len(findings) == 1 else 's'}", file=sys.stderr)

    for subject, reason in unchecked:
        print(f"{args.file}: catalogue: could not check against {subject}: {reason}",
              file=sys.stderr)
    if unchecked:
        print("Those checks are the only ones here that read a document in another "
              "repository, so nothing else in this run covers them; pass "
              "--catalogue with a local copy to check them without a network.",
              file=sys.stderr)

    if findings:
        return 1
    if unchecked:
        # Not 0. A run that skipped the only cross-repository invariant has not
        # earned the word conformant, and a warning printed under a green tick is
        # a warning nobody reads. Not 1 either: nothing in the document is known
        # to be wrong, and reporting it as a violation sends somebody looking for
        # a defect in a file that may well be clean. A third code says the true
        # thing, that this checked what it could, and it still stops a default CI
        # step, which is the right posture for the check with no other guard.
        return UNCHECKED

    print(f"{args.file}: conformant")
    return 0


if __name__ == "__main__":
    sys.exit(main())
