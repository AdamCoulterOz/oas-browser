#!/usr/bin/env python3
"""Tests for tools/validate_coverage.py, the coverage mapping conformance check.

Every invariant the checker enforces has a test here that feeds it a document
violating exactly that invariant, and asserts two things: that the document is
rejected, and that the finding names the right JSON path. A check that has never
failed is indistinguishable from a check that cannot fail, and both are green.

The path assertion is not decoration. This checker runs in somebody else's CI,
against somebody else's data, and the JSON path is the entire actionable content
of the failure for them. A check that fires on the right document and names the
wrong location has moved the work rather than done it.

Most tests assert the *set* of paths reported, not merely that one is present.
That is the guard against cascades: a broken grade block that also reported every
call in the document for citing an undeclared grade would be technically correct
and practically useless, because the one cause would be buried under its own
consequences.

The checker's stated error direction is over-firing, so the last class here
proves the other half: the places where the format states no rule and the checker
deliberately states none either. Those are where an over-firing check would start
rejecting correct data.

Proven by making them fail, not by being green. Every check in the validator was
disabled in turn, 28 of them, and each disabling turns this file red. The sweep
found one hole while it was being written: neutering the branch that reports half
of the method-and-path form fell through to a plain type check, which names the
same JSON path with a much worse message, so the path assertion alone could not
tell the two apart. Both tests now assert what the message says as well, which is
the thing that actually differs. That is the general lesson from it: asserting
the path is necessary and is not always sufficient, because two checks can agree
on where and disagree on what a reader is told.

Run with:

    python3 -m unittest discover -s tests -v
"""
import contextlib
import copy
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO / "tools" / "validate_coverage.py"

_spec = importlib.util.spec_from_file_location("validate_coverage", SCRIPT)
validate_coverage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_coverage)

FILE = "coverage.json"
CATALOGUE = "specs.json"

# A conformant document, and the base every mutation below starts from. It is
# deliberately not minimal: it carries both ways of naming an operation, an
# optional note, an optional source line, and two grades, so that a mutation
# removing one thing leaves the rest exercised.
GRADES = [
    {"id": "observed", "title": "Observed in recorded traffic",
     "caveat": "Seen on the wire.", "order": 0, "observed": True},
    {"id": "derived", "title": "Derived from source",
     "caveat": "Read out of the implementation.", "order": 1, "observed": False},
]

ARTIFACTS = {"kind": "provider component",
             "kinds": {"resource": "Resource", "datasource": "Data source"}}

CALL = {"spec": "ppapi", "operation": "environmentmanagement_getEnvironment",
        "coverage": "full", "grade": "observed"}

ITEM = {"id": "powerplatform_environment", "kind": "resource",
        "name": "powerplatform_environment",
        "source": {"path": "internal/services/environment/resource.go", "line": 412},
        "calls": [CALL,
                  {"spec": "bapi", "method": "get", "path": "/v1/environments",
                   "coverage": "partial", "grade": "derived",
                   "note": "Only when location changed."}]}

VALID = {"artifacts": ARTIFACTS, "grades": GRADES, "items": [ITEM]}

DROP = object()  # amend(x, key=DROP) removes the key rather than setting it


def amend(base, **changes):
    out = copy.deepcopy(base)
    for key, value in changes.items():
        if value is DROP:
            out.pop(key, None)
        else:
            out[key] = value
    return out


def document(**changes):
    return amend(VALID, **changes)


def with_grades(*grades):
    """A document whose only interesting part is its grade block. items is empty
    so that a broken grade block cannot be mistaken for its own consequences."""
    return document(grades=list(grades), items=[])


def one_item(**changes):
    return document(items=[amend(ITEM, **changes)])


def one_call(**changes):
    """A document with a single item making a single call, mutated as asked."""
    return document(items=[amend(ITEM, calls=[amend(CALL, **changes)])])


class ValidatorCase(unittest.TestCase):

    def findings(self, doc, spec_ids=None):
        return validate_coverage.validate(doc, FILE, spec_ids, CATALOGUE)

    def paths(self, findings):
        out = []
        for finding in findings:
            head, path, rest = finding.split(": ", 2)
            self.assertEqual(head, FILE, f"finding does not name the file: {finding}")
            self.assertIn("expected ", rest, f"finding says nothing about what was expected: {finding}")
            self.assertIn("; found ", rest, f"finding says nothing about what was found: {finding}")
            out.append(path)
        return out

    def assertClean(self, doc, spec_ids=None):
        findings = self.findings(doc, spec_ids)
        self.assertEqual(findings, [], "a conformant document was rejected")

    def assertRejectedAt(self, doc, *expected_paths, spec_ids=None):
        """Rejected, and the findings name exactly these paths and no others."""
        findings = self.findings(doc, spec_ids)
        self.assertTrue(findings, "a violating document was accepted")
        self.assertEqual(sorted(self.paths(findings)), sorted(expected_paths))
        return findings


class AConformantDocumentPasses(ValidatorCase):
    """The reference point. Without this every rejection below is consistent with
    a checker that rejects everything."""

    def test_the_worked_example_from_the_contract_validates(self):
        self.assertClean(VALID)

    def test_a_single_grade_corpus_validates(self):
        # A corpus with one grade and a corpus with five must both work, so the
        # two-grade shape above must not be load-bearing.
        self.assertClean(with_grades(GRADES[0]))

    def test_nothing_in_the_vocabulary_is_hardcoded(self):
        # The whole point of deriving. A document sharing no id with the worked
        # example, in either vocabulary, is just as conformant.
        doc = {
            "artifacts": {"kind": "helm chart", "kinds": {"chart": "Chart"}},
            "grades": [{"id": "attested", "title": "Attested", "caveat": "x.",
                        "order": 7, "observed": True}],
            "items": [{"id": "ingress", "kind": "chart",
                       "calls": [{"spec": "gateway", "operation": "listRoutes",
                                  "coverage": "partial", "grade": "attested"}]}],
        }
        self.assertClean(doc)


class GradeDeclarations(ValidatorCase):

    def test_grades_absent(self):
        self.assertRejectedAt(amend(with_grades(), grades=DROP), "grades")

    def test_grades_empty(self):
        self.assertRejectedAt(with_grades(), "grades")

    def test_grades_not_an_array(self):
        self.assertRejectedAt(document(grades={"observed": {}}, items=[]), "grades")

    def test_grade_missing_id(self):
        self.assertRejectedAt(with_grades(amend(GRADES[0], id=DROP)), "grades[0].id")

    def test_grade_id_empty(self):
        self.assertRejectedAt(with_grades(amend(GRADES[0], id="  ")), "grades[0].id")

    def test_grade_missing_title(self):
        self.assertRejectedAt(with_grades(amend(GRADES[0], title=DROP)), "grades[0].title")

    def test_grade_missing_caveat(self):
        self.assertRejectedAt(with_grades(amend(GRADES[0], caveat=DROP)), "grades[0].caveat")

    def test_grade_order_is_a_string(self):
        self.assertRejectedAt(with_grades(amend(GRADES[0], order="0")), "grades[0].order")

    def test_grade_order_is_a_boolean(self):
        # Python calls True an int. JSON does not, and a grade ordered `true`
        # is not an ordered grade.
        self.assertRejectedAt(with_grades(amend(GRADES[0], order=True)), "grades[0].order")

    def test_grade_observed_is_a_string(self):
        # "true" is the shape this fails in when a corpus is generated by a
        # templating step, and it is exactly the x-probe-verified defect.
        self.assertRejectedAt(with_grades(amend(GRADES[0], observed="true")), "grades[0].observed",
                              "grades")

    def test_duplicate_grade_ids(self):
        self.assertRejectedAt(
            with_grades(GRADES[0], amend(GRADES[1], id="observed")), "grades[1].id")

    def test_duplicate_grade_orders(self):
        self.assertRejectedAt(
            with_grades(GRADES[0], amend(GRADES[1], order=0)), "grades[1].order")

    def test_no_grade_is_observed(self):
        self.assertRejectedAt(with_grades(amend(GRADES[0], observed=False), GRADES[1]), "grades")

    def test_two_grades_are_observed(self):
        self.assertRejectedAt(with_grades(GRADES[0], amend(GRADES[1], observed=True)), "grades")

    def test_the_observed_finding_names_both_offenders(self):
        # The count alone is not actionable in a corpus with five grades.
        findings = self.findings(with_grades(GRADES[0], amend(GRADES[1], observed=True)))
        self.assertIn("grades[0].observed", findings[0])
        self.assertIn("grades[1].observed", findings[0])


class ArtifactDeclarations(ValidatorCase):

    def test_artifacts_absent(self):
        self.assertRejectedAt(document(artifacts=DROP), "artifacts")

    def test_artifacts_not_an_object(self):
        self.assertRejectedAt(document(artifacts=["resource"]), "artifacts")

    def test_kind_absent(self):
        self.assertRejectedAt(document(artifacts=amend(ARTIFACTS, kind=DROP)), "artifacts.kind")

    def test_kind_empty(self):
        self.assertRejectedAt(document(artifacts=amend(ARTIFACTS, kind="")), "artifacts.kind")

    def test_kinds_absent(self):
        self.assertRejectedAt(document(artifacts=amend(ARTIFACTS, kinds=DROP)), "artifacts.kinds")

    def test_kinds_empty(self):
        self.assertRejectedAt(document(artifacts=amend(ARTIFACTS, kinds={})), "artifacts.kinds")

    def test_kinds_is_an_array_of_ids(self):
        # The plausible wrong shape: a list of kind ids with no labels.
        self.assertRejectedAt(document(artifacts=amend(ARTIFACTS, kinds=["resource"])),
                              "artifacts.kinds")

    def test_kind_label_is_not_a_string(self):
        self.assertRejectedAt(
            document(artifacts=amend(ARTIFACTS, kinds={"resource": {"label": "Resource"}})),
            "artifacts.kinds.resource", "items[0].kind")


class ItemIdentity(ValidatorCase):

    def test_items_absent(self):
        self.assertRejectedAt(document(items=DROP), "items")

    def test_items_not_an_array(self):
        self.assertRejectedAt(document(items={}), "items")

    def test_item_id_absent(self):
        self.assertRejectedAt(one_item(id=DROP), "items[0].id")

    def test_item_id_empty(self):
        self.assertRejectedAt(one_item(id=""), "items[0].id")

    def test_duplicate_item_ids(self):
        self.assertRejectedAt(document(items=[ITEM, copy.deepcopy(ITEM)]), "items[1].id")

    def test_the_duplicate_finding_names_the_first_use(self):
        findings = self.findings(document(items=[ITEM, copy.deepcopy(ITEM)]))
        self.assertIn("items[0].id", findings[0])

    def test_item_kind_is_undeclared(self):
        self.assertRejectedAt(one_item(kind="module"), "items[0].kind")

    def test_item_kind_absent(self):
        self.assertRejectedAt(one_item(kind=DROP), "items[0].kind")

    def test_the_kind_finding_lists_what_was_declared(self):
        # Derived from artifacts.kinds, so the reader is told the answer rather
        # than sent to look for it.
        findings = self.findings(one_item(kind="module"))
        self.assertIn('"resource"', findings[0])
        self.assertIn('"datasource"', findings[0])
        self.assertIn("artifacts.kinds", findings[0])


class ItemSource(ValidatorCase):

    def test_source_path_is_absolute(self):
        self.assertRejectedAt(
            one_item(source={"path": "/Users/adam/provider/resource.go"}),
            "items[0].source.path")

    def test_source_path_is_windows_absolute(self):
        self.assertRejectedAt(
            one_item(source={"path": "C:\\provider\\resource.go"}),
            "items[0].source.path")

    def test_source_path_escapes_the_repository(self):
        self.assertRejectedAt(
            one_item(source={"path": "../other-repo/resource.go"}),
            "items[0].source.path")

    def test_source_path_escapes_partway_along(self):
        self.assertRejectedAt(
            one_item(source={"path": "internal/../../resource.go"}),
            "items[0].source.path")

    def test_source_path_absent(self):
        self.assertRejectedAt(one_item(source={"line": 1}), "items[0].source.path")

    def test_source_line_is_zero(self):
        self.assertRejectedAt(
            one_item(source={"path": "resource.go", "line": 0}), "items[0].source.line")

    def test_source_line_is_negative(self):
        self.assertRejectedAt(
            one_item(source={"path": "resource.go", "line": -3}), "items[0].source.line")

    def test_source_line_is_a_string(self):
        self.assertRejectedAt(
            one_item(source={"path": "resource.go", "line": "412"}), "items[0].source.line")

    def test_source_is_not_an_object(self):
        self.assertRejectedAt(one_item(source="resource.go"), "items[0].source")


class CallOperationIdentity(ValidatorCase):
    """A call names its operation exactly one of two ways. Both forms at once is
    not redundancy: it is two claims with nothing to reconcile them."""

    def test_both_forms_at_once(self):
        self.assertRejectedAt(
            one_call(method="get", path="/v1/environments"), "items[0].calls[0]")

    def test_operation_with_only_a_method(self):
        self.assertRejectedAt(one_call(method="get"), "items[0].calls[0]")

    def test_neither_form(self):
        self.assertRejectedAt(one_call(operation=DROP), "items[0].calls[0]")

    def test_method_without_path(self):
        findings = self.assertRejectedAt(
            one_call(operation=DROP, method="get"), "items[0].calls[0].path")
        # Not merely "expected a string". Half of this form is a call that named
        # its operation neither way, and saying so is the difference between a
        # reader adding the missing half and a reader retyping what is there.
        self.assertIn("identifies nothing", findings[0])

    def test_path_without_method(self):
        findings = self.assertRejectedAt(
            one_call(operation=DROP, path="/v1/environments"), "items[0].calls[0].method")
        self.assertIn("identifies nothing", findings[0])

    def test_operation_is_empty(self):
        self.assertRejectedAt(one_call(operation=""), "items[0].calls[0].operation")

    def test_operation_is_not_a_string(self):
        self.assertRejectedAt(one_call(operation=412), "items[0].calls[0].operation")

    def test_method_is_not_a_string(self):
        self.assertRejectedAt(
            one_call(operation=DROP, method=None, path="/v1/environments"),
            "items[0].calls[0].method")

    def test_path_is_empty(self):
        self.assertRejectedAt(
            one_call(operation=DROP, method="get", path="  "), "items[0].calls[0].path")


class CallFields(ValidatorCase):

    def test_spec_absent(self):
        self.assertRejectedAt(one_call(spec=DROP), "items[0].calls[0].spec")

    def test_spec_empty(self):
        self.assertRejectedAt(one_call(spec=""), "items[0].calls[0].spec")

    def test_coverage_absent(self):
        self.assertRejectedAt(one_call(coverage=DROP), "items[0].calls[0].coverage")

    def test_coverage_is_an_undefined_word(self):
        self.assertRejectedAt(one_call(coverage="none"), "items[0].calls[0].coverage")

    def test_coverage_is_capitalised(self):
        self.assertRejectedAt(one_call(coverage="Full"), "items[0].calls[0].coverage")

    def test_the_coverage_finding_admits_it_carries_a_remembered_value(self):
        # The one literal vocabulary in the checker. A rotted literal rejects
        # correct data and reads as a data defect, so somebody edits the corpus
        # to match the checker and the edit looks like a conformance fix. The
        # message has to name the other possibility, because it is the only part
        # of this file the person meeting the failure will read.
        findings = self.findings(one_call(coverage="none"))
        self.assertIn("out of date", findings[0])

    def test_grade_is_undeclared(self):
        self.assertRejectedAt(one_call(grade="pac-cli"), "items[0].calls[0].grade")

    def test_grade_absent(self):
        self.assertRejectedAt(one_call(grade=DROP), "items[0].calls[0].grade")

    def test_the_grade_finding_lists_what_the_document_declared(self):
        findings = self.findings(one_call(grade="pac-cli"))
        self.assertIn('"observed"', findings[0])
        self.assertIn('"derived"', findings[0])
        self.assertIn("grades", findings[0])

    def test_note_is_not_a_string(self):
        self.assertRejectedAt(one_call(note=["Only when location changed."]),
                              "items[0].calls[0].note")

    def test_call_is_not_an_object(self):
        self.assertRejectedAt(document(items=[amend(ITEM, calls=["ppapi"])]),
                              "items[0].calls[0]")

    def test_calls_is_not_an_array(self):
        self.assertRejectedAt(one_item(calls={"spec": "ppapi"}), "items[0].calls")


class DuplicateCalls(ValidatorCase):

    def test_the_same_operation_twice_in_one_item(self):
        self.assertRejectedAt(
            document(items=[amend(ITEM, calls=[CALL, copy.deepcopy(CALL)])]),
            "items[0].calls[1]")

    def test_the_same_operation_under_a_different_grade_is_still_a_duplicate(self):
        # Identity is the operation, not the whole call. Two rows claiming
        # different grades for one operation is the contradiction the coverage
        # view exists to surface, and it cannot render both.
        self.assertRejectedAt(
            document(items=[amend(ITEM, calls=[CALL, amend(CALL, grade="derived",
                                                           coverage="partial")])]),
            "items[0].calls[1]")

    def test_the_same_method_and_path_twice(self):
        pair = {"spec": "bapi", "method": "get", "path": "/v1/environments",
                "coverage": "full", "grade": "observed"}
        self.assertRejectedAt(
            document(items=[amend(ITEM, calls=[pair, copy.deepcopy(pair)])]),
            "items[0].calls[1]")

    def test_a_method_spelled_in_another_case_is_still_a_duplicate(self):
        pair = {"spec": "bapi", "method": "get", "path": "/v1/environments",
                "coverage": "full", "grade": "observed"}
        self.assertRejectedAt(
            document(items=[amend(ITEM, calls=[pair, amend(pair, method="GET")])]),
            "items[0].calls[1]")

    def test_the_duplicate_finding_names_the_first_occurrence(self):
        findings = self.findings(document(items=[amend(ITEM, calls=[CALL, copy.deepcopy(CALL)])]))
        self.assertIn("items[0].calls[0]", findings[0])

    def test_the_same_operation_in_two_items_is_not_a_duplicate(self):
        # Two artifacts calling one operation is the normal case, and forbidding
        # it would reject most real mappings.
        self.assertClean(document(items=[ITEM, amend(ITEM, id="powerplatform_environments")]))

    def test_the_same_operation_id_in_two_specs_is_not_a_duplicate(self):
        # Operation ids are unique within a spec, not across a corpus. Ignoring
        # the spec here would reject two genuinely different operations.
        self.assertClean(document(items=[amend(ITEM, calls=[CALL, amend(CALL, spec="bapi")])]))


class CatalogueAgreement(ValidatorCase):
    """The catalogue check is optional, and only the calls' spec ids are checked
    against it."""

    def test_a_spec_absent_from_the_catalogue(self):
        self.assertRejectedAt(VALID, "items[0].calls[1].spec", spec_ids={"ppapi"})

    def test_every_spec_present_passes(self):
        self.assertClean(VALID, spec_ids={"ppapi", "bapi", "dataverse"})

    def test_the_finding_lists_the_catalogue_and_its_ids(self):
        findings = self.findings(VALID, spec_ids={"ppapi"})
        self.assertIn(CATALOGUE, findings[0])
        self.assertIn('"ppapi"', findings[0])

    def test_no_catalogue_means_no_spec_check(self):
        # Not the same as an empty catalogue. Omitting --catalogue must not
        # quietly assert that every spec id is wrong.
        self.assertClean(VALID)


class CatalogueShapes(ValidatorCase):
    """Both catalogue shapes are accepted deliberately: a bare top-level array is
    the legacy form with no version field to detect, and the object form exists
    because a bare array has nowhere to put a default or an index. Detecting the
    shape is derived where a version field would be remembered."""

    def ids(self, catalogue):
        report = validate_coverage.Report(CATALOGUE)
        return validate_coverage.catalogue_spec_ids(report, catalogue), report.findings

    def test_the_bare_array_form(self):
        ids, findings = self.ids([{"id": "ppapi"}, {"id": "bapi"}])
        self.assertEqual(ids, {"ppapi", "bapi"})
        self.assertEqual(findings, [])

    def test_the_object_form(self):
        ids, findings = self.ids({"default": "ppapi", "index": "index.json",
                                  "specs": [{"id": "ppapi"}, {"id": "bapi"}]})
        self.assertEqual(ids, {"ppapi", "bapi"})
        self.assertEqual(findings, [])

    def test_both_shapes_agree(self):
        # The adjacent question: each shape being internally consistent is not
        # the same as the two shapes meaning the same thing.
        entries = [{"id": "ppapi", "title": "A"}, {"id": "bapi", "title": "B"}]
        bare, _ = self.ids(entries)
        wrapped, _ = self.ids({"default": "ppapi", "specs": copy.deepcopy(entries)})
        self.assertEqual(bare, wrapped)

    def test_an_object_with_no_specs_array(self):
        ids, findings = self.ids({"default": "ppapi"})
        self.assertIsNone(ids)
        self.assertTrue(findings)
        self.assertIn("specs", findings[0])

    def test_an_entry_with_no_id(self):
        ids, findings = self.ids([{"title": "Nameless"}])
        self.assertTrue(findings)
        self.assertIn("[0].id", findings[0])

    def test_a_catalogue_that_is_neither_shape(self):
        ids, findings = self.ids("ppapi")
        self.assertIsNone(ids)
        self.assertTrue(findings)


class EveryFindingIsReported(ValidatorCase):
    """Not one per run. A validator that stops at the first error transfers
    triage to whoever runs it: they learn the true size of the problem only
    after N runs of the build."""

    def test_a_document_wrong_in_many_ways_reports_all_of_them(self):
        doc = {
            "artifacts": {"kind": "", "kinds": {"resource": "Resource"}},
            "grades": [amend(GRADES[0], caveat=DROP), amend(GRADES[1], observed=True)],
            "items": [
                {"id": "one", "kind": "module",
                 "source": {"path": "/absolute/resource.go"},
                 "calls": [{"spec": "ppapi", "coverage": "some", "grade": "hearsay"}]},
                {"id": "one", "kind": "resource", "calls": []},
            ],
        }
        findings = self.findings(doc)
        self.assertEqual(sorted(self.paths(findings)), sorted([
            "artifacts.kind",
            "grades",                       # two grades claim observed
            "grades[0].caveat",
            "items[0].kind",
            "items[0].source.path",
            "items[0].calls[0]",            # names its operation neither way
            "items[0].calls[0].coverage",
            "items[0].calls[0].grade",
            "items[1].id",
        ]))

    def test_a_broken_grade_block_does_not_bury_itself_under_its_consequences(self):
        # The cascade guard. With no readable grade declaration, every call in
        # the document cites an undeclared grade, and reporting all of them
        # would be correct and useless.
        findings = self.findings(document(grades=[]))
        self.assertEqual(self.paths(findings), ["grades"])

    def test_a_broken_kinds_block_does_not_bury_itself_either(self):
        findings = self.findings(document(artifacts=amend(ARTIFACTS, kinds={})))
        self.assertEqual(self.paths(findings), ["artifacts.kinds"])


class WhereItDeliberatelyStaysSilent(ValidatorCase):
    """This checker's stated error direction is over-firing, so this is the class
    that proves that direction specifically.

    Each of these is a place where the format states no rule. A checker that
    invented one here would reject correct data, and the failure would read as a
    data defect rather than as a stale checker, so somebody would edit the corpus
    to match. That is the failure this repository's handover calls worse than no
    check at all.
    """

    def test_an_unfamiliar_http_method_is_not_a_finding(self):
        # There is no declared method vocabulary, so a literal verb list would
        # be the second remembered value in the file, and it would reject PATCH
        # the first time somebody used it, or a WebDAV verb, or an extension.
        self.assertClean(one_call(operation=DROP, method="patch", path="/v1/environments"))

    def test_an_item_with_no_calls_is_not_a_finding(self):
        # An artifact known to map to nothing yet is a legitimate state, and the
        # alternative is a corpus that omits it and looks complete.
        self.assertClean(one_item(calls=DROP))

    def test_an_item_with_an_empty_call_list_is_not_a_finding(self):
        self.assertClean(one_item(calls=[]))

    def test_an_item_with_no_source_is_not_a_finding(self):
        self.assertClean(one_item(source=DROP))

    def test_an_item_with_no_name_is_not_a_finding(self):
        self.assertClean(one_item(name=DROP))

    def test_a_source_with_no_line_is_not_a_finding(self):
        self.assertClean(one_item(source={"path": "internal/resource.go"}))

    def test_an_empty_item_list_is_not_a_finding(self):
        # A mapping that has begun and mapped nothing yet is not malformed.
        self.assertClean(document(items=[]))

    def test_unknown_keys_are_not_findings(self):
        # Do not allow-list. An allow-list silently drops every key added later,
        # and here it would reject a corpus that is ahead of this checker rather
        # than behind it.
        doc = document(items=[amend(ITEM, calls=[amend(CALL, confidence="high")],
                                    deprecated=True)])
        doc["x-generated-by"] = "map.go"
        doc["artifacts"] = amend(ARTIFACTS, plural="provider components")
        doc["grades"] = [amend(GRADES[0], tone="strong"), GRADES[1]]
        self.assertClean(doc)

    def test_a_filename_that_looks_like_a_parent_reference_is_not_a_finding(self):
        # ".." is checked as a path segment, not as a substring. A file named
        # resource..go is odd and is not an escape.
        self.assertClean(one_item(source={"path": "internal/resource..go"}))

    def test_a_dot_segment_is_not_a_finding(self):
        self.assertClean(one_item(source={"path": "./internal/resource.go"}))


class TheCommandLine(ValidatorCase):
    """End to end, because the exit code is what a content repository's CI reads
    and nothing above exercises it."""

    def run_main(self, doc, catalogue=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        target = root / FILE
        target.write_text(doc if isinstance(doc, str) else json.dumps(doc))
        argv = [str(target)]
        if catalogue is not None:
            path = root / CATALOGUE
            path.write_text(json.dumps(catalogue))
            argv += ["--catalogue", str(path)]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = validate_coverage.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_a_conformant_document_exits_zero(self):
        code, out, err = self.run_main(VALID)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("conformant", out)

    def test_a_violating_document_exits_one_with_findings_on_stderr(self):
        code, out, err = self.run_main(one_call(coverage="none"))
        self.assertEqual(code, 1)
        self.assertIn("items[0].calls[0].coverage", err)
        self.assertEqual(out, "")

    def test_the_findings_name_the_file_that_was_checked(self):
        code, out, err = self.run_main(one_call(coverage="none"))
        self.assertIn(FILE, err)

    def test_the_catalogue_is_enforced_through_the_flag(self):
        code, out, err = self.run_main(VALID, catalogue=[{"id": "ppapi"}])
        self.assertEqual(code, 1)
        self.assertIn("items[0].calls[1].spec", err)

    def test_the_object_shaped_catalogue_is_enforced_through_the_flag(self):
        code, out, err = self.run_main(
            VALID, catalogue={"default": "ppapi", "specs": [{"id": "ppapi"}, {"id": "bapi"}]})
        self.assertEqual(code, 0, err)

    def test_unparseable_json_is_a_finding_and_not_a_traceback(self):
        code, out, err = self.run_main("{\n  \"grades\": [,\n}")
        self.assertEqual(code, 1)
        self.assertIn("line 2", err)

    def test_a_missing_file_is_a_finding_and_not_a_traceback(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = validate_coverage.main([str(REPO / "no-such-coverage.json")])
        self.assertEqual(code, 1)
        self.assertIn("no-such-coverage.json", err.getvalue())

    def test_a_broken_catalogue_does_not_pass_for_a_clean_run(self):
        # An unreadable catalogue must not degrade into "no catalogue given",
        # which is the under-firing direction: the run would go green having
        # checked nothing it was asked to check.
        code, out, err = self.run_main(VALID, catalogue={"default": "ppapi"})
        self.assertEqual(code, 1)
        self.assertIn("specs", err)


if __name__ == "__main__":
    unittest.main()
