# OpenAPI fixtures

Small OpenAPI 3.0.3 documents, each written to exercise one thing, for testing a
general OpenAPI browser.

These are not a corpus. A corpus samples the middle of the space: it exercises
whatever happens to exist. These are written by someone looking for edges, which
is a different distribution and the one that finds bugs. Each document is as
small as it can be while still making its case, and is named for the case it
makes, so a failure says what broke without further reading.

Nothing here describes any real API. The domain is an invented public library,
kept consistent across every fixture so that reading a second one costs nothing.

## Layout

    valid/       documents that are valid OpenAPI 3.0.3
    invalid/     documents that are deliberately malformed

Subdirectories under `valid/` group fixtures by the area they exercise. Each
fixture has a sidecar named after it: `foo.json` is described by
`foo.expected.json`.

`invalid/` means the *document* is malformed, not that its content is hostile.
Everything in `valid/descriptions/` is valid OpenAPI carrying attack payloads in
its description strings, and it lives under `valid/` because that is the whole
point: a validator will never flag any of it.

`valid/catalogue/` is the one group with a single shared sidecar,
`specs.expected.json`, because its assertions are about the three specs
together rather than about any one of them.

## How expected behaviour is recorded

In a JSON sidecar per fixture, not a markdown file. Three reasons:

- The fixtures are JSON, so the sidecars are one syntax rather than two.
- Every assertion carries its own `status`, so the set of things the browser
  cannot do yet is a query rather than a careful read of prose.
- The harness that comes later can consume the assertions directly instead of a
  human re-deriving them from paragraphs.

A sidecar looks like this:

```json
{
  "fixture": "example.json",
  "exercises": "what this document is for, in one line",
  "validates": true,
  "pending": true,
  "doNotChangeFixture": "...",
  "note": "anything a reader needs to know before judging the fixture",
  "expected": [
    { "assert": "what correct rendering looks like", "status": "implemented" },
    { "assert": "...", "status": "pending", "why": "why it does not happen yet" }
  ]
}
```

`validates` records what `openapi-spec-validator` actually says about the
document. It is not the same question as whether the document conforms: see
`invalid/ref-pointer-escape-tilde.json`, which the validator passes and the
specification does not allow.

## Pending assertions

**An assertion marked `pending` describes behaviour the browser does not have
yet, and it is written as correct, not as current.**

A fixture that fails on a pending assertion is the backlog made executable. Do
not edit the fixture, and do not soften the assertion, to make it match what the
app does today. Fix the app, or leave the assertion failing until someone does.
Sidecars containing any pending assertion carry `"pending": true` and a
`doNotChangeFixture` line so this is hard to miss.

The statuses were set by reading the implementation being extracted into this
repository. They are a starting point, and worth re-checking once the app lands
here.

## Security assertions

Some assertions carry `"kind": "security"`. Their sidecar is flagged
`"security": true` and carries a `doNotSoften` line.

These are safety requirements, not rendering preferences. They say what must be
true, and they were deliberately **not** checked against the current
implementation, because a fixture that recorded today's behaviour would entrench
it. They are all `pending` for that reason: treat them as unmet until someone
demonstrates otherwise.

They may be satisfied, and the fixture may then be extended. They must never be
relaxed, narrowed or deleted to match what an implementation does.

The whole of `valid/descriptions/` is this. Descriptions render as HTML, and
after the extraction the browser loads a catalogue from a URL, so spec content
is arbitrary third-party input rendering on the browser's own origin. That
change arrives as a consequence of the split rather than as a change anyone
makes.

## Validating

`openapi-spec-validator`, in a throwaway virtualenv, since a plain
`pip install` is blocked by PEP 668 on most machines:

```
python3 -m venv .venv
.venv/bin/pip install openapi-spec-validator
.venv/bin/python - <<'PY'
import pathlib
from openapi_spec_validator import validate
from openapi_spec_validator.readers import read_from_filename
root = pathlib.Path("tests/fixtures")
for p in sorted(root.rglob("*.json")):
    if p.name.endswith(".expected.json") or p.name == "specs.json":
        continue
    try:
        validate(read_from_filename(str(p))[0])
        print("PASS", p)
    except Exception as e:
        print("FAIL", p, str(e).replace("\n", " ")[:120])
PY
```

Everything under `valid/` passes. Three documents under `invalid/` are rejected,
which is the point of them. The fourth, `ref-pointer-escape-tilde.json`, passes
the validator while still being non-conformant, and its sidecar says so.

`valid/catalogue/specs.json` is a catalogue index rather than an OpenAPI
document, so it is not validated.

## Inventory



### `invalid/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `operation-no-responses.json` | an operation with no responses key, and an operation with an empty responses object | no, by design | yes |  |
| `ref-dangling.json` | three references that resolve to nothing: a parameter, a response body schema and a whole response | no, by design |  |  |
| `ref-pointer-escape-tilde.json` | RFC 6901 ~0 unescaping, and the ordering rule that makes ~01 decode to ~1 rather than to a slash | yes | yes |  |
| `response-lowercase-wildcard.json` | a lowercase 4xx range key, which plain string sorting places after `default` and therefore in an obviously wrong position | no, by design | yes |  |

### `valid/catalogue/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `specs.json, catalogue-api.json, lending-api.json, branches-api.json` | a catalogue of three specs, deliberately sharing operation ids and component names, so that a deep link that cannot name a spec resolves against the wrong one | yes | yes |  |

### `valid/composite-schemas/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `allof-many-members.json` | allOf with three members: two references and one inline object | yes | yes |  |
| `allof-property-merge.json` | two inline allOf members, each carrying its own properties and required list, that must combine into one property set | yes | yes |  |
| `allof-single-member.json` | allOf with exactly one member, the idiom for attaching a description to a $ref under OAS 3.0 | yes | yes |  |
| `anyof.json` | anyOf with two inline members, where one or both may apply | yes | yes |  |
| `discriminator.json` | a discriminator with an explicit mapping whose keys differ from the schema names | yes | yes |  |
| `oneof.json` | oneOf across two named schemas | yes | yes |  |

### `valid/degenerate/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `empty-tags.json` | an empty tags array at the document root and an empty tags array on an operation | yes |  |  |
| `no-components.json` | a document with no components key, where every schema is inline | yes |  |  |
| `no-servers.json` | a document with no servers key | yes |  |  |
| `operation-no-parameters.json` | an operation with no parameters key at all | yes |  |  |
| `path-no-operations.json` | a path item with a summary and description but no HTTP methods, beside a path that does have one | yes |  |  |
| `schema-no-properties.json` | an object schema with no properties key, and one with an explicitly empty properties map | yes |  |  |

### `valid/descriptions/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `description-attribute-breakout.json` | a link title breaking out of its quoting, markup inside a code span and a fenced block, and an unclosed attribute that would swallow the rest of the document | yes | yes | yes |
| `description-image-onerror.json` | an img with an onerror attribute, an onerror smuggled through a markdown image title, and an onmouseover on a plain element | yes | yes | yes |
| `description-injection-sites.json` | the same three-part payload written into all ten places a description can appear, each labelled with its site | yes | yes | yes |
| `description-javascript-uri.json` | markdown links whose href is a javascript: URI, written inline, reference-style, as an autolink, and with the scheme obfuscated | yes | yes | yes |
| `description-safe-html.json` | inline HTML that is legitimate and worth keeping, beside the markdown that produces the same result | yes | yes | yes |
| `description-script-tag.json` | a raw <script> tag, both inline and with a src, written into a description at every rendering site | yes | yes | yes |

### `valid/examples/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `example-values.json` | the singular `example` keyword on a parameter, on a parameter's schema, on individual properties, and on a whole schema | yes | yes |  |
| `examples-named-media-type.json` | a media type's `examples` map with three named entries, one of which also carries a description | yes | yes |  |

### `valid/extensions/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `extensions-preserved.json` | vendor extension keys at the document root, on info, on a path item, on an operation, on a parameter, on a schema and on a schema property | yes |  |  |

### `valid/media-types/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `multiple-media-types.json` | a request body and a response that each declare three media types with deliberately different schemas | yes | yes |  |

### `valid/notes/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `notes-node-coverage.json` | one x-notes entry on each node the extension is allowed on: a tag, an operation, a parameter object, that parameter's schema, a response object, a component schema and a schema property | yes | yes |  |
| `notes-one-grade-many-entries.json` | three x-notes entries on one node, all sharing the same grade | yes |  |  |
| `notes-several-grades.json` | four notes across three declared grades on a single node | yes | yes |  |
| `notes-single.json` | a single x-notes entry written as a bare string rather than an object | yes |  |  |
| `notes-through-ref.json` | notes on a schema node reached through a $ref, against the inline case as a control, on both a parameter and a property | yes | yes |  |
| `notes-undeclared-grade.json` | a note carrying a grade that is neither built in nor declared by the document, and a note carrying an empty grade | yes |  |  |

### `valid/operations/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `multi-verb-differing-parameter-counts.json` | four operations on one path whose parameter counts differ and do not increase monotonically | yes |  |  |

### `valid/path-parameters/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `path-item-parameters-only.json` | parameters declared on the path item, with no operation-level parameters anywhere on the path | yes | yes |  |
| `path-item-parameters-overridden.json` | an operation parameter overriding a path item parameter by matching name and in, and a same-name parameter in a different location that must not override | yes | yes |  |
| `path-item-parameters-plus-operation.json` | the union of path item parameters and operation parameters, with no name collision between them | yes | yes |  |

### `valid/refs/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `ref-chain-over-hop-limit.json` | a chain of twelve references that resolves, beside a chain of three, to separate a hop limit from a genuine cycle | yes | yes |  |
| `ref-cycle-two-step.json` | Author -> Book -> Author, a cycle that closes on the second hop rather than the first | yes |  |  |
| `ref-examples.json` | $ref from a media type's examples map into components/examples | yes | yes |  |
| `ref-headers.json` | $ref from a response header into components/headers | yes |  |  |
| `ref-nested-two-hops.json` | two-hop resolution: operation parameter -> components/parameters -> components/schemas, with keys on the inner target that must survive both hops | yes | yes |  |
| `ref-parameters.json` | $ref from an operation's parameter list into components/parameters | yes |  |  |
| `ref-path-item.json` | a path item that is a $ref to another path item, which OAS 3.0 allows | yes | yes |  |
| `ref-pointer-escape-slash.json` | a pointer whose token contains a slash, escaped as ~1 per RFC 6901 | yes |  |  |
| `ref-request-bodies.json` | $ref from an operation's requestBody into components/requestBodies | yes |  |  |
| `ref-responses.json` | $ref from a response entry into components/responses | yes |  |  |
| `ref-schemas.json` | $ref from a response media type into components/schemas | yes |  |  |
| `ref-self-recursive.json` | a schema whose property refers back to the schema itself | yes |  |  |
| `ref-siblings-ignored.json` | keys written beside a $ref, which OAS 3.0 requires to be ignored | yes |  |  |

### `valid/responses/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `response-default-and-wildcards.json` | the 4XX and 5XX range keys and the default key, including an operation whose only response is default | yes | yes |  |

### `valid/schema-keywords/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `additional-properties.json` | additionalProperties written as true, as false, as a schema, and left unwritten | yes | yes |  |
| `schema-constraints.json` | minLength, maxLength, pattern, minimum, maximum, multipleOf, exclusiveMinimum, default, enum and format | yes | yes |  |
| `schema-visibility.json` | readOnly, writeOnly and deprecated on properties, title and nullable on schemas, and deprecated on an operation | yes | yes |  |

### `valid/security/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `security-operation-optout.json` | an operation with `security: []`, which opts out of the document-level requirement entirely | yes | yes |  |
| `security-operation-override.json` | an operation-level security requirement replacing the document-level one | yes | yes |  |
| `security-schemes.json` | an OAuth2 authorizationCode flow, an apiKey scheme and an HTTP bearer scheme, with a document-level security requirement | yes | yes |  |

### `valid/servers/`

| Fixture | Exercises | Validates | Pending | Security |
| --- | --- | --- | --- | --- |
| `server-template-multiple-variables.json` | more than one variable in a single server URL, including one with no enum and one with no description | yes | yes |  |
| `server-variables.json` | server variables carrying a default, an enum and a description | yes | yes |  |
| `servers-multiple.json` | a document declaring three servers | yes | yes |  |

