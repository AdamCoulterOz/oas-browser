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
rejecting correct data. Two of the newest rules are there specifically because
they were nearly written the other way round: a duplicate key that ignored the
entrypoint, and a path comparison that folded case. Each would have rejected real
data from the first producer to use it.

Proven by making them fail, not by being green. Every check in the validator was
disabled in turn, 75 mutations, and each one turns this file red.

The first sweep found a hole while it was being written: neutering the branch
that reports half of the method-and-path form fell through to a plain type check,
which names the same JSON path with a much worse message, so the path assertion
alone could not tell the two apart. Both tests now assert what the message says
as well, which is the thing that actually differs.

The sweep after the format changed found the same shape three more times, which
promotes it from an anecdote to the failure mode of this file. A missing
`grades.observed`, an empty call `grade` and a missing uncatalogued `reason` are
each caught twice over: once by the check that says what shape the value must
have, and again by the check that says which declared id it must name. Delete the
first and the second still fires, at the same path, telling the reader to pick
one of the declared ids when what they have is a boolean or nothing at all. Those
tests now assert the message too. Asserting the path is necessary and is not
always sufficient, because two checks can agree on where and disagree entirely on
what a reader is told.

It also found one that was not about messages: a catalogue declaring no usable
spec has to yield None rather than an empty set, and nothing here pinned the
difference. An empty set reports every call in the mapping for naming an
undeclared spec, which is the cascade the rest of this file exists to prevent.

Nothing here touches a network. The one function that would, fetch_json, is
substituted, because a conformance checker whose own suite needs a network goes
red for reasons that have nothing to do with the data it checks.

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
CATALOGUE_URL = "https://example.invalid/corpus/specs.json"

# A conformant document, and the base every mutation below starts from. It is
# deliberately not minimal: it carries both ways of naming an operation, an
# entrypoint, an api version, an optional note, an optional source line, an
# uncatalogued call and two grades, so that a mutation removing one thing leaves
# the rest exercised.
GRADES = {
    "observed": "observed",
    "vocabulary": [
        {"id": "observed", "title": "Observed in recorded traffic",
         "caveat": "Seen on the wire.", "tone": "strong"},
        {"id": "derived", "title": "Derived from source",
         "caveat": "Read out of the implementation."},
    ],
}

OBSERVED, DERIVED = GRADES["vocabulary"]

ARTIFACTS = {"kind": "provider component",
             "kinds": {"resource": "Resource", "datasource": "Data source"},
             "entrypoints": {"create": "Create", "delete": "Delete"}}

REASONS = {"polled-location": "Polled from a Location header",
           "user-supplied": "URL supplied in configuration"}

CALL = {"spec": "ppapi", "operation": "environmentmanagement_getEnvironment",
        "coverage": "full", "grade": "observed", "entrypoint": "create",
        "apiVersion": "2023-06-01"}

ITEM = {"id": "powerplatform_environment", "kind": "resource",
        "name": "powerplatform_environment",
        "source": {"path": "internal/services/environment/resource.go", "line": 412},
        "calls": [CALL,
                  {"spec": "bapi", "method": "get", "path": "/v1/environments",
                   "coverage": "partial", "grade": "derived",
                   "note": "Only when location changed."}],
        "uncatalogued": [{"reason": "polled-location", "count": 3,
                          "note": "Polled until the operation reports done."}]}

VALID = {"catalogue": CATALOGUE_URL, "artifacts": ARTIFACTS, "grades": GRADES,
         "uncatalogued": REASONS, "items": [ITEM]}

# The other repository's half. These are spec documents, not mappings: they are
# what the catalogue points at, and they are where an operation either exists or
# does not.
PPAPI_DOC = {"paths": {
    "/environments/{environmentId}": {
        "get": {"operationId": "environmentmanagement_getEnvironment"},
        "delete": {"operationId": "environmentmanagement_deleteEnvironment"}},
}}

BAPI_DOC = {"paths": {
    "/v1/environments": {"get": {"operationId": "listEnvironments"}},
}}

# The two real spellings that motivated the path rule, plus the partial-brace
# case, the catch-all surface that motivated the specificity ranking, and a pair
# that ties. The catch-all is declared first on purpose: a ranking removed in
# favour of first-match-wins would pick it, and these tests should notice.
VERSIONED_DOC = {"paths": {
    "/api/data/{apiVersion}/{entitySetName}": {
        "get": {"operationId": "records_query"}},
    "/api/data/{apiVersion}/publishers": {
        "get": {"operationId": "publishers_list"}},
    "/api/data/{apiVersion}/EntityDefinitions": {
        "get": {"operationId": "listEntityDefinitions"}},
    "/licensing/billingPolicies": {"post": {"operationId": "createBillingPolicy"}},
    "/api/EntityDefinitions(LogicalName='{}')": {
        "get": {"operationId": "getEntityDefinition"}},
    "/api/{scope}/records/{id}": {"get": {"operationId": "recordById"}},
    "/api/{scope}/{table}/latest": {"get": {"operationId": "latestOfTable"}},
}}

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


def with_grades(*vocabulary, observed="observed"):
    """A document whose only interesting part is its grade block. items is empty
    so that a broken grade block cannot be mistaken for its own consequences."""
    return document(grades={"observed": observed, "vocabulary": list(vocabulary)},
                    items=[])


def one_item(**changes):
    return document(items=[amend(ITEM, **changes)])


def one_call(**changes):
    """A document with a single item making a single call, mutated as asked."""
    return document(items=[amend(ITEM, calls=[amend(CALL, **changes)])])


def index_of(spec_document):
    return validate_coverage.operation_index(spec_document)


class ValidatorCase(unittest.TestCase):

    def findings(self, doc, spec_ids=None, operations=None):
        return validate_coverage.validate(doc, FILE, spec_ids, CATALOGUE, operations)

    def paths(self, findings):
        out = []
        for finding in findings:
            head, path, rest = finding.split(": ", 2)
            self.assertEqual(head, FILE, f"finding does not name the file: {finding}")
            self.assertIn("expected ", rest, f"finding says nothing about what was expected: {finding}")
            self.assertIn("; found ", rest, f"finding says nothing about what was found: {finding}")
            out.append(path)
        return out

    def assertClean(self, doc, spec_ids=None, operations=None):
        findings = self.findings(doc, spec_ids, operations)
        self.assertEqual(findings, [], "a conformant document was rejected")

    def assertRejectedAt(self, doc, *expected_paths, spec_ids=None, operations=None):
        """Rejected, and the findings name exactly these paths and no others."""
        findings = self.findings(doc, spec_ids, operations)
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
        self.assertClean(with_grades(OBSERVED))

    def test_nothing_in_the_vocabulary_is_hardcoded(self):
        # The whole point of deriving. A document sharing no id with the worked
        # example, in any of its four vocabularies, is just as conformant.
        doc = {
            "catalogue": "https://charts.example.invalid/specs.json",
            "artifacts": {"kind": "helm chart", "kinds": {"chart": "Chart"},
                          "entrypoints": {"install": "Install"}},
            "grades": {"observed": "attested",
                       "vocabulary": [{"id": "attested", "title": "Attested",
                                       "caveat": "x."}]},
            "uncatalogued": {"templated": "Path built at runtime"},
            "items": [{"id": "ingress", "kind": "chart",
                       "calls": [{"spec": "gateway", "operation": "listRoutes",
                                  "coverage": "partial", "grade": "attested",
                                  "entrypoint": "install"}],
                       "uncatalogued": [{"reason": "templated"}]}],
        }
        self.assertClean(doc)


class GradeDeclarations(ValidatorCase):

    def test_grades_absent(self):
        self.assertRejectedAt(amend(with_grades(), grades=DROP), "grades")

    def test_grades_is_the_older_array_shape(self):
        old = [{"id": "observed", "title": "T", "caveat": "c.", "order": 0,
                "observed": True}]
        self.assertRejectedAt(document(grades=old, items=[]), "grades")

    def test_the_older_shape_is_named_as_such(self):
        # Somebody meeting this failure has a file that was conformant last
        # month. Telling them the shape moved is the whole of the fix.
        findings = self.findings(document(grades=[], items=[]))
        self.assertIn("grades.observed", findings[0])
        self.assertIn("grades.vocabulary", findings[0])

    def test_grades_is_not_an_object(self):
        self.assertRejectedAt(document(grades="observed", items=[]), "grades")

    def test_vocabulary_absent(self):
        self.assertRejectedAt(document(grades={"observed": "observed"}, items=[]),
                              "grades.vocabulary")

    def test_vocabulary_empty(self):
        self.assertRejectedAt(with_grades(), "grades.vocabulary")

    def test_vocabulary_is_not_an_array(self):
        self.assertRejectedAt(
            document(grades={"observed": "observed", "vocabulary": {}}, items=[]),
            "grades.vocabulary")

    def test_grade_missing_id(self):
        self.assertRejectedAt(with_grades(amend(OBSERVED, id=DROP)),
                              "grades.vocabulary[0].id", "grades.observed")

    def test_grade_id_empty(self):
        self.assertRejectedAt(with_grades(amend(OBSERVED, id="  ")),
                              "grades.vocabulary[0].id", "grades.observed")

    def test_grade_missing_title(self):
        self.assertRejectedAt(with_grades(amend(OBSERVED, title=DROP)),
                              "grades.vocabulary[0].title")

    def test_grade_missing_caveat(self):
        self.assertRejectedAt(with_grades(amend(OBSERVED, caveat=DROP)),
                              "grades.vocabulary[0].caveat")

    def test_grade_is_not_an_object(self):
        self.assertRejectedAt(with_grades("observed"), "grades.vocabulary[0]",
                              "grades.observed")

    def test_duplicate_grade_ids(self):
        self.assertRejectedAt(with_grades(OBSERVED, amend(DERIVED, id="observed")),
                              "grades.vocabulary[1].id")

    def test_the_duplicate_grade_finding_names_the_first_declaration(self):
        findings = self.findings(with_grades(OBSERVED, amend(DERIVED, id="observed")))
        self.assertIn("grades.vocabulary[0].id", findings[0])

    def test_tone_is_not_a_string(self):
        self.assertRejectedAt(with_grades(amend(OBSERVED, tone=["strong"])),
                              "grades.vocabulary[0].tone")

    def test_a_grade_still_carrying_an_order(self):
        # Retired, not unknown. Unknown keys pass here; this one is flagged
        # because its author believes it still decides the ranking.
        self.assertRejectedAt(with_grades(amend(OBSERVED, order=0)),
                              "grades.vocabulary[0].order")

    def test_the_order_finding_says_what_replaced_it(self):
        findings = self.findings(with_grades(amend(OBSERVED, order=0)))
        self.assertIn("position in grades.vocabulary is the order", findings[0])

    def test_an_order_of_zero_is_still_flagged(self):
        # The falsy value. A truthiness test here would let the first grade in
        # every migrated file through, which is the one most likely to have one.
        findings = self.findings(with_grades(amend(OBSERVED, order=0)))
        self.assertEqual(self.paths(findings), ["grades.vocabulary[0].order"])

    def test_observed_absent(self):
        findings = self.assertRejectedAt(
            document(grades={"vocabulary": GRADES["vocabulary"]}, items=[]),
            "grades.observed")
        self.assertIn("naming which declared grade", findings[0])

    def test_observed_is_empty(self):
        findings = self.assertRejectedAt(with_grades(OBSERVED, observed="  "),
                                         "grades.observed")
        self.assertIn("naming which declared grade", findings[0])

    def test_observed_is_not_a_string(self):
        # "true" is the shape this failed in under the old boolean-per-grade
        # shape, when a corpus was generated by a templating step. The shape
        # changed; the templating step did not.
        #
        # The message is asserted, not just the path. Delete the shape check and
        # the reference check below catches this too, at the same path, telling
        # the reader to pick one of the declared ids when what they have is a
        # boolean. That is the trap this file's docstring records: two checks can
        # agree on where and disagree entirely on what a reader is told.
        findings = self.assertRejectedAt(with_grades(OBSERVED, observed=True),
                                         "grades.observed")
        self.assertIn("naming which declared grade", findings[0])

    def test_observed_names_an_undeclared_grade(self):
        self.assertRejectedAt(with_grades(OBSERVED, DERIVED, observed="attested"),
                              "grades.observed")

    def test_the_observed_finding_lists_what_was_declared(self):
        findings = self.findings(with_grades(OBSERVED, DERIVED, observed="attested"))
        self.assertIn('"observed"', findings[0])
        self.assertIn('"derived"', findings[0])
        self.assertIn("grades.vocabulary", findings[0])


class ArtifactDeclarations(ValidatorCase):

    def test_artifacts_absent(self):
        self.assertRejectedAt(document(artifacts=DROP), "artifacts")

    def test_artifacts_not_an_object(self):
        self.assertRejectedAt(document(artifacts=["resource"]), "artifacts")

    def test_kind_absent(self):
        self.assertRejectedAt(document(artifacts=amend(ARTIFACTS, kind=DROP)),
                              "artifacts.kind")

    def test_kind_empty(self):
        self.assertRejectedAt(document(artifacts=amend(ARTIFACTS, kind="")),
                              "artifacts.kind")

    def test_kinds_absent(self):
        self.assertRejectedAt(document(artifacts=amend(ARTIFACTS, kinds=DROP)),
                              "artifacts.kinds")

    def test_kinds_empty(self):
        self.assertRejectedAt(document(artifacts=amend(ARTIFACTS, kinds={})),
                              "artifacts.kinds")

    def test_kinds_is_an_array_of_ids(self):
        # The plausible wrong shape: a list of kind ids with no labels.
        self.assertRejectedAt(document(artifacts=amend(ARTIFACTS, kinds=["resource"])),
                              "artifacts.kinds")

    def test_kind_label_is_not_a_string(self):
        self.assertRejectedAt(
            document(artifacts=amend(ARTIFACTS, kinds={"resource": {"label": "Resource"}})),
            "artifacts.kinds.resource", "items[0].kind")

    def test_kind_id_is_empty(self):
        self.assertRejectedAt(
            document(artifacts=amend(ARTIFACTS, kinds={"": "Resource"})),
            'artifacts.kinds.""', "items[0].kind")

    def test_entrypoints_empty(self):
        self.assertRejectedAt(document(artifacts=amend(ARTIFACTS, entrypoints={})),
                              "artifacts.entrypoints")

    def test_entrypoints_is_an_array_of_ids(self):
        self.assertRejectedAt(
            document(artifacts=amend(ARTIFACTS, entrypoints=["create"])),
            "artifacts.entrypoints")

    def test_entrypoint_label_is_not_a_string(self):
        self.assertRejectedAt(
            document(artifacts=amend(ARTIFACTS, entrypoints={"create": 1})),
            "artifacts.entrypoints.create", "items[0].calls[0].entrypoint")

    def test_a_broken_entrypoints_block_does_not_bury_itself(self):
        # The same cascade guard the kinds block gets. An unreadable declaration
        # makes every call citing an entrypoint wrong, and the cause is one line.
        findings = self.findings(document(artifacts=amend(ARTIFACTS, entrypoints=[])))
        self.assertEqual(self.paths(findings), ["artifacts.entrypoints"])


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

    def test_item_is_not_an_object(self):
        self.assertRejectedAt(document(items=["powerplatform_environment"]), "items[0]")


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

    def test_method_is_upper_case(self):
        findings = self.assertRejectedAt(
            one_call(operation=DROP, method="GET", path="/v1/environments"),
            "items[0].calls[0].method")
        self.assertIn("lowercase", findings[0])

    def test_the_method_finding_names_the_normal_form(self):
        # Refusing what was written without naming what to write instead makes
        # the reader guess whether the rule is lowercase, uppercase, or a list.
        findings = self.findings(
            one_call(operation=DROP, method="Get", path="/v1/environments"))
        self.assertIn('"get"', findings[0])


class CallEntrypoints(ValidatorCase):
    """An artifact may invoke different operations depending on which of its
    named entrypoints ran. The id has to name one the document declares."""

    def test_an_undeclared_entrypoint(self):
        self.assertRejectedAt(one_call(entrypoint="update"),
                              "items[0].calls[0].entrypoint")

    def test_the_entrypoint_finding_lists_what_was_declared(self):
        findings = self.findings(one_call(entrypoint="update"))
        self.assertIn('"create"', findings[0])
        self.assertIn('"delete"', findings[0])
        self.assertIn("artifacts.entrypoints", findings[0])

    def test_an_entrypoint_when_the_document_declares_none(self):
        doc = document(artifacts=amend(ARTIFACTS, entrypoints=DROP))
        self.assertRejectedAt(doc, "items[0].calls[0].entrypoint")

    def test_that_finding_names_the_missing_declaration_rather_than_the_id(self):
        # The fix is a declaration, not a different id, and a message listing
        # valid ids would be a message listing nothing.
        findings = self.findings(document(artifacts=amend(ARTIFACTS, entrypoints=DROP)))
        self.assertIn("artifacts.entrypoints", findings[0])
        self.assertIn("declares none", findings[0])

    def test_an_empty_entrypoint(self):
        self.assertRejectedAt(one_call(entrypoint="  "), "items[0].calls[0].entrypoint")

    def test_an_entrypoint_that_is_not_a_string(self):
        self.assertRejectedAt(one_call(entrypoint=["create"]),
                              "items[0].calls[0].entrypoint")


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

    def test_the_coverage_finding_says_a_third_value_means_a_new_axis(self):
        # This message used to hedge that the checker might be out of date,
        # because the pair is the one vocabulary a document cannot declare. The
        # hedge is withdrawn: full and partial are a closed binary, and inviting
        # a reader to widen the enum invites them to collapse two questions onto
        # one word. What the message must now do is name the other repair.
        findings = self.findings(one_call(coverage="none"))
        self.assertIn("axis", findings[0])
        self.assertIn("closed binary", findings[0])

    def test_the_coverage_finding_no_longer_hedges(self):
        # Asserting the absence, because the reversal is the point. A message
        # carrying both readings would tell the reader to widen the enum and to
        # add an axis, which is worse than either.
        findings = self.findings(one_call(coverage="none"))
        self.assertNotIn("out of date", findings[0])

    def test_grade_is_undeclared(self):
        self.assertRejectedAt(one_call(grade="pac-cli"), "items[0].calls[0].grade")

    def test_grade_absent(self):
        findings = self.assertRejectedAt(one_call(grade=DROP), "items[0].calls[0].grade")
        self.assertIn("a non-empty string naming a declared grade", findings[0])

    def test_grade_is_empty(self):
        findings = self.assertRejectedAt(one_call(grade=""), "items[0].calls[0].grade")
        self.assertIn("a non-empty string naming a declared grade", findings[0])

    def test_the_grade_finding_lists_what_the_document_declared(self):
        findings = self.findings(one_call(grade="pac-cli"))
        self.assertIn('"observed"', findings[0])
        self.assertIn('"derived"', findings[0])
        self.assertIn("grades.vocabulary", findings[0])

    def test_api_version_is_empty(self):
        self.assertRejectedAt(one_call(apiVersion=""), "items[0].calls[0].apiVersion")

    def test_api_version_is_not_a_string(self):
        self.assertRejectedAt(one_call(apiVersion=2023), "items[0].calls[0].apiVersion")

    def test_the_api_version_finding_says_absence_is_allowed(self):
        # It is an annotation. A reader told only that the value is wrong may
        # conclude the key is required and invent one.
        findings = self.findings(one_call(apiVersion=""))
        self.assertIn("no apiVersion at all", findings[0])

    def test_approximate_is_true(self):
        self.assertClean(one_call(approximate=True))

    def test_approximate_is_false(self):
        self.assertClean(one_call(approximate=False))

    def test_approximate_is_not_a_boolean(self):
        self.assertRejectedAt(one_call(approximate="yes"),
                              "items[0].calls[0].approximate")

    def test_approximate_is_a_number(self):
        # The other shape a templating step produces, and 0 is falsy, so a
        # truthiness test here would read a flagged row as an unflagged one.
        self.assertRejectedAt(one_call(approximate=0),
                              "items[0].calls[0].approximate")

    def test_note_is_not_a_string(self):
        self.assertRejectedAt(one_call(note=["Only when location changed."]),
                              "items[0].calls[0].note")

    def test_call_is_not_an_object(self):
        self.assertRejectedAt(document(items=[amend(ITEM, calls=["ppapi"])]),
                              "items[0].calls[0]")

    def test_calls_is_not_an_array(self):
        self.assertRejectedAt(one_item(calls={"spec": "ppapi"}), "items[0].calls")


class UncataloguedCalls(ValidatorCase):
    """Calls an artifact makes that no catalogue operation names. A coverage view
    silently omitting a fifth of what an artifact does looks exactly like a
    complete one, which is why these are recorded rather than dropped."""

    def entries(self, *entries):
        return document(items=[amend(ITEM, uncatalogued=list(entries))])

    def test_reason_absent(self):
        # The message, not only the path. Without the shape check the vocabulary
        # check reports the same location and tells the reader to choose one of
        # the declared reasons, which is not the fix when there is no reason at
        # all.
        findings = self.assertRejectedAt(self.entries({"count": 2}),
                                         "items[0].uncatalogued[0].reason")
        self.assertIn("records nothing except why it is one", findings[0])

    def test_reason_empty(self):
        findings = self.assertRejectedAt(self.entries({"reason": ""}),
                                         "items[0].uncatalogued[0].reason")
        self.assertIn("records nothing except why it is one", findings[0])

    def test_reason_is_undeclared(self):
        self.assertRejectedAt(self.entries({"reason": "who-knows"}),
                              "items[0].uncatalogued[0].reason")

    def test_the_reason_finding_lists_what_was_declared(self):
        findings = self.findings(self.entries({"reason": "who-knows"}))
        self.assertIn('"polled-location"', findings[0])
        self.assertIn('"user-supplied"', findings[0])
        self.assertIn("uncatalogued", findings[0])

    def test_entries_with_no_declaration_map(self):
        doc = amend(self.entries({"reason": "polled-location"}), uncatalogued=DROP)
        self.assertRejectedAt(doc, "uncatalogued")

    def test_that_finding_names_the_entry_that_needed_it(self):
        # One finding for one cause, and the cause is at the top of the file
        # while the evidence for it is several hundred lines down.
        doc = amend(self.entries({"reason": "polled-location"}), uncatalogued=DROP)
        findings = self.findings(doc)
        self.assertIn("items[0].uncatalogued[0].reason", findings[0])

    def test_a_missing_declaration_is_reported_once_not_once_per_entry(self):
        # The cascade guard for this axis. A producer's extractor emits these in
        # bulk, and a few hundred copies of one sentence is a worse failure than
        # the one it describes.
        doc = document(uncatalogued=DROP, items=[
            amend(ITEM, uncatalogued=[{"reason": "polled-location"},
                                      {"reason": "user-supplied"}]),
            amend(ITEM, id="other", uncatalogued=[{"reason": "polled-location"}]),
        ])
        findings = self.findings(doc)
        self.assertEqual(self.paths(findings), ["uncatalogued"])

    def test_count_is_zero(self):
        self.assertRejectedAt(
            self.entries({"reason": "polled-location", "count": 0}),
            "items[0].uncatalogued[0].count")

    def test_count_is_negative(self):
        self.assertRejectedAt(
            self.entries({"reason": "polled-location", "count": -1}),
            "items[0].uncatalogued[0].count")

    def test_count_is_a_string(self):
        self.assertRejectedAt(
            self.entries({"reason": "polled-location", "count": "3"}),
            "items[0].uncatalogued[0].count")

    def test_count_is_a_boolean(self):
        # Python calls True an int. JSON does not, and a call site counted
        # `true` is not a counted call site.
        self.assertRejectedAt(
            self.entries({"reason": "polled-location", "count": True}),
            "items[0].uncatalogued[0].count")

    def test_note_is_not_a_string(self):
        self.assertRejectedAt(
            self.entries({"reason": "polled-location", "note": ["polled"]}),
            "items[0].uncatalogued[0].note")

    def test_an_entry_is_not_an_object(self):
        self.assertRejectedAt(self.entries("polled-location"),
                              "items[0].uncatalogued[0]")

    def test_uncatalogued_is_not_an_array_on_the_item(self):
        self.assertRejectedAt(one_item(uncatalogued={"reason": "polled-location"}),
                              "items[0].uncatalogued")

    def test_the_declaration_map_is_empty(self):
        self.assertRejectedAt(document(uncatalogued={}), "uncatalogued")

    def test_the_declaration_map_is_an_array_of_ids(self):
        self.assertRejectedAt(document(uncatalogued=["polled-location"]), "uncatalogued")

    def test_a_declared_reason_has_no_label(self):
        self.assertRejectedAt(
            document(uncatalogued={"polled-location": ""}),
            "uncatalogued.polled-location", "items[0].uncatalogued[0].reason")


class DuplicateCalls(ValidatorCase):
    """Identity is (spec, entrypoint, operation). Every part of that is there
    because leaving it out rejects real data, or because putting it in would."""

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
        # Two findings, and both are wanted: the second row is not normalised,
        # and it is also the same row twice. Case-folding the comparison is what
        # keeps the second one from being missed once the first is fixed.
        pair = {"spec": "bapi", "method": "get", "path": "/v1/environments",
                "coverage": "full", "grade": "observed"}
        self.assertRejectedAt(
            document(items=[amend(ITEM, calls=[pair, amend(pair, method="GET")])]),
            "items[0].calls[1]", "items[0].calls[1].method")

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

    def test_the_same_operation_from_two_entrypoints_is_not_a_duplicate(self):
        # The case the entrypoint axis exists for, and the one that would have
        # made this checker reject correct data. A component reaching one
        # operation from its create and its delete path is two rows, and which
        # phase is the useful fact.
        self.assertClean(
            document(items=[amend(ITEM, calls=[CALL, amend(CALL, entrypoint="delete")])]))

    def test_the_same_operation_from_the_same_entrypoint_is_a_duplicate(self):
        self.assertRejectedAt(
            document(items=[amend(ITEM, calls=[CALL, amend(CALL, coverage="partial")])]),
            "items[0].calls[1]")

    def test_two_calls_with_no_entrypoint_are_still_duplicates(self):
        bare = amend(CALL, entrypoint=DROP)
        self.assertRejectedAt(
            document(items=[amend(ITEM, calls=[bare, copy.deepcopy(bare)])]),
            "items[0].calls[1]")

    def test_one_with_an_entrypoint_and_one_without_are_not_duplicates(self):
        # Absent is its own value, not a wildcard. A wildcard would make the
        # first row that omits the key collide with every row that names one.
        bare = amend(CALL, entrypoint=DROP)
        self.assertClean(document(items=[amend(ITEM, calls=[bare, CALL])]))

    def test_two_api_versions_of_one_operation_are_still_a_duplicate(self):
        # apiVersion is an annotation, not a disambiguator. Two calls to one
        # operation at two versions are two claims about one operation, and the
        # coverage view can render one of them.
        self.assertRejectedAt(
            document(items=[amend(ITEM, calls=[CALL, amend(CALL, apiVersion="2024-01-01")])]),
            "items[0].calls[1]")

    def test_the_duplicate_finding_names_the_entrypoint(self):
        # With the entrypoint in the key, a finding that does not say which one
        # sends the reader to two rows that differ in a field it did not mention.
        findings = self.findings(
            document(items=[amend(ITEM, calls=[CALL, amend(CALL, coverage="partial")])]))
        self.assertIn('"create"', findings[0])


class CatalogueAgreement(ValidatorCase):
    """Spec ids are checked against the catalogue the mapping names."""

    def test_a_spec_absent_from_the_catalogue(self):
        self.assertRejectedAt(VALID, "items[0].calls[1].spec", spec_ids={"ppapi"})

    def test_every_spec_present_passes(self):
        self.assertClean(VALID, spec_ids={"ppapi", "bapi", "dataverse"})

    def test_the_finding_lists_the_catalogue_and_its_ids(self):
        findings = self.findings(VALID, spec_ids={"ppapi"})
        self.assertIn(CATALOGUE, findings[0])
        self.assertIn('"ppapi"', findings[0])

    def test_no_catalogue_means_no_spec_check(self):
        # Not the same as an empty catalogue. An unresolved catalogue must not
        # quietly assert that every spec id is wrong. What stops a run silently
        # skipping it is the exit code, not a finding here.
        self.assertClean(VALID)


class CatalogueOperations(ValidatorCase):
    """The operation a call names has to be one the spec describes. This is the
    check whose subject lives in the other repository."""

    def against(self, spec_document=None, **changes):
        operations = {"ppapi": index_of(spec_document or VERSIONED_DOC)}
        return document(items=[amend(ITEM, calls=[amend(CALL, **changes)],
                                     uncatalogued=DROP)]), operations

    def test_an_operation_id_the_spec_does_not_declare(self):
        doc, ops = self.against(PPAPI_DOC, operation="environmentmanagement_listAll")
        self.assertRejectedAt(doc, "items[0].calls[0].operation", operations=ops)

    def test_an_operation_id_the_spec_declares_passes(self):
        doc, ops = self.against(PPAPI_DOC)
        self.assertClean(doc, operations=ops)

    def test_an_operation_id_differing_only_in_case(self):
        doc, ops = self.against(PPAPI_DOC, operation="environmentmanagement_getenvironment")
        findings = self.assertRejectedAt(doc, "items[0].calls[0].operation", operations=ops)
        self.assertIn("differing only in case", findings[0])

    def test_a_templated_segment_matches_a_pinned_one(self):
        # The case the rule exists for: the spec templates the api version and
        # the caller pins it. Twenty-two operations in the first corpus to hit
        # this are versioned that way, so it is a class and not three rows.
        doc, ops = self.against(operation=DROP, method="get",
                                path="/api/data/v9.2/EntityDefinitions")
        self.assertClean(doc, operations=ops)

    def test_a_segment_differing_in_case_is_still_a_gap(self):
        # And this is why the comparison is not simply loosened. The caller
        # sending BillingPolicies does not reach billingPolicies, and this file's
        # whole job is describing what the code actually does.
        doc, ops = self.against(operation=DROP, method="post",
                                path="/licensing/BillingPolicies")
        self.assertRejectedAt(doc, "items[0].calls[0].path", operations=ops)

    def test_the_case_difference_is_visible_in_the_message(self):
        # "Not found" would send the reader looking for a missing operation.
        # The operation is there and their path is wrong by one letter.
        doc, ops = self.against(operation=DROP, method="post",
                                path="/licensing/BillingPolicies")
        findings = self.findings(doc, operations=ops)
        self.assertIn("differing only in case", findings[0])
        self.assertIn('"/licensing/billingPolicies"', findings[0])

    def test_a_segment_differing_in_more_than_case(self):
        doc, ops = self.against(operation=DROP, method="post",
                                path="/licensing/billing-policies")
        findings = self.assertRejectedAt(doc, "items[0].calls[0].path", operations=ops)
        self.assertNotIn("differing only in case", findings[0])

    def test_a_differing_segment_count_does_not_match(self):
        # The templated segment stands for one segment, not for a tail.
        doc, ops = self.against(operation=DROP, method="get",
                                path="/api/data/v9.2/extra/EntityDefinitions")
        self.assertRejectedAt(doc, "items[0].calls[0].path", operations=ops)

    def test_braces_inside_a_segment_are_a_template_too(self):
        doc, ops = self.against(operation=DROP, method="get",
                                path="/api/EntityDefinitions(LogicalName='account')")
        self.assertClean(doc, operations=ops)

    def test_a_catch_all_does_not_make_a_specific_row_ambiguous(self):
        # GET /api/data/v9.2/publishers matches the catch-all and the specific
        # operation, both legitimately. Without the specificity ranking every one
        # of these is ambiguous, which on the first real run was twenty-five rows
        # shadowed by one catch-all.
        doc, ops = self.against(operation=DROP, method="get",
                                path="/api/data/v9.2/publishers")
        self.assertClean(doc, operations=ops)

    def test_the_specific_path_is_the_one_it_resolved_to(self):
        # Which of the two won is otherwise invisible, so it is read out of the
        # message for a method neither declares. First-match-wins would name the
        # catch-all, which is declared first in the fixture for that reason.
        doc, ops = self.against(operation=DROP, method="delete",
                                path="/api/data/v9.2/publishers")
        findings = self.assertRejectedAt(doc, "items[0].calls[0].method", operations=ops)
        self.assertIn('"/api/data/{apiVersion}/publishers"', findings[0])

    def test_a_catch_all_matching_alone_still_resolves(self):
        # It is a real operation and not a fallback. A rule that only ever
        # resolved specific paths would report every generic surface as a gap.
        doc, ops = self.against(operation=DROP, method="get",
                                path="/api/data/v9.2/systemusers")
        self.assertClean(doc, operations=ops)

    def test_two_equally_specific_operations_are_reported_as_ambiguous(self):
        doc, ops = self.against(operation=DROP, method="get",
                                path="/api/scope/records/latest")
        self.assertRejectedAt(doc, "items[0].calls[0].path", operations=ops)

    def test_the_ambiguity_finding_names_both_candidates(self):
        # A tie is a fact about the spec, and the reader cannot act on it
        # without knowing which two operations tied.
        doc, ops = self.against(operation=DROP, method="get",
                                path="/api/scope/records/latest")
        findings = self.findings(doc, operations=ops)
        self.assertIn("items[0].calls[0].path", findings[0])
        self.assertIn('"recordById"', findings[0])
        self.assertIn('"latestOfTable"', findings[0])

    def test_a_method_the_spec_does_not_declare_on_that_path(self):
        doc, ops = self.against(operation=DROP, method="delete",
                                path="/api/data/v9.2/EntityDefinitions")
        findings = self.assertRejectedAt(doc, "items[0].calls[0].method", operations=ops)
        self.assertIn('"get"', findings[0])

    def test_a_call_naming_an_operation_never_goes_through_path_matching(self):
        # Two ways of naming an operation, and running one through the other
        # answers a question nobody asked. An operation id that happens to look
        # like a path is still resolved by id.
        doc, ops = self.against(PPAPI_DOC, operation="/environments/{environmentId}")
        findings = self.assertRejectedAt(doc, "items[0].calls[0].operation", operations=ops)
        self.assertNotIn("path", findings[0].split("expected", 1)[1])

    def test_an_approximate_row_that_does_not_resolve_is_still_a_finding(self):
        # The misuse worth defending against. `approximate` is the producer's
        # confidence in a row, not a claim about the row's validity, and letting
        # it suppress this would hand any producer a way to silence a real
        # failure by declaring uncertainty about it.
        doc, ops = self.against(PPAPI_DOC, operation="environmentmanagement_listAll",
                                approximate=True)
        self.assertRejectedAt(doc, "items[0].calls[0].operation", operations=ops)

    def test_an_approximate_row_that_resolves_is_still_clean(self):
        doc, ops = self.against(PPAPI_DOC, approximate=True)
        self.assertClean(doc, operations=ops)

    def test_a_spec_with_no_index_is_not_checked(self):
        # Only specs whose documents could be read are checked. A spec absent
        # from the index is unchecked, not wrong, and the exit code says so.
        doc, _ = self.against(PPAPI_DOC, operation="environmentmanagement_listAll")
        self.assertClean(doc, operations={"bapi": index_of(BAPI_DOC)})


class PathMatching(ValidatorCase):
    """The matching rule on its own, because it is the piece with the most ways
    to be subtly wrong and the least visible when it is."""

    def matches(self, spec_path, call_path, fold=False):
        return validate_coverage.path_matches(spec_path, call_path, fold)

    def test_identical_paths_match(self):
        self.assertTrue(self.matches("/v1/environments", "/v1/environments"))

    def test_a_templated_segment_matches_any_one_segment(self):
        self.assertTrue(self.matches("/v1/environments/{id}", "/v1/environments/abc"))

    def test_a_templated_segment_does_not_match_two_segments(self):
        self.assertFalse(self.matches("/v1/environments/{id}", "/v1/environments/a/b"))

    def test_a_templated_segment_does_not_match_an_empty_one(self):
        self.assertFalse(self.matches("/v1/environments/{id}", "/v1/environments/"))

    def test_a_literal_segment_is_case_sensitive(self):
        self.assertFalse(self.matches("/licensing/billingPolicies",
                                      "/licensing/BillingPolicies"))

    def test_and_folds_only_when_asked(self):
        self.assertTrue(self.matches("/licensing/billingPolicies",
                                     "/licensing/BillingPolicies", fold=True))

    def test_the_literal_part_of_a_partly_templated_segment_is_case_sensitive(self):
        self.assertFalse(self.matches("/api/Items(Name='{}')", "/api/items(Name='x')"))

    def test_a_partly_templated_segment_matches_a_value(self):
        self.assertTrue(self.matches("/api/Items(Name='{}')", "/api/Items(Name='x')"))

    def test_regex_characters_in_a_literal_segment_are_literal(self):
        # The pattern is built, so a segment containing regex punctuation must
        # not quietly become a pattern of its own.
        self.assertTrue(self.matches("/api/a.b", "/api/a.b"))
        self.assertFalse(self.matches("/api/a.b", "/api/axb"))

    def test_a_shorter_path_does_not_match(self):
        self.assertFalse(self.matches("/v1/environments/{id}", "/v1/environments"))


class CatalogueShapes(ValidatorCase):
    """Both catalogue shapes are accepted deliberately: a bare top-level array is
    the legacy form with no version field to detect, and the object form exists
    because a bare array has nowhere to put a default or an index. Detecting the
    shape is derived where a version field would be remembered."""

    def ids(self, catalogue):
        report = validate_coverage.Report(CATALOGUE)
        entries = validate_coverage.catalogue_entries(report, catalogue)
        declared = None if entries is None else {sid for sid, _ in entries}
        return declared, report.findings

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

    def test_a_catalogue_declaring_nothing_yields_no_vocabulary(self):
        # None rather than an empty set, and the distinction is the cascade
        # guard: an empty set would report every call in the mapping for naming
        # an undeclared spec, burying the one cause under all of its
        # consequences.
        ids, findings = self.ids([])
        self.assertIsNone(ids)
        self.assertTrue(findings)

    def test_a_catalogue_whose_only_entry_has_no_id_yields_no_vocabulary(self):
        ids, _ = self.ids([{"title": "Nameless"}])
        self.assertIsNone(ids)

    def test_a_catalogue_that_is_neither_shape(self):
        ids, findings = self.ids("ppapi")
        self.assertIsNone(ids)
        self.assertTrue(findings)

    def test_an_entry_url_is_carried_through(self):
        report = validate_coverage.Report(CATALOGUE)
        entries = validate_coverage.catalogue_entries(
            report, [{"id": "ppapi", "url": "ppapi.json"}, {"id": "bapi"}])
        self.assertEqual(entries, [("ppapi", "ppapi.json"), ("bapi", None)])


class OperationIndexing(ValidatorCase):
    """Reading a spec document. Every method key OpenAPI gives meaning to, and
    nothing else."""

    def test_operation_ids_and_paths_are_collected(self):
        index = index_of(PPAPI_DOC)
        self.assertEqual(index.ids, {"environmentmanagement_getEnvironment",
                                     "environmentmanagement_deleteEnvironment"})
        self.assertEqual(index.paths, {"/environments/{environmentId}": {
            "get": "environmentmanagement_getEnvironment",
            "delete": "environmentmanagement_deleteEnvironment"}})

    def test_non_method_keys_are_not_operations(self):
        index = index_of({"paths": {"/x": {"get": {}, "parameters": [], "summary": "s"}}})
        self.assertEqual(list(index.paths["/x"]), ["get"])

    def test_a_document_with_no_paths_object_has_no_index(self):
        self.assertIsNone(index_of({"openapi": "3.0.0"}))

    def test_an_operation_without_an_id_still_declares_its_method(self):
        index = index_of({"paths": {"/x": {"get": {"summary": "s"}}}})
        self.assertEqual(index.ids, set())
        self.assertEqual(index.paths, {"/x": {"get": None}})


class EveryFindingIsReported(ValidatorCase):
    """Not one per run. A validator that stops at the first error transfers
    triage to whoever runs it: they learn the true size of the problem only
    after N runs of the build."""

    def test_a_document_wrong_in_many_ways_reports_all_of_them(self):
        doc = {
            "catalogue": CATALOGUE_URL,
            "artifacts": {"kind": "", "kinds": {"resource": "Resource"}},
            "grades": {"observed": "hearsay",
                       "vocabulary": [amend(OBSERVED, caveat=DROP),
                                      amend(DERIVED, order=1)]},
            "items": [
                {"id": "one", "kind": "module",
                 "source": {"path": "/absolute/resource.go"},
                 "calls": [{"spec": "ppapi", "coverage": "some", "grade": "hearsay",
                            "entrypoint": "create"}],
                 "uncatalogued": [{"reason": "polled-location"}]},
                {"id": "one", "kind": "resource", "calls": []},
            ],
        }
        findings = self.findings(doc)
        self.assertEqual(sorted(self.paths(findings)), sorted([
            "artifacts.kind",
            "grades.observed",              # names no declared grade
            "grades.vocabulary[0].caveat",
            "grades.vocabulary[1].order",   # written against the older shape
            "uncatalogued",                 # cited by an item and never declared
            "items[0].kind",
            "items[0].source.path",
            "items[0].calls[0]",            # names its operation neither way
            "items[0].calls[0].coverage",
            "items[0].calls[0].grade",
            "items[0].calls[0].entrypoint",  # no entrypoints declared here
            "items[1].id",
        ]))

    def test_a_broken_grade_block_does_not_bury_itself_under_its_consequences(self):
        # The cascade guard. With no readable grade declaration, every call in
        # the document cites an undeclared grade, and reporting all of them
        # would be correct and useless.
        findings = self.findings(document(grades={"observed": "observed",
                                                  "vocabulary": []}))
        self.assertEqual(self.paths(findings), ["grades.vocabulary"])

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
        # reject PATCH the first time somebody used it, or a WebDAV verb, or an
        # extension. The spec's own method keys are known, and that is a
        # different question: an unknown method is simply in no spec.
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

    def test_a_call_with_no_entrypoint_is_not_a_finding(self):
        # Entrypoints are an axis some artifacts have. Requiring one everywhere
        # would force a synthetic id onto every call that has no phase.
        self.assertClean(one_call(entrypoint=DROP))

    def test_a_document_declaring_no_entrypoints_is_not_a_finding(self):
        doc = document(artifacts=amend(ARTIFACTS, entrypoints=DROP),
                       items=[amend(ITEM, calls=[amend(CALL, entrypoint=DROP)])])
        self.assertClean(doc)

    def test_a_call_with_no_api_version_is_not_a_finding(self):
        # Its absence means the operation's default, which is a meaning and not
        # an omission.
        self.assertClean(one_call(apiVersion=DROP))

    def test_a_call_with_no_approximate_flag_is_not_a_finding(self):
        # Absent means false, which is the ordinary case and must not need
        # spelling out on every row a producer is sure about.
        self.assertClean(one_call(approximate=DROP))

    def test_an_item_with_no_uncatalogued_calls_is_not_a_finding(self):
        self.assertClean(one_item(uncatalogued=DROP))

    def test_an_empty_uncatalogued_list_is_not_a_finding(self):
        self.assertClean(one_item(uncatalogued=[]))

    def test_no_uncatalogued_declaration_when_nothing_cites_one(self):
        # The map is required only once an item cites a reason. Requiring it
        # always would reject every mapping written before the axis existed.
        self.assertClean(document(uncatalogued=DROP,
                                  items=[amend(ITEM, uncatalogued=DROP)]))

    def test_an_uncatalogued_entry_with_no_count_or_note(self):
        self.assertClean(one_item(uncatalogued=[{"reason": "user-supplied"}]))

    def test_a_grade_with_no_tone_is_not_a_finding(self):
        self.assertClean(with_grades(amend(OBSERVED, tone=DROP)))

    def test_a_tone_nobody_here_has_heard_of_is_not_a_finding(self):
        # The tone vocabulary is keel's. A list of tones here would be a second
        # remembered vocabulary rotting against a repository with no reason to
        # tell this one when it grows.
        self.assertClean(with_grades(amend(OBSERVED, tone="whisper")))

    def test_unknown_keys_are_not_findings(self):
        # Do not allow-list. An allow-list silently drops every key added later,
        # and here it would reject a corpus that is ahead of this checker rather
        # than behind it. `order` is the deliberate exception, because it is
        # retired rather than unknown, and it has its own test.
        doc = document(items=[amend(ITEM, calls=[amend(CALL, confidence="high")],
                                    deprecated=True)])
        doc["x-generated-by"] = "map.go"
        doc["artifacts"] = amend(ARTIFACTS, plural="provider components")
        doc["grades"] = {"observed": "observed",
                         "vocabulary": [amend(OBSERVED, weight=3), DERIVED]}
        self.assertClean(doc)

    def test_a_filename_that_looks_like_a_parent_reference_is_not_a_finding(self):
        # ".." is checked as a path segment, not as a substring. A file named
        # resource..go is odd and is not an escape.
        self.assertClean(one_item(source={"path": "internal/resource..go"}))

    def test_a_dot_segment_is_not_a_finding(self):
        self.assertClean(one_item(source={"path": "./internal/resource.go"}))


class TheCommandLine(ValidatorCase):
    """End to end, because the exit code is what a content repository's CI reads
    and nothing above exercises it.

    fetch_json is substituted throughout. Nothing here opens a socket, and the
    substitution is also what lets the unreachable-catalogue path be tested at
    all, since a test that needs the network to be down is a test that passes for
    the wrong reason on a laptop.
    """

    def setUp(self):
        self.responses = {
            CATALOGUE_URL: ([{"id": "ppapi", "url": "ppapi.json"},
                             {"id": "bapi", "url": "bapi.json"}], None),
            "https://example.invalid/corpus/ppapi.json": (PPAPI_DOC, None),
            "https://example.invalid/corpus/bapi.json": (BAPI_DOC, None),
        }
        self.fetched = []
        original = validate_coverage.fetch_json

        def fake(url, timeout=10):
            self.fetched.append(url)
            return self.responses.get(url, (None, "URLError: nothing at that address"))

        validate_coverage.fetch_json = fake
        self.addCleanup(setattr, validate_coverage, "fetch_json", original)

    def run_main(self, doc, catalogue=None, specs=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        target = root / FILE
        target.write_text(doc if isinstance(doc, str) else json.dumps(doc))
        argv = [str(target)]
        if catalogue is not None:
            path = root / CATALOGUE
            path.write_text(json.dumps(catalogue))
            for name, spec_document in (specs or {}).items():
                (root / name).write_text(json.dumps(spec_document))
            argv += ["--catalogue", str(path)]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = validate_coverage.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_a_conformant_document_exits_zero(self):
        code, out, err = self.run_main(VALID)
        self.assertEqual(code, 0, err)
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

    def test_the_declared_catalogue_is_fetched_with_no_flag_at_all(self):
        # The point of making the field required. Before this, a repository that
        # never passed --catalogue got a green run that had checked nothing
        # across the boundary and said so nowhere.
        code, out, err = self.run_main(one_call(spec="nowhere"))
        self.assertEqual(code, 1)
        self.assertIn("items[0].calls[0].spec", err)
        self.assertIn(CATALOGUE_URL, self.fetched)

    def test_the_operation_check_runs_with_no_flag_either(self):
        code, out, err = self.run_main(one_call(operation="environmentmanagement_listAll"))
        self.assertEqual(code, 1)
        self.assertIn("items[0].calls[0].operation", err)

    def test_a_missing_catalogue_field_is_a_finding(self):
        code, out, err = self.run_main(document(catalogue=DROP))
        self.assertEqual(code, 1)
        self.assertIn("catalogue", err)

    def test_a_relative_catalogue_field_is_a_finding(self):
        code, out, err = self.run_main(document(catalogue="specs.json"))
        self.assertEqual(code, 1)
        self.assertIn("catalogue", err)

    def test_a_catalogue_that_cannot_be_fetched_exits_two(self):
        # Not 0, which would be a green run that checked nothing across the
        # boundary. Not 1, which would send somebody looking for a defect in a
        # file that may be clean.
        self.responses.pop(CATALOGUE_URL)
        code, out, err = self.run_main(VALID)
        self.assertEqual(code, validate_coverage.UNCHECKED)
        self.assertIn("could not check", err)
        self.assertIn(CATALOGUE_URL, err)
        self.assertEqual(out, "")

    def test_findings_outrank_an_unreachable_catalogue(self):
        # Both are true and only one is actionable. A run reporting "could not
        # check" as its exit code, with real findings above it, would be read as
        # a network problem and retried.
        self.responses.pop(CATALOGUE_URL)
        code, out, err = self.run_main(one_call(coverage="none"))
        self.assertEqual(code, 1)
        self.assertIn("items[0].calls[0].coverage", err)
        self.assertIn("could not check", err)

    def test_a_spec_document_that_cannot_be_fetched_exits_two(self):
        self.responses.pop("https://example.invalid/corpus/ppapi.json")
        code, out, err = self.run_main(VALID)
        self.assertEqual(code, validate_coverage.UNCHECKED)
        self.assertIn('spec "ppapi"', err)

    def test_the_spec_ids_are_still_checked_when_one_document_is_unreachable(self):
        # The two catalogue checks are independent, and losing the deeper one
        # must not lose the shallower one with it.
        self.responses.pop("https://example.invalid/corpus/ppapi.json")
        code, out, err = self.run_main(one_call(spec="nowhere"))
        self.assertEqual(code, 1)
        self.assertIn("items[0].calls[0].spec", err)

    def test_a_catalogue_entry_naming_no_url_is_unchecked_not_a_finding(self):
        self.responses[CATALOGUE_URL] = ([{"id": "ppapi"}, {"id": "bapi"}], None)
        code, out, err = self.run_main(VALID)
        self.assertEqual(code, validate_coverage.UNCHECKED)
        self.assertIn("names no url", err)

    def test_the_local_override_is_used_instead_of_fetching(self):
        code, out, err = self.run_main(
            VALID,
            catalogue=[{"id": "ppapi", "url": "ppapi.json"},
                       {"id": "bapi", "url": "bapi.json"}],
            specs={"ppapi.json": PPAPI_DOC, "bapi.json": BAPI_DOC})
        self.assertEqual(code, 0, err)
        self.assertEqual(self.fetched, [], "the override still went to the network")

    def test_the_local_override_checks_operations_too(self):
        code, out, err = self.run_main(
            one_call(operation="environmentmanagement_listAll"),
            catalogue=[{"id": "ppapi", "url": "ppapi.json"},
                       {"id": "bapi", "url": "bapi.json"}],
            specs={"ppapi.json": PPAPI_DOC, "bapi.json": BAPI_DOC})
        self.assertEqual(code, 1)
        self.assertIn("items[0].calls[0].operation", err)

    def test_a_local_spec_document_that_is_missing_exits_two(self):
        code, out, err = self.run_main(
            VALID,
            catalogue=[{"id": "ppapi", "url": "ppapi.json"},
                       {"id": "bapi", "url": "bapi.json"}],
            specs={"bapi.json": BAPI_DOC})
        self.assertEqual(code, validate_coverage.UNCHECKED)
        self.assertIn('spec "ppapi"', err)

    def test_the_catalogue_is_enforced_through_the_flag(self):
        code, out, err = self.run_main(VALID, catalogue=[{"id": "ppapi"}])
        self.assertEqual(code, 1)
        self.assertIn("items[0].calls[1].spec", err)

    def test_the_object_shaped_catalogue_is_enforced_through_the_flag(self):
        code, out, err = self.run_main(
            VALID,
            catalogue={"default": "ppapi",
                       "specs": [{"id": "ppapi", "url": "ppapi.json"},
                                 {"id": "bapi", "url": "bapi.json"}]},
            specs={"ppapi.json": PPAPI_DOC, "bapi.json": BAPI_DOC})
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


class Fetching(unittest.TestCase):
    """The one function that would touch a network, tested where it can be
    without one."""

    def test_a_scheme_it_will_not_follow(self):
        value, reason = validate_coverage.fetch_json("file:///etc/passwd")
        self.assertIsNone(value)
        self.assertIn("file", reason)

    def test_a_refused_connection_is_a_reason_and_not_a_traceback(self):
        # Loopback, port 1. No name resolution and no network, and the failure
        # this checks is the shape of the return rather than the wording.
        value, reason = validate_coverage.fetch_json("http://127.0.0.1:1/specs.json",
                                                     timeout=1)
        self.assertIsNone(value)
        self.assertTrue(reason)


if __name__ == "__main__":
    unittest.main()
