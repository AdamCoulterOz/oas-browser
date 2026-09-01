# Why the OAS browser is like this

This document is `oas-browser`'s foundational context. It states the boundary,
the contracts, the operating model, and the reasoning behind decisions already
made. It is written to be read cold, without the conversation that produced it.

**It was written as a handover, and it is no longer one.** It was authored in
`powerplatform-apis` by the session that performed the extraction, addressed to
whoever would inherit the browser afterwards. The extraction happened, the
browser moved, this file moved with it, and it is now read by the owner rather
than handed to them. So it is no longer a set of instructions. It is the
reasoning to reach for when something here surprises you.

That change of address matters more than it sounds, because the file crossed a
context boundary carrying its own conventions, which is a failure this document
warns about at **Cross-spec links** and then committed on itself: it arrived
still saying "this repo" and meaning `powerplatform-apis`, still describing the
browser repo as one to be created, and still calling the work unpushed. Nothing
errored, there was no diff to review, and it read entirely fine. Corrected now,
and recorded because it is the cleanest instance of that pattern in the project.

**Every rule below is stated with the reason it exists, deliberately.** A rule in
a handover outlives the session that wrote it and gets applied by someone who no
longer has the context to question it, so a bare instruction here is more
dangerous than a bare instruction anywhere else. One rule in an earlier draft of
this document was wrong, and it was wrong because a true premise got
over-generalised by one step that nobody took deliberately. It is corrected
below, with the step visible. Where a reason here does not hold for you, that is
grounds to refuse the rule, not to work around it.

## How to read this

It is long because most of it is reasoning rather than instruction. You do not
need all of it before you start.

**Read now, in this order:**

1. **Why the split**, **Three repos**, **How to operate**. What you own, what you
   do not, and how the job works. Fifteen minutes and it prevents most of the
   avoidable mistakes.
2. **The failure pattern.** One idea with several faces, and it accounts for
   nearly every defect this project has produced. If you read only one section,
   read that one.
3. **Reaching the other boundaries.** You cannot do this job alone and the other
   two parties are live sessions, not repositories.

**Read when you need it:** the contracts, the extraction plan, the ranked backlog,
the practical gotchas.

**A word on the tone.** Nearly every rule here arrived as somebody correcting me,
and several are corrections to corrections. Two of the most useful came from the
sessions this document tells you to talk to. That is not throat-clearing: it is
the single most reliable thing I learned, which is that **the boundaries are peers
and they will out-argue you regularly.** Treat a confident list of rules as
expensive rather than obvious, and expect to add to it the same way.

## Why the split

The browser and the Power Platform specs grew up in one repo, so the browser
learned things it has no business knowing. That is now blocking a decision: a
Terraform resource to API coverage mapping has to live somewhere, and it has no
natural host, because it is a join between two things that neither side owns
outright.

The answer is not to pick a side. It is that the browser is a general tool that
should not know what Power Platform is, and once that is true, each piece of
content has an obvious home and the browser owns only the contracts between
them.

## Three repos

**1. `AdamCoulterOz/oas-browser` (this repo). Created 2026-08-28.**

A general OpenAPI browser. Blazor WebAssembly, built on keel. It must not
contain the string "Power Platform" anywhere outside its own sample fixtures.

Owns: rendering, navigation, search, the schema tree, code samples, theming,
keel consumption, the GitHub issue and comment layer, and **every contract the
other two repos implement against**.

**2. `powerplatform-apis`, which this browser was extracted from.**

The API specs and the machinery that produces them: the docs mirror, the
generator, `enrichment.json`, the catalogue. Owns spec content and its
provenance.

**3. The fork of `terraform-provider-power-platform`.**

The Terraform resource to API mapping. Owns mapping content. It may reference
`powerplatform-apis`, since a mapping naturally cites the operations it maps to.

All three are opened by the browser. Only the browser defines the formats.

## The contracts the browser defines

This is the real work of the split, and most of it does not exist yet. Today
these behaviours are hardcoded with Power Platform vocabulary baked in. Each one
has to become a declared contract that a corpus fills in.

### Catalogue

`specs.json` already does this: the list of specs the browser loads. It is close
to general already. It needs a place for a corpus to declare the things below.

**Shape, decided and given to the specs owner.** It becomes an object, because
there is nowhere in a bare array to put the grade declaration, the docs
provider, the grouping label or branding, and introducing the object once beats
adding `default` to the array and moving it later.

```json
{ "default": "ppapi", "index": "index.json", "specs": [ { "id": "...", ... } ] }
```

`default` names the spec a bare link resolves against. `index` is optional; see
the routing decision for what it costs to omit.

**No version field and no flag day.** A top-level array is the legacy form and
behaves exactly as today, first entry as default. Detecting the shape is derived
where a version field would be remembered, and it makes the legacy path
*precisely* today's behaviour rather than approximately.

### Evidence grades — do this first

Take this before the rest of the extraction, not as part of it. The conformance
checker currently hardcodes the grade set as a literal, which makes it the one
invariant in that file that can go stale silently while every other check derives
its answer from the data. Its failure mode is also the damaging one: a stale
grade list rejects correct data and reads as a data defect, so the corpus gets
edited to match the checker. Corpus-declared grades retire that literal the
moment they land.

The browser renders `x-notes` on any node: findings where an API's real
behaviour contradicts its documentation. Each note carries a `source` naming how
it was established, and notes are grouped by grade into one callout per grade,
so a reader can tell an attested claim from a modelled one at a glance.

**The mechanism is general. The vocabulary is not.** `live`, `pac-cli` and
`provider` are Power Platform's three provenances, and they are currently
hardcoded in `Model/SpecNote.cs` along with their titles, caveats and ordering.

The browser must instead let a corpus declare its own grades: an id, a title, a
caveat line, a tone, an order, and which one counts as "observed". A corpus with
one grade and a corpus with five must both work. `powerplatform-apis` then
declares its three.

Decisions already settled, do not relitigate:

- Three grades, not four. "Documented but never checked" was rejected as a
  grade: it is the default state of most of a docs-derived corpus, so it would
  immediately become the most common grade and drown the contradictions the
  panel exists to surface.
- Never merge grades into one callout. Ordering and visual weight are the levers
  if stacking ever needs compacting.
- Stacking is rare and load-bearing: measured across the migrated specs, 50 of
  52 note-carrying entities have one grade, 2 have two, none have three. Do not
  pre-solve it. Remeasure after the remaining specs land.
- **The induced order ranks evidential weight, not informativeness, and those
  come apart.** The order exists because a wire observation really is stronger
  evidence that a claim holds than a third party's model of the API. That stays
  true. But a third-party client answers a question the wire cannot, and the
  distinction earned itself in practice.

  Seven operations were added to a corpus on the evidence of a provider's call
  sites alone, graded `provider` because a working client is real evidence about
  what *exists* and none about what the service *returns*. Reading them off the
  call sites rather than inferring them is what made the details right: creation
  is a `PUT` to a client-chosen id with no `POST` to a collection, so `201`
  against `200` is the only thing separating a create from a replace; delete
  answers `200` rather than `204`; every call carries a `$filter` naming an
  environment the host has already identified.

  Every one of those would have been guessed wrong. **Probing asks what the
  service will answer. A vendor SDK says what the vendor models. A working
  third-party client is the only source that says what an operation looks like
  when somebody uses it in anger** — including which of several plausible shapes
  is the one that works, and which redundant parameter is nonetheless required.

  So do not read the lowest grade as the least useful source. It is the weakest
  warrant for *this claim is true* and sometimes the only witness to *this is how
  it is actually done*.
- Grade the finding, not the entity. Node-level markers are a fallback for when
  the note's own text does not say where it came from.

### Upstream documentation links

An operation can link to its published documentation. The browser currently
hardcodes a Microsoft Learn badge, complete with the Microsoft logo drawn inline
in `OperationView.razor`.

Generalise to: a corpus declares its upstream docs provider once, giving a label
and a mark, and operations carry a URL. The badge is then built from the
declaration.

### Cross-spec links: the `spec:` scheme

A corpus of several specs needs prose in one to reference another. The corpus
says *what it means*; the browser decides what URL that is.

```
spec:<specId>                        the spec's overview
spec:<specId>#/resources/<tag>       a resource within it
spec:<specId>#/schemas/<name>        a schema within it
spec:<specId>#/operations/<id>       an operation within it
```

`<specId>` is the `id` from the catalogue.

**The fragment vocabulary is a stable contract the browser owns and translates.
It is not the browser's route shape, and an earlier version of this section said
it was.** That wording was wrong in the way that matters: it couples a corpus's
files to the browser's internal URL format, so the routing change decided below
would have silently broken every `spec:` link in every corpus. The whole purpose
of the scheme is that the corpus says *what it means* and the browser decides
what URL that is. That the vocabulary currently resembles the route shape is a
coincidence, not a promise, and the two are now free to diverge.

Found by the specs owner asking whether the vocabulary was moving, because they
had already shipped a checker that enforces it. Nobody would have found it from
this side: the coupling is invisible while the two happen to agree.

**And a gap that follows from it, which is the browser's.** A corpus-side
conformance check validates that a fragment resolves against *the corpus*. It
cannot detect that the *browser* stopped honouring the vocabulary — it stays
green while every link 404s. The browser therefore owes a test that every
fragment form still resolves, and until that exists a corpus's green says
something about its data and nothing about the links working. This is the
consumer-can-only-see-its-own-layer rule, arriving as a hole in a check that
already existed.

This replaced ten relative markdown links that were **broken in production and
had never worked**. They were written for GitHub's file view, where `../bapi`
resolves correctly, and the browser has no router, so they resolved outside the
site path entirely and 404'd. Two specs used two different depths; both were
wrong, and their disagreement was the only visible symptom. Had they agreed,
nothing would have pointed at them.

An unresolvable `spec:` link fails as an unresolvable link rather than a
confident 404. That is deliberate: visibly missing beats silently wrong.

**Do not extend the conformance check to READMEs.** This is the important part
and it is counterintuitive enough that someone helpful will try. In a README
rendered by GitHub, `../bapi` *is* correct and must stay. The same syntax is
right in one rendering context and wrong in the other:

- Prose inside a spec is rendered by **the browser**, and uses `spec:`.
- Prose in a README is rendered by **GitHub**, and uses ordinary relative paths.

Unifying them would flag correct content, and someone would then "fix" a working
README into a broken one. Two renderers, two conventions, deliberately not
reconciled. This is also the root of the original bug: browser-rendered prose was
written using GitHub-rendered conventions, by someone who had no reason to think
of them as different contexts.

**Which predicts where the next one comes from: prose that moves between the two
contexts carries its conventions with it.** A paragraph lifted out of a README
into a spec description arrives carrying relative links that were correct where
they came from, and it will look entirely fine. The exclusion above protects
READMEs from the check; this is the reason that protects specs from READMEs. Any
time prose is copied across that boundary, its links need re-reading, and nothing
about the text will signal that.

### Other extensions in use

- `x-stub` on a schema means "referenced by the corpus but never defined, shape
  unknown". General; keep.
- `x-probe-verified` and `x-source` are node-level provenance markers. These
  fold into the grade contract above rather than staying as separate concepts.
- **Preserve unknown `x-` keys through `$ref` resolution.** Do not allow-list.
  An allow-list silently drops every extension added later, and the symptom is
  invisible.

### The coverage mapping

The contract that prompted the split. The browser defines a format for "this
external artifact maps to these operations", renders it as a coverage view, and
knows nothing about Terraform or Power Platform in doing so.

Designed as a contract first, before any producer serialised anything. The
counterpart is a live session owning the mapping *content* for a fork of
`terraform-provider-power-platform`.

**Where a declared vocabulary lives: at the level of the thing it describes.**
`kinds` and `entrypoints` describe artifacts, so they sit inside `artifacts`.
`grades` describes calls, and calls have no top-level container, so it sits at
the root. `uncatalogued` reasons describe uncatalogued entries, so the root as
well.

Written down because it existed in the design and nowhere in the words. A
producer put the `uncatalogued` vocabulary inside `artifacts`, following a
sentence of mine that said "alongside `kinds` and `entrypoints`", and the
checker rejected it. Both readings were available and the placement looked
arbitrary from outside. They asked what would make the asymmetry necessary
rather than accepting it, which is the near-uniformity rule pointed at a format,
and the answer was a real rule nobody had stated.

```json
{
  "catalogue": "https://example.invalid/specs.json",
  "grades": { "observed": "observed",
              "vocabulary": [ { "id": "observed", "title": "...", "caveat": "...",
                                "tone": "<keel tone, optional>" },
                              { "id": "derived", "title": "...", "caveat": "..." } ] },
  "artifacts": { "kind": "provider component",
                 "kinds": { "resource": "Resource", "datasource": "Data source" },
                 "entrypoints": { "Create": "Create", "Read": "Read" } },
  "uncatalogued": { "async-continuation": "Async continuation" },
  "items": [
    { "id": "<opaque, stable>", "kind": "<key of artifacts.kinds>",
      "name": "<for display, defaults to id>",
      "source": { "path": "<repo-relative>", "line": 412 },
      "calls": [ { "spec": "ppapi", "operation": "<operationId>",
                   "coverage": "full", "grade": "observed",
                   "entrypoint": "<key of artifacts.entrypoints>",
                   "apiVersion": "<only where the caller pins one>",
                   "approximate": false, "note": "..." } ],
      "uncatalogued": [ { "reason": "<key of the uncatalogued map>",
                          "count": 4, "note": "..." } ] } ]
}
```

Four decisions in that shape, each of which was a live alternative:

- **`{spec, operation}`, structured, not an `operationId` alone and not a
  `spec:` URI string.** Operation identity is unique only *within* a spec: the
  corpus has four operationIds appearing in more than one spec, so a mapping
  keyed on the id alone silently merges them. Structured rather than the URI
  because a data file wants a pair it can validate and index without parsing or
  unescaping, and ids can contain characters a URL must escape. It is the same
  address space the router now carries, so there is one addressing vocabulary
  rather than two.
- **Coverage is an ordered pair, `full` and `partial`, plus free text.** The
  producer named three kinds of partiality: conditional code paths, a subset of
  the request body, one direction only. Those are three *reasons*, not three
  degrees, and flattening an unordered set onto an ordered axis is the mistake
  already recorded under the evidence grades. Watch the free text: if it
  converges on recurring phrasings, that is an unstated axis asking to exist and
  it should be declared rather than left to calcify.
- **Grades are the same contract with a separately declared vocabulary.** Not a
  shared enum with the spec corpus. Theirs are provenances of a claim about an
  API's behaviour; these are provenances of a claim about what a codebase calls.
  Same mechanism, same reader-facing meaning, different sets. One enum spanning
  both would be the Power Platform mistake in a new place.
- **The inverse view is derived, not materialised.** "Which operations does
  nothing call" is a join the browser can compute from the catalogue and the
  mapping, and a derived answer stays true when either side changes. A
  materialised one is a claim about the spec living in the producer's repo,
  going stale the day an operation is added.

**Two extensions the first producer asked for, both accepted, and the reason
they were accepted rather than resisted.**

The rule was that the format must be expressible generally: *an external artifact
maps to these operations*. Both of these pass that test, and both reuse the
pattern already in the format rather than adding a concept.

- **`entrypoints`.** An artifact may invoke different operations depending on
  which of its named entrypoints ran. Declared in `artifacts.entrypoints` as
  id-to-label, optional `entrypoint` on a call. The producer's natural unit was
  `(artifact, entrypoint, operation)`, and collapsing it is lossy in a way
  nothing downstream can undo: one component reached one operation from three
  lifecycle entrypoints plus another component's delete path, where the useful
  fact is *which phase* and whether that phase always does. Refusing would have
  pushed the axis into synthetic ids, where nothing can read it.
- **`uncatalogued`.** Calls an artifact makes that no catalogue operation names,
  as a sibling of `calls`, with a producer-declared `reason` vocabulary. Around
  a fifth of the first producer's call sites have no operation identity at all
  and it is not extraction failure: a URL returned in a `Location` header and
  polled, a URL supplied by the user in configuration, a path whose segments are
  runtime values.

  **This one is not a convenience, it is the failure pattern.** A coverage view
  that silently omits a fifth of what an artifact does looks exactly like a
  complete one. Nothing is missing on screen; the page quietly asserts more than
  the data earned. Leaving it out would have been the browser making a
  completeness claim on a producer's behalf.

  **What belongs in `uncatalogued` is decided by the corpus, not by the call.
  I got this wrong, ruled on it, and was corrected. The wrong version is kept
  because the mistake is more useful than the rule.**

  Thirteen rows arrived with a placeholder in the path, reported as operations
  the corpus lacked. I split them on **which segment varies**: where the
  variable was a *key* into a named collection
  (`/api/data/v9.2/EntityDefinitions(LogicalName='{}')`) an operation exists and
  the variable is its parameter; where the variable was the *collection itself*
  (`/api/data/v9.2/{}({})`), supplied by the user at run time, the request is one
  of an unbounded family and no operation could name it. Three forwarded, ten
  ruled `uncatalogued`.

  **Ten of them resolve.** The corpus does not enumerate one operation per
  table; it documents the generic OData surface once, with the entity set as a
  path parameter. So "query an arbitrary entity set" is exactly one named
  operation — `records_query` — and the provider calls it. Twelve dataverse
  operations were about to be recorded as absent or uncatalogued while being
  both called and documented.

  The premise was true and the conclusion did not follow: a runtime entity-set
  name really is unbounded, and *that is a fact about the set, not about the
  operation*. **A spec can template a name as readily as an id.**

  So the distinction is real and answers a different question than I asked it.
  Which segment varies tells you whether the *caller* knows the name before it
  runs. Whether an operation exists tells you what the *corpus* documents. I
  measured a property of the call to decide a property of the corpus — the
  adjacent-question failure, committed while writing the section that names it,
  in a ruling that overrode a producer who had it right.

  The rule that survives: **`uncatalogued` is for calls no operation names, and
  only the corpus can say that.** Resolve against the catalogue first; what
  fails to resolve is a candidate, and a runtime-varying segment is a property
  worth carrying but not the test. That producer's `uncatalogued` ended up
  holding three rows rather than thirteen, and the field is still right.

- **Path matching absorbs a spelling convention and surfaces a defect, and the
  rule has to tell them apart.** A call naming `{method, path}` matches a spec
  operation when a **templated** spec segment matches any single literal call
  segment, and every other segment matches exactly, **including case**.

  Both halves came from real rows. A corpus templating its version as
  `/api/data/{apiVersion}/EntityDefinitions` against a caller pinning
  `/api/data/v9.2/...` is one operation spelled two ways, and 22 operations in
  that corpus are versioned so — treating it as a mismatch reports false gaps by
  the dozen. A caller sending `/licensing/BillingPolicies` where the spec says
  `billingPolicies` is a defect in the caller, and matching it loosely would
  hide a real bug inside the file whose entire job is describing what the code
  does.

  So: a templated segment matching a literal is a convention to absorb; a case
  difference is a defect to surface. Prefer `operation` by id anyway, which
  sidesteps the whole question.

  **And the rule needs a tiebreak, which is not optional.** A corpus that
  documents a catch-all alongside specific paths makes the rule ambiguous:

      GET /api/data/{apiVersion}/{entitySetName}   records_query
      GET /api/data/{apiVersion}/publishers        publishers_list

  A call to `/api/data/v9.2/publishers` matches both, legitimately, and nothing
  above chooses. On the first real run this made 25 rows ambiguous, every
  specific operation shadowed by the catch-all. So: **rank candidates by how
  many segments they match literally, most specific wins, and a genuine tie is
  reported rather than resolved.**

  It belongs in the contract rather than in each implementation because two
  consumers ranking differently would resolve the same row to different
  operations and neither would be wrong by the rule as first written.
  **Ambiguity in a shared contract is worse than a strict rule somebody
  disagrees with, because it produces disagreement nobody can adjudicate.**

  **And a second implementation is how you find out the rule was ambiguous.**
  The sentence was *"a templated segment in the spec matches any single literal
  segment in the call"*. The producer implemented it over whole segments; the
  checker here also handled a templated part *within* a segment, so
  `{entitySetName}({recordId})` matched `systemusers({id})` in one and not the
  other. Neither party knew the sentence had two readings until the two
  implementations disagreed on four rows.

  So: **a written contract with one implementation is untested, and the second
  implementation is the test.** This is the two-instruments argument from
  *Reporting across a boundary*, which was about consumers on different paths,
  applied to implementations of one specification. Rereading the sentence
  produces the reading it produced the first time; only running two of them
  produces the disagreement. Where a contract matters, a second implementation
  is not duplicated effort to be consolidated away.

  **And the qualification, which came from the producer and which I had
  overclaimed past.** The two implementations found it only because they
  disagreed *on data that exercised the difference*. That corpus happens to
  contain OData paths templated inside a segment. A producer that never touched
  that API would have had two implementations, one written rule, complete
  agreement, and the same latent ambiguity.

  So a second implementation is **a test that fires only on inputs reaching the
  difference**, which makes its coverage a property of the content rather than
  of the arrangement. It is a chance you get, not a guarantee you can rely on,
  and **the rules most likely to stay ambiguous are the ones neither party's
  data happens to stress.**

  Which is the argument for fixing the sentence rather than banking the catch:
  *a written rule two implementations agree on is not the same as a rule that
  says what it means*. The agreement may only record that nobody has yet fed it
  the case that separates them.

**And an axis that was asked for and should not be added, because a different
decision dissolved it.** The producer proposed a declared vocabulary for *why*
coverage is partial, having found three reasons in their extractor rather than in
prose, which is a stronger case than the usual convergence warning. But set the
three against `uncatalogued`: two of them are calls with no operation identity
and belong there, not in `calls`. Once they move, `partial` has one meaning left,
and **a declared enum with one member is a vocabulary pretending to be a choice.**
The free-text note then carries the specific condition, which is genuinely
per-row, rather than a category spelled out longhand.

Worth keeping as a shape: when a producer asks for two things, check whether one
of them removes the need for the other before building both.

**And one thing the producer was told not to build, which is the more useful
half.** The output they most want is "which operations are called only via this
spec when another spec also offers them". That is *not derivable*: it needs a
cross-spec sameness relation asserting that two specs describe the same logical
operation, and identical operationIds are not evidence of it, precisely because
those collisions exist. So it is a third contract, and it is a claim about what
the specs describe rather than about what code calls, which puts it with the
corpus rather than with the mapping.

The path of least resistance was for them to encode it in their file as a column
or a naming convention. That would have turned "an external artifact calls these
operations" into "these operations are equivalent" — a different claim, in the
wrong repo, that no validator here would catch. **A consumer's question quietly
redefining what a producer records is the same seam as everything else in this
document, arriving before either party has written a line.**

**"Not called" is a claim the data does not support. The honest state is "no
recorded caller in this mapping".**

`called fully` and `called conditionally` are positive claims backed by a call
site. The third state is *the absence of a record in one particular mapping*,
and the producer of that mapping is one consumer among many — an operation with
no row may have callers nobody has mapped. Saying "not called" asserts a fact
about the world from evidence that is only about one file.

With exactly one mapping loaded the two readings are indistinguishable, which is
why the wrong one is easy to ship, and it is the single-corpus trap arriving in
the **semantics** rather than in the fixtures. I wrote "not called" into the
design of the view whose entire purpose is making absence legible.

Consequences worth keeping:

- **Label states by the record, not by the world.** Name the source at least
  once where the states are introduced.
- **The four states are not one ordered set.** Two are positions on a scale of
  evidence, one is an absence of record, one is an anomaly. That is a second
  reason not to give all four one channel, independent of keel's.
- The general form: **an absence is always an absence *in* something.** Whenever
  a view derives a negative from a single source, the source belongs in the
  sentence, or the reader upgrades it to a universal for free.

**A published mapping changes on merges, not on releases.** The first producer's
file is regenerated by CI on every change under their source tree, so the
document at its URL moves whenever the provider does. Cache it as you would any
other content repository's file rather than as something with release boundaries
to key on. A view that assumes otherwise shows a reader the coverage of a commit
that no longer exists, and every number in it is plausible.

## Reaching the other boundaries, and being reachable

The other two boundaries are live agent sessions, not just repos, and most of the
good decisions this week came out of talking to them. Being unreachable is a real
failure mode, so this section is about addresses.

**Addresses are a remembered value and they rot.** By the rule elsewhere in this
document, prefer deriving them.

**But do not match on `cwd`.** An earlier draft said the durable identity of a
boundary is the repository it works in, discovered from a session's working
directory. That is wrong, and it is worth keeping the correction because of *how*
it is wrong.

`cwd` is genuinely derived. It derives **where a session was started**, which is
not **what it works on**. The specs corpus owner runs from a
`terraform-provider-power-platform` worktree and has never had a `cwd` inside
`powerplatform-apis`; no session anywhere does. A successor applying the `cwd`
rule would find nobody and conclude the specs owner does not exist. Whoever owns
the browser will very likely be working cross-repo too.

So this is the derived-versus-remembered test failing on its own terms: **a
derivation is only better than a memory if it derives the property you actually
need.** A stable-looking proxy for the right property is the more dangerous
shape, because it looks principled and returns a confident wrong answer where a
stale note would have returned an obviously missing one.

**How to find someone:** `ListAgents` lists live peer sessions by the name used to
message them; `mcp__ccd_session_mgmt__list_sessions` gives titles and `cwd`. Use
both to *enumerate candidates*, not to prove a role. `get_session` with `"self"`
returns your own address, which you need in order to tell anyone else yours.

**Snapshot as at 2026-08-28, correct then and quite possibly wrong now:**

- keel: **owned by a Codex agent from 2026-08-29**, addressed as `Keel` in the
  Codex `Keel` project. The Claude session that held it was `sch-9d`, then
  `keel-4b`; neither is the owner now.

**An address is valid only for the exchange it was observed in.** Not derived,
not remembered. Re-look it up per conversation.

That is stronger than this section's original advice and stronger than my own
first correction of it. I wrote that addresses shift *by a suffix*, having seen
`provider-api-client-libraries-827c35-d3` become `...-9f`. keel pointed out
their own name went `sch-9d` to `keel-4b`: **the prefix changed too, because the
project changed rather than only the session.** So the repo-matching derivation
this section endorses fails as well — it works only while a session name still
carries its repo, and keel's stopped doing so.

The failure mode is silent: messages simply do not land, and the sender has no
signal distinguishing a wrong address from a peer that is busy. Looking the
address up immediately before sending is the only thing that worked, and it is
what got this exchange through.
- Specs: peer name `provider-api-client-libraries-827c35-d3`, session title
  "Provider API client library separation".
- The session that wrote this document: `Power Platform Provider`, session id
  `local_a5362817-4349-4f53-a9ca-87f3083dbc98`. That session handed the browser
  over on 2026-08-28 and is not a standing address.

Do not trust that table. Derive, and use it only to sanity-check what you derive.

### Announcing yourself, which is a duty and not a courtesy

**This was carried out on 2026-08-28 and the section is now a record of how,
kept because the browser will change hands again.**

Whoever owns the browser after the extraction is a **new session with a new
address**, and both other boundaries have the old one. A message from an
unfamiliar name is easy to ignore, and both of them are correctly cautious.

So, early and before asking anything:

1. Message both boundaries, say you are the new owner of the OAS browser, and
   give your address.
2. **Prove it against repository state, which is the part they can check.** The
   browser repo is **`AdamCoulterOz/oas-browser`**, created 2026-08-28. Both
   boundaries have agreed this protocol:
   - State the current `HEAD` sha of `oas-browser`. Someone not actually working
     in it cannot produce that.
   - Name the four content commits the specs owner made: `479d340`, `07fc150`,
     `735f360`, `6173c64`. Someone without this handover cannot produce those.

   Together those derive the property that matters, which is *is this session
   actually working on the thing it claims to own*, rather than a proxy for it.
3. Ask them to confirm they have replaced the old address. Do not assume a
   message that got no reply arrived at someone who understood it.

**This protocol is weaker than it was written, and the correction went through
two rounds. Both are kept, because the second is the one that matters.**

*First round, and wrong.* I read the two checks as testing two different
properties, and said the sha proves you are working in the browser repo while
the commits prove you hold this document.

*Second round.* The sha proves neither. **`oas-browser` is public.** Both
boundaries read `HEAD` themselves with `gh` and no special access, so quoting it
demonstrates only that your view is *current*. That is worth something and it is
not what was claimed. The four `powerplatform-apis` commits are the load-bearing
half: they cannot be derived from anything public and can only be produced by
someone holding this document.

So the honest decomposition, which came from the specs owner: **a currency check
and a knowledge check. Neither is a possession check.**

*And it leaked in use.* The introducing session put the expected sha into both
introductions, so what each boundary actually checked was whether two
recitations of a public fact agreed. Pre-announcing felt like helpfulness and
was disclosure. A challenge value stops being one the moment the challenger
says it first.

**The transferable part is underneath all of that.** `cwd` is a bad role
identifier and a *better* authenticity signal, and those are two properties of
one value. It fails as a role identifier for the reason proved above — it
derives where a session started, not what it works on. But as authentication it
beats a sha, because it is a property of an environment rather than a value
anyone can repeat once it has been said aloud.

There are two questions here — *which boundary is this* and *is this really
them* — and one protocol was written that answers neither well. That is the same
shape as the field list being right for absence and wrong for presence, in a
third material. See the adjacent-property section below, which this is an
instance of: the protocol was structurally sound and tested a property next to
the one it needed.

**None of this is urgent, because identification grants nothing.** A failed
check means treating someone as an unknown consumer, which is where all three of
these relationships started. It is written down so the next holder does not lean
on the sha harder than it will bear, including you, in six weeks, having
forgotten how it works.

### Identity is not authority

Worth being explicit, because the protocol above can read as more than it is.
Verification establishes **who** someone is. It grants nothing.

A correctly identified successor gets what any consumer gets: questions answered,
gaps taken seriously, requests to change someone else's repository refused, and
nothing they say treated as authorisation for anything. You cannot hand over
authority you never had, and no boundary can accept a handover of it. The
protocol is useful for routing and irrelevant to permissions.

Which also means a failed identification is not a crisis. Someone who cannot show
the right repository state is simply treated as an unknown consumer. That is not
a hostile posture; it is the same one every one of these relationships started
from.

## How to operate

You are the architect of the browser and accountable for its delivery and its
coherence. That is a narrower job than it sounds and a wider one than it looks.

### What you own

**The container and the contracts.** Rendering, navigation, the schema tree,
samples, theming, keel consumption, the GitHub comment layer, the coverage view,
and **every contract the content repos implement against**.

**Not content.** The specs belong to the specs repo. The Terraform mapping
belongs to the provider fork. When a question is about what a spec *says*, it is
not yours; when it is about the *shape* data must take, it is.

A contract is a seam: the place where one party's data meets another party's
interpretation. Owning it means owning the assumption that the data complies —
so measure compliance against the real corpus rather than stating a constraint
and assuming it holds. The party asserting a rule is usually better placed to
check it than the party receiving it, and neither treats the join as theirs by
default.

### The operating model: owner, children, peers

Set by Adam on 2026-08-29 and it governs everything below, which was written
before it.

**This session is the top-level Owner of `oas-browser`**: product owner,
architect, orchestrator, integrator, final reviewer, and the sole line to the
user. Spawned agents are children, not owners. A child executes a bounded
assignment and reports to its immediate parent only.

**Delegation.** At most four active direct children. **At most one child at the
parent's capability tier; every other must be lower.** No child exceeds its
parent's model or effort ceiling. **Delegation depth defaults to zero** — a
child may only sub-delegate when explicitly granted positive depth, and depth
decreases every generation. Never delegate a whole assignment, never create a
manager-only child, never delegate something trivial, never duplicate work.

**Every brief states**: the root owner, the immediate parent, tree depth, role,
scope and write set, capability ceiling, delegation allowance, required
evidence, and only the upstream context the child actually needs.

**Communication.** A worker talks to its immediate parent and its own children.
Not to the user, not to siblings, not to higher ancestors, not to other sessions
or other repositories' owners. **Cross-repository needs bubble up one parent at
a time to the top-level Owner, and only Owners talk peer-to-peer.** Decisions
and evidence come back down the same chain. The Owner alone accepts work,
coordinates peers, and presents to the user.

**Where the briefs in this repo's history do not meet it, so nobody copies
them as templates.** The delegation done on 2026-08-28 complied on the parts
this document already argued for — criteria authored by the owner, explicit
write sets, evidence required as mutation results rather than assertions, all
cross-boundary contact kept on the owner's thread, every child's work reviewed
and pushed by the owner. It failed on the structural parts, which were not
stated anywhere at the time:

- **No brief named a capability tier**, so every child inherited the parent's.
  Four concurrent children at the owner's tier is three more than the model
  permits.
- **No brief stated a delegation allowance.** One child spawned a follow-up task
  chip, which is a sub-delegation nobody had authorised, and the fact that it
  was a good suggestion is beside the point.
- **No brief stated root owner, parent, depth or role**, because the tree was
  one level deep and it felt obvious. It is obvious to the parent and invisible
  to the child, which is the same audience error this document records about
  failure messages and about statements of state.

### Delegate implementation. Keep judgement.

Delegate freely within the model above. Sub-agents do the work; you assign,
review and communicate.

**Non-delegable:**

- **Authoring the criteria** a reviewer applies. This is the real skill. A vague
  "review this" delegated is worthless; a specific criterion delegated is as good
  as doing it yourself. Each criterion should name *the specific thing that would
  be missing*, so it is a pass/fail someone without your context can apply.

  **And when briefing, transfer the gotchas this document already holds.** Two
  briefs of mine told an agent to publish and serve the app and omitted
  `rm -rf dist` and the import-map step, both of which are in *Practical
  gotchas* and both of which cost the agent a broken run it had to diagnose.
  Owning a list of hard-won failures is worth nothing if it is not consulted at
  the moment somebody is about to hit them, and the moment is the brief.

  Likewise **state expected numbers as of when, or leave them out.** A brief of
  mine quoted a corpus total that had grown by eight operations since I wrote it
  down. The agent measured, disagreed, and was right — but the safe outcome
  depended on it checking rather than trusting me, which is the wrong way round
  for a figure I supplied as ground truth.
- **The go/no-go on release.**
- **Cross-boundary communication.** Requests and responses to keel and the
  content repos stay on your thread. Do not delegate a relationship.

**A reviewer must be a different agent from the one that did the work, and must
not be given its report.** An agent confirming another agent's summary is not a
check. Have it re-derive the evidence; if its number differs from the expectation
you gave, that is information, and it should say so rather than reconcile toward
you.

### Release discipline

- **Gate before you push**, with independent re-derivation.
- **Seal the tree during a gate.** A commit landing mid-run invalidates the
  verdict.
- **Do not grow a held release.** A blocked release attracts work, because every
  improvement that lands while it is stuck looks free to include. That is how a
  release stops shipping permanently. The largest pending change is always the
  worst candidate.
- **A move should move known-good code.** Never relocate and rewrite in one step;
  a later failure becomes ambiguous between two causes.
- **Verify a deploy with a cache bust.** Pages sets a short max-age on
  `index.html`; a post-deploy check without one reports the *previous* build as
  current. This produced a false pass once already.
- **When you vouch for an artefact to someone else, audit the artefact they will
  receive, through the channel they will receive it.**

  A consumer's user was deciding whether to fetch and execute a checker this
  repo publishes. I audited it — imports, no subprocess, no eval, one network
  call, writes nothing — and sent the result as the basis for that decision. The
  audit was **exact about the file I ran it on**, which was my uncommitted
  working copy. What `main` served was 672 lines to my 1408, predating every
  change in the contract they were checking against. They fetched it, ran it,
  and got 165 findings that were all the checker being older than the format.

  Every sentence I wrote was true and none of it was about the artefact anyone
  could obtain. That is the adjacent-question failure with the highest stakes it
  has reached here, because the answer was carried across a boundary and used by
  somebody else to make a safety decision. Rigour is what made it feel settled.

  The rule *gate before you push* has an inverse that nothing here had stated:
  **gating without pushing leaves an artefact that only you can see, and
  describing it to anyone else describes nothing they can run.** Verify through
  the consumer's path — fetch the URL, check the sha, diff against what you hold
  — because "I checked it" and "I checked what you will get" are different
  claims and only the second is worth anything to them.

  Related, found in the same minutes: `raw.githubusercontent.com` serves with
  `cache-control: max-age=300`, so it kept serving the old file for two minutes
  after the push. A consumer's re-run inside that window disagrees with one
  outside it for no reason visible to them. The cache-bust rule above, arriving
  in a distribution channel rather than in a deploy check.

### Working in a shared tree

More than one writer will be in a repo at once, some of them not yours.

- **Stage explicit paths. Never `git add -A` or `git add .`.**
- **Keep every diff small enough to read** — that is a review control. A
  reformat that turns a three-line edit into a 4000-line diff hides whatever else
  is in the commit, and did.
- **A constraint protecting a shared resource must be addressed to everyone who
  can touch it, not to everyone you are directing.** This failed twice: both
  times a rule was given to sub-agents and not to the peer session in the same
  tree. The resource does not care who manages whom.
- The counterpart, and the cheaper of the two: **before committing to a shared
  tree, ask whether anything is running against it.** Where a defence can sit on
  either side, put it on the side that does not have the information.

### Reporting across a boundary

- **Calibrate a rule before you dispatch it.** A rule with an unknown
  false-positive rate does not transfer knowledge, it transfers triage of your
  own output. Run it yourself first.
- **Say when a finding is single-site.** One instance plus a measurement feels
  complete and cannot distinguish a local mistake from a systemic one. Name what
  would tell those apart.
- **A consumer can only find defects in the layer it touches, so silence about a
  layer is not evidence about it.** Two consumers on different paths are two
  instruments measuring different things, not two measurements of the same thing.

  The evidence, from keel sorting one day's consumer-found issues by layer: every
  markup-and-structure finding came from its static consumer (a closed drawer
  still focusable, `<div>` where a `<button>` was needed, undocumented behavioural
  obligations). Every parameter-surface and vocabulary finding came from this
  browser (an emphasis axis not orthogonal to tone, a variant present in CSS and
  absent from the enum, tones carrying meanings they cannot express, missing
  density and icon axes). **Neither found a single instance of the other's
  class**, on the same system, on the same day, both looking hard.

  Not because either was less careful. A component consumer never sees the
  element, the roles or the focus handling, so a defect there is invisible from
  where they sit — the abstraction that makes the path pleasant is the one that
  hides its most likely failure. Symmetrically, a static consumer never touches
  the parameter vocabulary and cannot report a defect in it.

  Two consequences worth carrying into this browser's own consumer relationships:

  1. **Do not read "nobody has reported X" as "X is fine."** Read it as "nobody
     who touches X has reported it", and then check whether anyone touches X at
     all. `KeelSelect` being an unremarked restyled native select was not evidence
     it worked; it was evidence nobody had built a form.
  2. **Divergence between two consumption paths is worse than a consistency
     defect.** It destroys the *generalisability* of reports: each consumer's
     finding stops being true of the system and becomes true only of their
     surface. You lose not just correctness but the ability to reason from one
     report to the whole.
- **Check the neighbours before sending.** The pull that produced a defect
  usually produced more than one instance. Reporting one line when the next line
  has the same bug wastes the recipient's second look.
- **Attribute precisely.** With several parties converging on one subject,
  findings blur, and attribution is not courtesy — it is knowing who to ask when
  there is a follow-up question.
- **Escalate what you own.** Being in contact with someone is not the same as
  owning the question. Proximity is not authority.
- **Do not forward an observation as a claim.** A producer reporting something
  about their own extraction is describing *their* artefact. The same sentence
  arriving at the corpus owner is a claim about *theirs*, and the two are
  different assertions with different burdens.

  The worked case: a mapping producer reported a call carrying no `api-version`
  on a path where the corpus requires one. Held rather than forwarded, pending
  the exact path. The path turned out not to exist — their extractor had missed
  a second call site — and three further extraction defects surfaced from
  chasing it.

  Had it been forwarded, the corpus owner would have searched a corpus that was
  already correct and found nothing. Their own account of why that is worse than
  it sounds is the part to keep: **the likely outcome is not "no finding", it is
  a carefully documented note recording that the thing was not observed. A wrong
  finding is expensive; a wrong finding documented as unconfirmed is worse,
  because it looks like diligence.**
- **A retraction that never arrives leaves the original claim standing**, and
  the original claim was about somebody else's work. Chase the follow-up on a
  claim you held back, and pass the retraction with the same weight you would
  have passed the finding.
- **The party holding the data does the analysis. Do not send them a
  conclusion.** This is the same rule as *owning a contract means owning the
  assumption that the data complies*, pointed the other way, and it is easy to
  get backwards while being helpful.

  The instance: 25 of a producer's 131 operation references did not resolve
  against the corpus. Asking the producer to characterise them was the wrong
  request, and the corpus owner said so — it puts the analysis with the party
  who does not hold the corpus, index or checks, so whatever came back would
  have been a theory about somebody else's data formed without it. The raw list
  costs the holder minutes and the non-holder hours, and only one of those two
  answers is worth anything.

  The general form: **when a question spans two parties, the cheap accurate
  answer and the expensive speculative one are usually on opposite sides of the
  boundary.** Ask which side can answer it, not which side noticed it.
- **When challenging from partial visibility, challenge the question rather than
  the answer.** You will often see enough to notice something is unexamined and
  not enough to say what the conclusion should be. Those are different claims and
  only the first is available to you.

  A worked instance: keel was documenting a static consumption path, and it
  looked like the path was being documented merely because it existed. The useful
  intervention was not "this path should not exist" — that was unknowable from
  here — but "'write it down' and 'should it exist' are different questions and
  only the first is being asked". That got the second question asked. The answer
  turned out to be decisive and against the challenge: there is a real static
  consumer, and it had found most of that week's structural bugs precisely by
  using that path.

  The challenge was still worth making, and being wrong cost nothing, because it
  was framed as a gap in the reasoning rather than a verdict on the outcome. Had
  it been phrased as a recommendation it would have been an outsider overruling
  someone with strictly more information.

### Conduct

Take corrections properly: state what was wrong, why, and what replaces it.
Several of the most valuable rules here arrived as someone else correcting a rule
of mine, and two of them were corrections to corrections. Disagree where you
have grounds; the boundaries are peers, not clients.

## The keel relationship, in detail

The rules for consuming keel, its current release plan, and the open items
between you. The addressing and announcement protocol is in **Reaching the other
boundaries** above; this section is the substance of the relationship rather than
how to reach it.

**Upstream: keel** (`/Users/adam/Code/GitHub/AdamCoulterOz/keel`), Adam's design
system, consumed as a private NuGet package. Rules, which are not optional:

1. keel owns how every control looks. This app expresses intent and arranges
   things. Never hand-roll a control, colour, spacing value or breakpoint keel
   could own.
2. If keel lacks something, ask keel. Do not work around it. A local override is
   a keel bug report, by keel's own rule.
3. **Build against keel's published documentation. That is its interface and
   what it contracts to.** Do not code against its source.

   This rule has been round the houses, so here is where it landed and why, since
   the reasoning matters more than the instruction.

   An early version said docs-only, applied so strictly that reading the source
   felt like a boundary violation. keel's owner corrected that: the boundary is
   about *changing* keel, not reading it, and their generated reference had
   drifted from the enums it describes, so source was the more reliable text.
   Both true. But the conclusion — treat source as the interface — is wrong, and
   Adam's correction is the one that stands:

   **A dependency's contract is what it publishes.** Code against its
   implementation and you couple to things it never promised and can change
   without notice. That the published document happens to be wrong today is a
   defect to fix, not a reason to depend on something else.

   The decisive argument is what each posture does to the documentation over
   time. **Reading source removes the pressure that keeps docs honest.** If
   consumers route around a bad reference, nobody depends on it, so nothing
   forces it true and it decays freely. The live proof is `ButtonVariant`:
   `.keel-btn--destructive` exists in the CSS, `Destructive` does not exist in
   the enum, and the reference told both consumers it did — for at least four
   releases, unreported, because each consumption path read its own side rather
   than the published contract.

   So, in order:

   1. **Build from the docs.** If a documented value does not exist, you get a
      compile error, and *that is the correct outcome*: a loud, mechanical,
      undeniable signal. Report it as "your documented value does not exist",
      which is precisely accurate and lands on the right layer.
   2. **If the docs do not answer it, ask keel.** It is a live session. It knows
      how its own system works and can tell you in one message, without you
      reconstructing that understanding from its implementation.
   3. **Never build against something the source offers and the docs do not
      promise.** That is the coupling this rule exists to prevent.

   **If you find yourself reverse engineering how to use keel, stop: that is
   already a bug against its contract.** The need to do it *is* the finding.
   Report it rather than satisfying it.

   And the reason this matters more than tidiness: **answering your own question
   from source destroys information.** Asking produces two things — your answer,
   and a signal to keel that its contract is missing something. Deducing produces
   only the first. The gap that sent you looking then survives, unreported,
   because the only person who noticed it has quietly worked around it. That is
   how `ButtonVariant` stayed wrong for four releases.

   Reading source to *substantiate a defect you have already found* is fine, and
   makes for a better report. Reading it to work out how something is meant to be
   used is not, however convenient. Ask.
4. **Choose a token by meaning, never by appearance.** A tone reports a *state
   the thing is in*. Before using one, ask what state the element is actually in.
   If the answer is "none, this is a permanent fact about it", a tone is the
   wrong tool and the answer is usually typographic. A token used outside its
   purpose works by coincidence, and keel has not agreed to preserve the
   coincidence, so it breaks later and more confusingly than it would have now.
5. Report by messaging the keel session directly, not by filing GitHub issues.

Open with keel, and its release plan for them:

- **0.4.3, additive. Taken, and current.** Their component reference generator,
  which was silently understating the size of an enum. `KeelNavBar` gaining
  horizontal padding and moving its burger to the trailing edge. And the new ink
  tokens (`--success-text` and siblings), which add values without changing any,
  so contrast fixes do not wait for the breaking release. Note the nav padding
  shifts the effective container-query collapse threshold, and this app's rail
  switches at 880px keyed to keel's `Size.Lg`, which sits exactly on that
  boundary. Re-check against their corrected arithmetic rather than assuming.

  **What taking it cost, which is the useful part.** 0.4.3 improved every
  ink-against-ground ratio and degraded every ink-against-ink pair. Measured
  across both versions rather than inferred: tertiary on `--surface-subtle` went
  3.33 to 6.01 in light, and the *same token movement* took this app's request
  line from 4.65 to 2.57, a 45% loss. One change, two axes, opposite signs. See
  **the adjacent question** below; this is its cleanest quantified instance.

  **No keel release can be assumed safe for a pair, because keel commits a ratio
  for no pairs at all.** Everything it promises is ink against ground. That is
  not an under-documented area, it is stated: a layout relying on two inks being
  distinguishable is relying on something never promised, and 0.4.3 is the proof
  that such reliance breaks with no check anywhere able to flag it.

  The consequence for this app is a rule rather than a retune: **where colour
  distinguishes two things a reader must tell apart, add a cue that is not
  colour.** Picking two inks further apart is the obvious repair and the wrong
  one, since it re-buys a guarantee that does not exist.

  The discriminator, which is the part worth keeping, because no flat threshold
  works: this app's two colour-separated pairs are 2.57 and 1.39, and **the
  worse-looking number is the healthy one.** The 1.39 pair is mono against sans
  with a separator and a gap, so colour contributes nothing and is not being
  asked to. The 2.57 pair inherits family, size and weight from its parent and
  has no separator at all, so colour is not the primary cue but the only one. A
  pair whose colour contribution is near zero and whose non-colour cue is strong
  is the state you want, not a defect. I nearly "fixed" the healthy one.
- **0.5.0, breaking.** `Emphasis` gains a `Loud` rung so it becomes a real
  loudness ladder and `New` stops being the one tone that renders differently
  under `Filled`. keel's own components move onto the ink tokens. `KeelCallout`
  gains a density axis, at which point `.notes--compact` here can be deleted.
- **Still open, no date.** A sidebar rail component, and a disclosure primitive
  (their issue 7).
- **#26, confirmed against the shipped 0.4.3 component.** `KeelCallout` has
  `Tone`, `Title`, `ShowIcon`, `Live` and `ChildContent`. `ShowIcon` is a bool
  and there is no way to supply an icon. This is what gates separating the two
  non-observed evidence grades by glyph, and keel considers it the right fix for
  that case rather than the categorical palette in #23, since a glyph difference
  survives a colour vision deficiency where two hues inside one tone do not.

  **Do not let it block the trunk.** 535 nodes carry provenance markers, 419 of
  which need only the observed against not-observed binary and nothing from
  keel. Build those; add the subdivision for the remaining 115 when #26 lands.
  keel has said explicitly they would rather this app shipped the trunk and told
  them the branch is waiting than have 419 nodes sitting on their backlog
  position.
- **#42, filed by keel from this app's report.** There is no vocabulary for
  content the system deliberately withheld: not an error, since nothing failed;
  not a warning, since there is nothing to act on; not disabled, since it was
  never available; and not a tone, since a tone reports a state and "refused" is
  a permanent fact about that link in the way "required" is about a parameter.
  The category is larger than links and covers redacted, elided and sanitised
  content. The constraint on any naming: **the absence is the information**, and
  a reader must not be able to confuse "nothing was here" with "something was
  here and is not being shown". That rules out both silent dropping and
  error-flavoured marking, and it is the same rule that forces
  `x-probe-verified` to render both states rather than only the true one.

  Until it lands, the hand-rolled textual marker in `Markdown.cs` stays. keel's
  reasoning for taking the gap rather than saying "use `Warning`" is worth
  keeping: reaching for a tone there would repeat the `--warning`-on-required
  mistake in a new place a month later.

**Do not pre-emptively change any tone or emphasis value ahead of 0.5.0.** A
migration table is coming with it.

**Two different bugs that look identical in a grep.** keel's `--success`,
`--warning` and `--danger` are fill-strength values that fail WCAG AA when used
as text: 3.09:1, 2.77:1 and 4.36:1 on white. An audit of every state-token-as-ink
use is in progress, and it separates two kinds of hit, because they need
different fixes and only one of them is keel's:

1. **Contrast failures.** The token carries the right meaning but is not legible
   in that role. keel's fill/ink/on split fixes these; they wait for 0.5.0.
2. **Tokens chosen by appearance rather than meaning.** Semantically wrong, and
   no retuning fixes them. Ours, and mostly fixable today.

The worked example of the second kind, which is the more instructive one:
`.prop__req { color: var(--warning) }` renders the word "required" on every
schema property. Ask what state that property is in. It is not in a warning
state, has never been in one, and cannot enter one: being required is a
permanent fact about the parameter's shape. Amber read as alert-ish and
alert-ish felt right, so the token that happened to be amber got picked.

The contrast failure is what made it visible, but the line would still be wrong
if amber were perfectly legible. Fixing it by swapping in a text-safe warning
token later would correct the ratio and preserve the error, permanently, with
nothing left to surface it. It is emphasis rather than state, so the tool is
typographic: heavier weight and `--text-primary` among siblings at
`--text-secondary`, which also survives greyscale and colour vision deficiency.

**Downstream: the two content repos.** They implement the browser's contracts
and ask questions of it. Handle those directly rather than delegating them.

**Delegate implementation to sub-agents.** The non-delegable parts are:
authoring the criteria a reviewer applies, the release go/no-go, and
cross-boundary communication. Everything else, including review and release
mechanics, can be delegated if the criteria are specific enough.

## The failure pattern, which is the most valuable thing here

Four separate bugs in one week, all the same shape: **the surface renders
correctly and the meaning is gone.**

- A chip whose label was off-centre, because it was not the design system's chip.
- A link that still looked like a link, with no `href`, because a component
  tested the wrong field for "disabled".
- A live site serving a previous build, because `index.html` was cached.
- Every `$ref`'d parameter dropped, so whole operations rendered with no Request
  section at all.

Every one passed a screenshot. Every one was found by reading the rendered DOM
or the computed styles.

So: **the test is never "does it render".** It has to name the specific
distinction the thing exists to carry, and it has to be named *before* looking,
because absence is the one thing you cannot see. The best-phrased instance of
this, from the callout work: not "do both callouts render" but "can you tell the
two grades apart at a glance, without reading the words".

Note the two directions this failure runs in. Something can vanish, which leaves
a gap someone may eventually notice. Or a marker can be lost while everything
still renders, in which case the page quietly asserts *less* than the corpus
earned and looks identical to the honest version. A dropped provenance marker is
the second kind: nothing is missing on screen, the content simply starts reading
as unverified. Assert on counts, not on appearance.

### Where these hide, and why rules do not stop them

A related lesson, from a finding that two careful sweeps both missed. The task
was "move findings out of descriptions into notes", so one pass searched
descriptions for findings and another searched notes for house-rule violations.
A house-rule violation sitting in a *description* fell exactly between them.

Neither pass was careless; each did what it said. The bug lived in the seam. When
work is split into passes, the seams between them are where to look, and they
are invisible from inside either pass.

The general form, which explains why this keeps recurring:

> When you add a member to a set, the new member is the thing under review, so
> attention lands on it. The relationships are all *between* the new member and
> things nobody is currently looking at. There is no moment in a normal review
> where the pair is the subject.

This is why writing a rule down does not defend against it. Item 8 below is a
defect that survived a rule written specifically to prevent it: "never merge
grades" is a property of the *set*, and the review was of a *member*. A correct
rule about the whole is invisible from inside an inspection of a part, and gets
read as being about the part.

So the defence is not more rules. It is changing what the review takes as its
subject: **make the pair the subject, not the member.** The family-asymmetry
check under the keel rules is the same idea applied to a family rather than a
pair, which is probably why it works. It forces a comparison rather than an
inspection.

**And the stronger version, where it is available: build the constraint into the
shape of the thing so the violation is unsayable.**

> A rule that holds because the design cannot express the violation is a
> different class of thing from a rule everyone remembers to follow.

The evidence is this repo's own. *Colour must not be the sole cue* was written
down, understood by both parties, and violated twice this week in a file both
were editing while discussing it. More documentation would have changed nothing,
because nobody involved was unaware of the rule. What fixed it was keel
designing a component whose ordered states are carried by fill and whose
anomalous state is carried by shape, so a consumer *cannot* express the
distinction in hue alone — the discipline is discharged by the type rather than
by the author.

The same move appears elsewhere in this document without being named: naming the
observed grade once on the set rather than as a boolean per member makes "two
observed grades" unrepresentable rather than merely invalid, and requiring
`calls` to be present makes an empty one a claim rather than an omission. Reach
for it whenever a rule has already been broken by somebody who knew it.

Every instance this week has this shape, and in each one the thing under review
was genuinely fine: a token that passed in light while dark was not the subject;
a chip whose label was fixed while *why it was off-centre* was not the subject;
a new grade that rendered correctly while its relationship to its neighbour was
not the subject.

### The same pattern runs along ownership boundaries

The seam is not only between two passes of a review. It also runs between two
owners, and that version is more dangerous because nobody is looking by
construction rather than by inattention.

The worked example, which is exactly the shape the three-repo split creates.
`x-source` is the node-level provenance vocabulary. One spec was also using that
key at its document root to hold a prose paragraph about how the whole spec was
derived. Wiring up node provenance generically — which the browser had *asked
for* — would have read the paragraph as a grade and rendered a heading beginning
"Reported by Rewritten from 18 browser HAR captures...". Structurally valid,
syntactically fine, semantically absurd, and nothing would have errored.

Neither side was careless. The vocabulary belonged to the corpus owner. The
rendering belonged to the browser. **Its consistency belonged to neither, so it
went unexamined until it broke.** Each assumed it sat in the other's territory.

This is the thing to carry into the split, because the split multiplies these.
The browser owns the contracts, and a contract is precisely a seam: the place
where one party's data meets another party's interpretation. So:

**Owning a contract means owning the assumption that the data complies with it.**
Do not state a constraint to a content repo and assume compliance. Measure it
against the actual corpus, because the person who asserts the rule is usually
better placed to check it than the person receiving it, and neither party
naturally treats the join as theirs.

### Make the contract executable: one definition, many runners

The rule above is worth little as prose. The `x-source` collision was catchable
by a five-line script in under a minute; it survived only because writing that
script was nobody's job. A check in CI is what converts "nobody's job" into "the
build's job".

The arrangement that survives the split, and the reason for it:

- **The browser repo publishes the conformance checker**, because it is the
  contract owner and it is the party that breaks when the contract is violated.
- **Each content repo runs it in its own CI**, because that is where the data is
  and where a violation must block a merge.

Do *not* let each content repo write its own checker. That puts the definition of
conformance in the corpus, so the next invariant the browser adds has to be
independently discovered by every content repo, and the moment one lags, the
browser is consuming a corpus checked against an older contract. Same seam, one
level up: my assumption, their file, nobody owning the correspondence.

Invariants to carry, in their general form (the concrete Power Platform versions
exist today and must be generalised at extraction, since the browser may not know
what Power Platform is):

- Every `x-source` is one of the grades **that corpus declares**. Not a
  hardcoded triple: grade vocabulary is corpus-declared, so the invariant is
  agreement between a corpus's declaration and its usage, and it holds for a
  corpus with one grade or five.
- No key in the node-level extension namespace appears at the document root with
  a different meaning. This is the general statement of the `x-source` collision,
  written so it catches the next instance rather than only that one.
- Every `x-notes` entry is a string, or an object with `note` and a declared
  source.
- No `$ref` dangles.
- `x-probe-verified` is boolean, never a string.

**A rule with an unknown false-positive rate cannot be dispatched.** Calibrate
before you send it to anyone, including a sub-agent. The recipient cannot
distinguish a finding from noise, so an uncalibrated rule does not transfer
knowledge, it transfers work — and the work is triage of your own output.

This is not hypothetical. Two rules elsewhere in this project were correct in
principle and unusable in first form: one produced 18 hits with none real, the
other 59 with one real. Both would have read as substantial findings to whoever
received them.

The practical form: a matcher over prose over-fires, because prose legitimately
contains words that look like the thing you are matching. Scope it to where the
claim is checkable — for the enum-drift check above, only parameters whose type
is actually a keel enum, matched only against that enum's own members — and run
it yourself before it leaves your hands.

**The two error directions are not equally bad, and which one is worse depends on
what you are checking.** Calibrate for the direction that matters.

For a *findings* check, over-firing is the expensive failure: noise buries the
real hits and the recipient cannot triage. For a *safety* check, under-firing is
the one that hurts, because a clean report is indistinguishable from a clean
system.

The instructive case, from keel testing its own HTML escaping after this repo
flagged an injection surface: their first detector reported seven leaks, all
false, because it matched the literal string `onerror` — which survives correct
escaping *as text* and is therefore evidence the escaping worked. Their own
summary is the part to keep: **a false positive cost a minute; the same
carelessness pointed the other way reports clean on a real hole.**

So a naive matcher is a nuisance in a findings check and a hazard in a security
check. Before writing either, ask which way yours fails when it is wrong, and
prove that direction specifically by feeding it something that must be caught.

**And there is a worse state than miscalibrated.** That detector was not simply
over-eager: `onerror` appears in the attack *and* in the defence, so it could not
distinguish them at all. It fired on its own success condition. It over-reported
there by luck of the payload; a different payload and the same detector reports
clean on a real hole, for the same reason.

A check that cannot tell the failure from the fix is measuring the wrong thing,
and its error direction is then **arbitrary rather than unknown** — which is why
observing that it fires tells you nothing about whether it works. Ask what a pass
and a fail actually look like to your check before trusting either.

**And there is a fourth state, worse than arbitrary: a check whose error is
*anti-correlated* with the truth.** It does not merely fail unpredictably. It
passes most reliably in exactly the case it exists to catch.

The instance is the post-deploy check in *Practical gotchas*. Pages sets a short
`max-age` on `index.html`, so a check that fetches it without a cache bust reads
the *previous* build. If the deploy worked, the cache may have expired and the
check is right by luck. **If the deploy did not take, the previous build is
still current and still cached, so the check confidently confirms the thing it
was written to detect the absence of.** The worse the failure, the more reliably
it reports success.

The framing came from the specs owner and it is worth carrying: that is not a
flaky check, and calling it flaky invites someone to retry it. It has to be
fixed, and **the fix has to carry its reason where it is read**, because a
cache-buster with no comment looks like superstition and gets tidied away by the
next person. Anything that survives only while everyone remembers why is a
hand-maintained list wearing a different costume.

The general question to ask of a check: not only *which way does it fail*, but
*is the case it fails on the same case it exists for*. Those come apart more
often than they sound like they would.

**A test environment can be built so the bug is unreachable, and that green is
worse than an untested case.**

The browser shows the origin its catalogue was fetched from, so a catalogue
cannot lie about where it came from. It was verified locally against a second
origin on a different port, in a browser, and it worked. Loading a real corpus
through its real redirect showed the marker reading the same origin for two
different corpora, because they are two paths on one host, and the whole URL is
the only thing that separates them.

**A second origin on a different port is the one arrangement where "which
origin" and "which catalogue" never come apart.** The environment was
constructed so that the defect could not appear. Nothing was skipped and the
verification was real; it measured a configuration in which the question could
not arise.

That is worse than not testing, because an untested case looks untested. This
one produced a green that felt like coverage, in a browser, against a live page.

**And the general form, which is the more useful half: one is the number at
which cross-thing mistakes cannot occur.** Every check this repo has about the
relationship between two files — the catalogue a mapping declares against the
one loaded, the origin display, spec ids colliding with route segments — is
exercised against a single corpus and a single mapping. Single is the
configuration in which a cross-corpus error is unreachable by construction.

So the fixtures want a second catalogue, not because anyone needs two corpora
but because **one is the count at which these checks cannot fail.** The same
argument as proving an invariant by making it fail, applied to the shape of the
fixture set rather than to the assertion.

**Behaviour encoded in a container comes along unnoticed, or is lost unnoticed,
when you lift the code out of it.**

A resolution rule looked up operations in a `Dictionary` built with
`StringComparer.Ordinal`. That comparer was the rule "an operationId differing
only in case is a different operationId" — a real decision, stated nowhere, held
by the container rather than by the code. Lifting the logic to a linear scan
preserved it only because whoever typed the comparison happened to write
`Ordinal`, and **a mutation folding case survived the whole suite**, because
nothing had ever written the rule down.

So when you move code out of a structure, ask what the structure was deciding.
A comparer, a key type, an ordered collection, a set that silently deduplicates:
each is a behavioural claim wearing a data structure. The lift either drops it
or reproduces it by luck, and both look identical afterwards.

The mutation is what found it. A survivor is not always a hole in the tests; it
can be a rule that was never anywhere but in a type argument.

**Prove each invariant by making it fail.** Every check in the first version was
run against a synthetic violation and required to go red, including the real
`x-source` collision reverted on purpose. This matters because *a check that has
never failed is indistinguishable from a check that cannot fail*. Both are green,
and no observation separates them except making one fail deliberately. It is the
pattern in this document applied to the test instead of the page.

**And the other half of that, which arrived from a producer about to run a
checker for the first time: when you know in advance what should fail, a pass is
the finding.** Their file contained 21 rows they knew could not resolve — seven
naming operations a corpus had not published yet, two spelling a path the way
their code wrongly spells it, and others. Their own account:

> I would be more worried by a green run than by those findings. A green run
> would mean either the corpus had quietly grown seven operations nobody has
> added, or my resolver had started matching things it should not.

So a first run gets a real pass condition instead of a vacuous one. Not *does it
come back clean*, but *does it come back with exactly the failures I named, and
are they the ones I named*. More is a defect in the checker or the format; fewer
means something resolved that should not have. **Write the expected set down
before running, so the run cannot talk you into a number** — a count you read
first is very hard to disagree with afterwards.

**It paid on first use, twice.** The first run was against a stale published
checker that could not perform the operation-level check at all, and reported
zero catalogue findings. Their words: without the written expectation they would
have read that as their rows resolving cleanly. **Zero findings from a check
that did not run is indistinguishable from zero findings from a check that
passed.** Nothing in the output separates them.

And when the real run came back, they compared the **multiset** rather than the
total — ten finding shapes at the expected multiplicities, not just 21 against
21. A count is a hash of the thing you care about with a very high collision
rate, and twenty-one findings that happen to number twenty-one while being
different findings is a completely available outcome. Pre-register the shapes,
not the number.

**A static check cannot see "worse than it was", and some defects have no other
symptom.** This came from keel, from the 0.4.3 contrast work, and it is a
distinct claim from the delta rule below rather than a restatement of it. That
rule is about *reporting* a delta honestly. This is about a whole class of defect
that no assertion over a single state can detect.

The instance: 0.4.3's ink pairs were not wrong in isolation. Every one of them
would pass any threshold you could write down, and the release improved every
guarantee keel had actually made. What happened is that a pair got **worse than
it had been**, by 45%, and there is no state-at-a-point assertion that sees that,
because nothing was violated at either end.

So two artefacts are needed and they are not interchangeable:

- a **static check**, which is what a party can be held to, and
- a **release diff over two versions**, which is the only thing that catches a
  regression whose endpoints both pass.

Only the second would have caught it. Worth carrying into this repo's own
checker, which is currently conceived entirely as the first: the conformance
invariants all assert properties of one corpus at one moment. A corpus that
quietly loses half its notes between two publishes satisfies every one of them.
The fixture assertions have the same shape and the same blind spot.

**What to diff, when it gets built.** Do not guess the invariants — ask the
producer, because they know which numbers their own failures move. The first
coverage producer named three unprompted, and their reasoning is the whole
argument in one sentence: *my four extraction defects today all moved the
full-versus-partial split, and none of them moved it enough to look wrong.*

- total rows
- `uncatalogued` count
- the full-versus-partial split
- item count, added after a fifth defect emitted 58 items where there were 60

**The property they share is that a wrong value is a plausible value.** None of
those five defects produced an error, a malformed file or an implausible number.
That is what makes single-state checking blind to them and what makes the diff
worth building: not that the numbers are important, but that nothing else can
tell you when one has drifted.

**An equality assertion is the wrong half of the pair when the risk is undue
sameness.** `tools/contrast_pairs.py` had a bug where the dark theme resolved to
the light declarations, so it printed light figures under a dark heading: every
number correct, the whole table answering a different question from its own
column header. keel checked their own apparatus and did not have it, but found
something better in the checking.

Their suite asserts that Light equals KeelLight and Dark equals KeelDark. It
never asserts that the two groups *differ*. So a broken resolver satisfies every
assertion that exists and violates only the one that does not: primary comes
back near-black, the ground comes back white, the pair reads 15:1, and the dark
half of the suite silently becomes a duplicate of the light half while staying
green.

The general form, which is the adjacent-question pattern inside a test suite:
**when a resolver can fail by collapsing two things into one, checking that each
thing is internally consistent is the check it would pass.** The assertion has to
be that they are not the same. A canary comparing one token across the two
themes is enough, and it is the only assertion in the file whose failure means
"the apparatus is broken" rather than "the values are wrong".

**And keep the hand-computed result after the tool exists.** The tool's bug was
caught only because a set of numbers computed by hand, before the rewrite,
existed to reconcile against. Written tool-first it would have been
self-consistent and wrong, and nothing in its output would have said so. The
instinct after building a tool is to delete the manual working as superseded.
That working is the only independent thing that can contradict the tool, so
deleting it removes the sole means of falsifying it, at exactly the moment the
tool starts being trusted.

**Known limitation, and the fix that is NOT the answer.** The root-collision
check compares key *names*, not meanings, so a key legitimately used at both
levels with the *same* meaning would be a false positive. None exists today, and
over-strict is the right default.

If a genuine case appears, **do not add an exemption list.**

The general rule, which is worth more than the specific advice: **does this
answer come out of the data, or out of someone's memory of the data?** A derived
answer stays true by construction. A remembered one is correct on the day it is
written and cannot tell you which day you are on. The two look identical in the
source and differ entirely in six months.

**One real qualification, because the rule is not absolute.** A remembered list
is defensible when you are testing for **absence** and indefensible when you are
testing for **presence**.

The worked example. The structural verification strips `description` and
`x-notes` and compares the rest — a field list, deliberately. That is correct
there, because the question is *did anything else move*, and a list of things to
ignore is exactly the right shape for it. The same list used to answer *did I
find them all* would have been wrong: nine of the ten broken cross-spec links
were in descriptions, and the tenth was in `info.x-write-surface.notDocumented`,
a custom extension nobody would have thought to enumerate.

Same list, opposite validity, depending on the direction of the question. So the
test is not "is there a list" but "would a thing missing from this list change my
answer". For absence, no. For presence, yes.

The conformance checker's link scan therefore walks **every string value in the
document** with no key filtering, and that is why it caught all ten. It is
written that way deliberately; do not "tidy" it into a field list.

The conformance checker itself demonstrates both, in one file. Its root-collision
check computes the node-level extension set *from the document*, so it stays
correct as extensions are added. Its `GRADES = {"live", "pac-cli", "provider"}`
is a literal, and rots.

Five instances of the remembered kind so far: keel's reduced-motion allowlist
covered whatever each author remembered; keel's animated-selector coverage was
correct on the day it was written; the constraint reader is a six-key allow-list
that silently drops `readOnly`; the original `$ref` resolver handled exactly one
target bucket; and the fifth is inside the checker built to prevent the other
four. Nobody is careless five times about the same thing, which is what makes it
structural.

**A field argued redundant is being argued about from one sample, and that
sample is the one that cannot show you the case needing it.**

The coverage format carries both an opaque `id` and a display `name`. A reviewer
called them redundant, correctly observing they were identical in the worked
example. The producer whose data made them look identical is the one who then
needed them apart: two of their artifacts existed twice over, once in each of
two kinds, sharing a display name and differing only in kind. Keying on the name
collapsed each pair and **silently emitted 58 items where there were 60**.

The general form, and it is not "keep every field just in case": **a redundancy
argument is made from the arguer's current data, and current data is precisely
the sample that cannot contain the counter-example.** So the question to ask of
a field that looks surplus is not "is it used" but "what would have to be true
for it to matter, and would I see that from here". Where the answer is a
composite identity, a second producer, or a corpus you do not hold, you are not
in a position to call it.

The counterpart to *near-uniformity is evidence of an unstated rule*: uniformity
in one sample is not evidence about the population, and the exception is
somewhere you are not looking.

**Duplication is a liability for correctness and an asset for detection, and
this document leans hard on only the first half.** Worth stating because the two
pull opposite ways and the tension is real.

Everywhere above, two sources for one fact is a defect: an explicit `order`
beside array position, a remembered list beside the data it describes. They can
disagree, and nothing says which wins.

But a corpus owner's normaliser reported three operations as missing that had
been in their corpus all along — it collapsed `{param}` to `{}` while leaving a
literal `v9.2` alone, so a templated path and a pinned one could never match.
What caught it was that a **README advertised a tag covering those very
operations**, and the two accounts could not both be true. Not review, not care:
a second independent description of one fact, disagreeing.

So the rule is not "never say a thing twice". It is: **two sources for one fact
are a liability when nothing compares them and an asset when something does.**
Redundancy with a check over it is corroboration. Redundancy without one is a
pair of claims waiting to drift, and the drift is silent. If you find yourself
keeping a second description, the question is not whether to delete it but
whether anything would notice if it stopped agreeing.

**And when two records of one fact do drift, the human-readable one is the
expensive one to leave stale.** A corpus re-derived a set of claims from a newer
tool build and updated the machine-readable provenance that records which build
they came from. The README, which still named the old one, was not touched. The
corpus owner's own summary: *machine-readable provenance corrected and
human-readable provenance left stale is a bad way round, since the README is
what a person reads.*

The instinct runs the other way, because the structured field feels like the
real record and the prose feels like commentary. It is backwards for the same
reason a check's failure message carries its reliability: **the least informed
reader meets the informal surface, and they are the one with no way to tell it
is wrong.**

**This document did the same thing within the hour.** The coverage format
changed in six places; the prose describing it was updated and the JSON sketch
beside it was not, so it still showed a `grades` array with a retired `order`
key and no `catalogue` field. An agent implementing from this file found it, and
would have implemented the wrong shape from the example if the validator had not
disagreed. **A code block is the part of a specification a reader copies**, so
it is the informal surface here, whatever it looks like — and prose and example
drifting apart is a two-record drift with nothing comparing them.

**A sixth, and it is the one that shows the shape is not about lists.** A
mapping producer bound query parameters *positionally*, on the assumption that
the call adding them appears after the URL they belong to. Three real spellings
broke it, and each produced a plausible file with something quietly missing
rather than an error. Their summary generalises the whole section better than
the list does: **positional binding is an allow-list of forms nobody wrote
down.** No literal appears anywhere, so nothing looks remembered, and the
assumption is nonetheless a fixed set of shapes chosen once by whoever wrote it.

Which extends the test. Not only *does this answer come out of the data or out
of someone's memory of the data*, but also: **does this code assume a shape it
never states?** A list you can see going stale is the easy case.

**Note which way a stale check fails.** A rotted `GRADES` rejects *correct* data,
and the failure reads as a data defect rather than a stale checker, so someone
"fixes" the corpus to match the list and the edit looks like a conformance fix in
the log. That is worse than no check at all. Hence a style rule for anything of
this kind: **an assertion carrying a remembered value should say so in its own
failure message** ("either this value is wrong or this checker is out of date").
Derived assertions need no such hedge, because there is nothing to be stale.

Two reasons that rule is better than it first looks:

- **It is self-limiting.** Writing "this checker may be out of date" is mildly
  embarrassing, which applies steady pressure toward deriving the answer instead.
  A check that has to admit it might be stale is one someone will want to replace
  with one that cannot be.
- **The failure message is the only part of a check read by someone who does not
  already know how it works.** What it asserts, how it derives its answer, and
  whether it can rot are all visible only to whoever opens the file. So the
  message is where a check's own reliability has to be stated, or it is not
  stated anywhere the person meeting it will actually look.

That second point is an audience argument and it generalises. The same failure
produced keel's "merged and green", which was complete from inside their repo and
incomplete from outside it. **A statement about state has to name the audience it
is complete for**, and the audience of a failure message is always the least
informed one.

The fix is the same move as corpus-declared grades: **declare where each
extension is valid and have the check read the declaration.** The corpus states
that a given extension is meaningful at node level, at document root, or at both;
the checker enforces the declaration rather than a list of pardons. A key
legitimately used at two levels has then said so out loud, which is precisely
what was missing when `x-source` was quietly doing two jobs.

Do not build that ahead of a real case. Recorded so that when one appears, the
answer is not the first thing that comes to hand.

### Near-uniformity is evidence of an unstated rule

A companion to the family-asymmetry check, and it runs the other way.

When almost every instance of something does the same thing, that reads as
tidiness. It is usually an **invariant that nobody wrote down**, being followed
by convention, and the handful of exceptions are not stylistic variation. They
are the places where whoever wrote them was not present when the convention
formed.

The worked example: almost every hover in keel that sets `--surface-sunken` also
sets `--text-primary` explicitly. That looked like housekeeping. It was actually
a real rule — those two tokens are the only combination that clears AA on that
ground — followed silently, and the two places that omitted it are the two live
contrast bugs.

So when you notice a near-uniformity: ask what rule would make it necessary
rather than merely neat, and check the exceptions against that rule before
assuming they are fine. Then write the rule down, because a convention that
holds only while everyone remembers it is a hand-maintained list wearing a
different costume.

**State such a rule as an obligation on whoever can act on it.** The surface-list
form ("secondary and tertiary ink are promised on base, card and subtle") is true
and unactionable: the person choosing the ink and the person choosing the ground
are two different declarations, often in two files and sometimes two authors, and
nobody writing `color: var(--text-tertiary)` can see that a hover three levels up
will drag it onto sunken. The actionable form points at the party who causes it:
*if you set `--surface-sunken` as a background, you own the ink of everything
inside it.*

### A delta claim needs a before-measurement

Two people made this error independently on the same bug, both while being
careful. Reporting the impact of the `$ref` fix, one counted 38 notes "behind a
`$ref`" (true, but it included schema refs the old resolver already followed);
the other counted 10 notes reaching the page afterwards (also true, but three of
them rendered fine before). The real figure was **7**.

Both had counted a **population** where a **delta** was the claim. Both numbers
were correct and neither answered the question asked.

It is easy to make because the population is directly measurable and the delta
is not: a delta requires constructing a before-state, which is real work, so the
population gets quietly substituted for it. The only defence is to build the
before-state and measure it. There is no shortcut, and "I understand the
mechanism, so the impact is derivable" is exactly the substitution — impact is a
property of the rendered page, not of the model.

Related, from the same bug: the impact was **understated twice** by reasoning
from the mechanism rather than looking at the page. "No Request section" was
really a `Request` heading with nothing under it, which is worse, because it
asserts the operation takes no parameters. "Loses a mandatory header" was really
"renders zero parameters including both path variables". Both corrections ran
the same direction.

That section, and several above it, are instances of something larger, which is
next.

### The adjacent question, which is the head of most of this document

This arrived from keel, as the collapse of four findings that had looked
separate:

> **An artefact answers one question well and an adjacent question badly, and
> the failure is using it for the second.**

In every instance the artefact was correct. The question asked of it was not the
one it answers. That is why none of these look like mistakes at the time and why
none of them error.

The instances, across three repositories and four materials:

| Artefact | Answers | Was used to answer |
|---|---|---|
| `cwd` | where a session started | what it works on |
| A HEAD sha on a public repo | is your view current | do you hold the handover |
| keel's `classes.json` | this name exists | this class does something |
| keel's `components.md` | everything it covers | what a consumer needed next |
| A field list of things to ignore | did anything else move | did I find them all |
| A population count | how many exist | how many changed |
| Ink measured against the ground | is this legible on the page | is this legible against that ink |
| Adjacent rungs of a ramp | do neighbours separate | does what the layout pairs separate |

`classes.json` published a class that styled nothing. The field list missed nine
of ten broken links because they were in descriptions. The population count made
38 and 10 out of a real figure of 7. The ink pair nobody measured lost 45%.

**Three levels, and they are not three candidates for the same slot.**

1. **The head, above.** It covers artefacts that neither derive nor measure
   anything: `components.md` is a document and `classes.json` is an inventory,
   and both fail this way.
2. **The sharpest instance, which keeps a property the head does not have.**
   *Adjacency is a property of the ramp; what a layout puts side by side is not.*
   A ramp author checks neighbours, because neighbours are what a ramp has. A
   consumer puts whatever two things the content requires next to each other,
   and the design system has no view on which.
3. **The form it takes for derivations**, which is where this document first
   reached it, in the addressing section and by a completely different route:
   *a derivation is only better than a memory if it derives the property you
   actually need.*

That the same principle was reached twice, independently, from colour ramps and
from how to address a peer session, is the evidence that it is structural rather
than a good phrasing.

**The part worth the most is that it predicts.** Everything else in this
document explains what already happened. Level 2 says where to look: **the pairs
most at risk are the ones the structure gives no reason to look at.** Generalised
to the head, and this is the sentence to carry: *the question an artefact is
worst at is the one adjacent to what it is for.*

Which is also why writing more rules does not defend against it, the same
conclusion the seam argument reaches by another road. Nobody misuses an artefact
they distrust. These failures happen with the artefacts people rely on most,
because reliability in one direction is what makes the adjacent direction feel
already answered.

### Two ways a decision stalls while looking like it is being handled

Both from keel, both worth having because the responsible-sounding move is the
failure in each.

**When the missing measurement is the subject, more evidence is not
forthcoming.** keel's categorical-palette issue has thin evidence because the
axis has no measurement, and it has no measurement because both places it was
already load-bearing carried it as a human judgement: *tell the two callouts
apart at a glance*, and *survive losing a hue channel*. People looking do not
leave numbers behind. So nothing accumulated and there is nothing to reason
from.

"We need more evidence before deciding" is always the responsible-sounding
answer and is sometimes a way of never starting. **The tell is whether anything
in the system is currently generating the evidence you are waiting for.** If
nothing is, waiting is not a plan: build the measurement, run it against what
exists, and argue the threshold from that.

Two open items here are this exact shape. The ink-against-ink pairs in this app,
and the callout criterion that has to be stated as *you must be able to tell them
apart at a glance* because there is no number for it. Both load-bearing, both
carried by someone looking, neither accumulating anything.

**Acknowledging a limit feels like handling it.** This is why an accepted caveat
stops being a retained one: the acknowledgement does the conversational work and
none of the design work, and it feels like both. keel's version is a comment on
the line above the value being edited, read as scenery. The agreement form is the
more dangerous of the two, because a comment is inert and an agreement feels like
an action.

## Practical gotchas, all learned the hard way

- **Verify a deploy with a cache bust.** GitHub Pages sets a short max-age on
  `index.html`. A post-deploy check without one reports the *previous* build as
  current. This produced a false pass once already.
- **Asset fingerprinting must stay on.** With stable names, a returning visitor
  boots a cached assembly whose hash no longer matches and the app fails to
  start. `fingerprint-importmap.py` exists because the SDK emits
  `dotnet.<hash>.js` but leaves the loader importing `./dotnet.js` with nothing
  mapping them.
- **`rm -rf dist` before publishing.** Publishing over an existing dist
  leaves the old fingerprinted runtime and the import-map script then refuses.
- **A local `http.server` needs `request_queue_size = 256`.** Blazor opens well
  over a hundred connections at boot; the default of 5 drops requests and looks
  exactly like a broken build.
- **Blazor renders a bool-bound `aria-*` as `"True"`, and omits it when false.**
  Write ARIA attributes as explicit lowercase strings.
- **`@code` is a Razor directive.** A loop variable named `code` is a parse
  error pointing at a directive nobody wrote.
- A method named `Tone` shadows keel's `Tone` type.

## Order of work, decided

1. **The release gate clears**, then push. Ten commits, currently unpushed.
2. The specs owner lands the ten cross-spec link rewrites and their conformance
   check, in one commit, then `conform.py` with its CI hook.
3. **The extraction, performed in the originating session**, not handed to the
   new one. Including migrating this document into `oas-browser` as its
   foundational context.
4. **Handing over to a new session is the last act**, once the browser repo
   builds, deploys and is verified.
5. Then: the three call-breaking defects, the keel rail and disclosure,
   corpus-declared grades, and the two features the browser exists for.

**Why the extraction is not the successor's first task.** A new session
inheriting "perform this migration" would be reconstructing intent from a
document while executing the riskiest change in the project. Inheriting a
*working repository* instead means this document stops being a set of
instructions and becomes what it should be: the reasoning behind decisions
already made, readable when something surprises you rather than required before
you can start.

It also keeps the judgement and the execution in the same place. Most of what is
written here was learned by being corrected mid-task, and a migration is exactly
where that happens.

**Consequence for this document.** It was written as a handover *to* whoever
would do the extraction. After the extraction it needs re-framing from "do this"
to "this is why it is like this", and the extraction plan section becomes a
record rather than a task list. That re-framing is part of step 3, not something
to leave for the reader.

### Extraction workstreams

Dependencies matter more than order here.

| # | Work | Depends on |
|---|---|---|
| 1 | Move and rename: files, namespaces, csproj identity, the `ppapi` JS global, base href as a parameter | gate + push |
| 2 | Generalise the C-category: grade declaration, docs provider, grouping axis, branding, catalogue schema, `securitySchemes` | 1 |
| 3 | **Fix the routing contract** — add the spec dimension to URLs | 1, and **before first publish** |
| 4 | Write test fixtures and a test project | nothing — can start immediately |
| 5 | CI, Pages, and the cross-repo artifact channel | 1 |
| 6 | Delete the dead surface rather than migrating it | 1 |

4 is the largest and the only one with no dependency, so it should not be left
until last. It is also what makes 2 and 3 verifiable rather than asserted.

**Why the extraction goes before the defect fixes, including the ones that
currently produce wrong output.** A move should move *known-good* code. If code
is changed and relocated in the same step, a failure afterwards could be either,
and separating them costs a bisect through a repository boundary. Everything in
the batch below is already diagnosed and written down, so the cost of waiting is
bounded; the cost of tangling a move with a rewrite is not.

The same argument applies to the keel rail and disclosure, which are the largest
pending change to this app's navigation. Take them **after** the move, in the new
repo, for the same reason: they replace the last hand-rolled controls here and
that is a rewrite, not a relocation.

## The extraction plan

From a full read of all 29 source files (~2,240 lines). Three categories: **A**
general, moves unchanged; **B** Power Platform specific, must not move as-is;
**C** general in intent, hardcoded in fact. Most of the work is C.

### Decide these before the first publish, because they set the URL contract

**1. Routing has no spec dimension, and that is a broken contract, not a gap.**
`Route` is `(Kind, Id)` with kinds Overview / Operation / Schema / Resource.
There is nowhere in the URL to say *which spec*, and `Shell` unconditionally
selects `catalogue[0]`. So `#/operations/X` always resolves against the first
entry. Switching specs in the picker changes what renders but not the URL, so
reloading or sharing that link silently returns the reader to spec zero — and if
the id does not exist there, to the overview.

**Nine of the ten specs are currently undeep-linkable.** This is invisible today
only because `ppapi` is both first and by far the largest. A general browser has
no privileged first member, so it becomes wrong immediately. Fix it *before*
publication: it is a URL-format change, and hash routing exists here precisely so
URLs stay stable.

**Decided: `#/<specId>/<kind>/<id>`, with the bare form resolving against a
catalogue-declared default.**

`HashRouter`'s own doc comment argues the opposite, and should be read as
superseded rather than as a constraint. It says the bare shape is a commitment
because deep links were already published by the site this browser was built
for. Two things about that. It is an inherited claim about the outside world
that nobody verified, which is the shape this document distrusts everywhere
else. And it is answered by the defect: those links resolved for `ppapi` and for
nothing else, so the only compatibility surface that exists is deep links into
spec zero, and those keep working when the declared default is `ppapi`. **You
cannot break what never worked, and fidelity to broken behaviour is not
compatibility.**

Three decisions beyond the bare shape, each of which is a rule from elsewhere in
this document applied:

- **The default is catalogue-declared, not `catalogue[0]`.** Positional default
  is an unstated rule of exactly the near-uniformity kind: it holds only because
  `ppapi` happens to be first and largest, and reordering the catalogue would
  silently change what every bare link in the world means. A declared field says
  out loud what is currently a coincidence.
- **A spec id may not collide with the kind vocabulary.** Parsing
  `#/<specId>/operations/X` means the first segment is a spec id unless it is
  `operations`, `schemas` or `resources`. That vocabulary is the browser's, so a
  corpus declaring a spec with one of those ids makes the URL ambiguous. This is
  the `ppapi` one-token-two-meanings collision again, and it belongs in the
  conformance checker with the reserved set **computed from the route kinds**
  rather than written out as a literal that can rot.
- **A bare link that misses does not land on the overview.** Today an id absent
  from spec zero silently falls back there, which is the confident-wrong failure:
  the reader asked for an operation and got a page that looks fine. The `spec:`
  scheme already set the precedent that visibly missing beats silently wrong.

**Cross-catalogue resolution requires a corpus-published id index, and is not
offered without one.** This is a correction to a first version of the decision,
and the correction is the interesting part.

The first version resolved a bare miss by searching the catalogue: try the
default, then fetch the other specs and look. The cost was weighed as latency on
a miss. Under a *runtime* catalogue it is not latency, it is an amplification
primitive: a crafted link makes a reader's browser fetch every spec the
catalogue names, from wherever it names them, and with `?catalogue=` an attacker
controls the link and the catalogue both. No XSS required.

A bound would be arbitrary and ordering-dependent, which is `catalogue[0]`'s
defect again. So instead the catalogue declares which ids live in which spec. A
bare link then costs zero spec fetches, because the answer is in a file already
loaded. No index, no cross-catalogue search, and a bare miss reports unresolved.
That removes the primitive rather than bounding it, and puts the cost on the
corpus that wants the feature rather than on every reader who clicks a link.

**Note where that defect lived.** Both decisions were right in isolation. It
appeared only when they were held together, in the seam, made in sequence by one
party — which is the ownership-boundary failure with both sides of the boundary
inside one head.

**The index format, settled against measured data rather than guessed.**

```json
{ "operations": { "environments_get": ["bapi", "powerapps"] },
  "schemas":    { "Organization": ["bapi", "licensing"] },
  "resources":  { "environments": ["ppapi"] } }
```

Id to a **list** of spec ids, per kind, fetched only on a bare-link miss. A list
of length one is the common case and stays a list.

Resolution order: a qualified link resolves directly and never consults the
index; a bare link tries the declared default, then the index, then reports
unresolved. Several candidates gives a disambiguation page.

**Default-first is not a tiebreak**, and it is worth being exact because the
numbers make it look like one. The bare form *means* "resolve against the
default", by definition, so the index exists only for ids the default has no
answer for. There is no case where two candidates compete and the default
quietly wins.

I would have specified scalar values. The specs owner measured the corpus in two
minutes and found 14 genuinely ambiguous ids out of 1249, including four
operations — so `{id: specId}` is not a total function and scalars would have
shipped, then failed on a reader's link.

**The asymmetry in that measurement is the part worth keeping.** Resolving
against the default first settles every tag collision and two thirds of schema
collisions, and **none** of the operation collisions, because `ppapi` namespaces
its operationIds (`environmentmanagement_getSupportedLocations`) while the other
nine use bare `noun_verb`, so `ppapi` never competes for those names and cannot
resolve them. Operations are the realistic deep-link target, so the
disambiguation path is real rather than theoretical.

**Lists for all three kinds, not only operations.** Making operations lists and
the rest scalars would encode this corpus's collision profile as of today into
the format. Tags never colliding is a fact about ten specs, not about OpenAPI,
and a corpus sharing a tag vocabulary would collide immediately with no way to
say so. Remembered-versus-derived applied to a schema instead of a check: the
shape that happens to fit today's data is the one that goes stale invisibly.

**A latent trap in the same data, recorded because nothing depends on it yet.**
Two operationId conventions coexist in that corpus. Any future feature that
reads structure *out of* an operationId — grouping, sorting, deriving a display
name — would work on nine specs and behave differently on the largest. It is a
near-uniformity with an unstated rule behind it, and the exception is the member
that matters most.

**2. The base href is a build-time literal in three places that must agree.**
`index.html`, `fingerprint-importmap.py` (which reads it to key the import map,
since import-map keys are resolved specifiers), and a `pages.yml` grep asserting
the exact string. A general browser will be hosted at a repo path, at a user-site
root, and at localhost. Make it a publish parameter with one source.

**3. Where the catalogue lives. Decided: the catalogue URL is a runtime input,
with a default baked in at build.**

`SpecStore` fetches `specs.json` relative, with `SiteRoot = ""` and a comment
stating the app *is* the site. Individual spec `url`s would already work
cross-origin unchanged, because `HttpClient` lets an absolute URI override the
base — but the catalogue itself has no way to be pointed elsewhere. Entries
resolve relative to the catalogue's own URL, not to the app's base.

**An earlier version of this item said "the catalogue URL is configuration" and
claimed multi-catalogue support as a benefit falling out for free. Those are not
consistent.** Configuration implies build time. Loading any catalogue implies
runtime. The second was asserted as an advantage while the first was imagined,
and the gap survived because the item was arguing against a different option at
the time. It was an unmade decision written as a made one.

Made now, and runtime, for a reason stronger than eventual convenience: **a
build-time catalogue makes the generality nominal.** The browser's own Pages
deployment would bake in exactly one corpus, and every other corpus would need
its own build and deployment of the browser. That reintroduces precisely the
coupling the split existed to remove. Runtime catalogues are not a future
nicety, they are what the split is for.

A default is still baked in, so that the redirect from the specs site's old
address lands somewhere useful with no query string. The override is what sets
the trust model.

**This decision is what makes item 4 below a gate rather than housekeeping**, and
it is why the two must be read together rather than in sequence. Deciding runtime
means spec content is arbitrary third-party input on this origin. Fixing item 4
first and then deciding runtime would have been the same two facts in an order
where neither forced the other.

**4. Descriptions could emit two kinds of dangerous link, and the split turned
that from unreachable into a vulnerability. Fixed in `2e00241`.**

**This item was wrong when it was written, and the correction is worth more than
the item.** It said descriptions render as unsanitised HTML, and named three
vectors: a `<script>` tag, a `javascript:` link href, an `onerror` on an image.
Two of those three had never worked.

`Rendering/Markdown.cs` escapes `&`, `<` and `>` across the whole string
*before* it does anything else, and only then runs three patterns that emit
`<code>`, `<strong>` and `<a>`. So the only HTML that can exist in the output is
HTML that file wrote. No tag from a description has ever reached the DOM.
Measured, in a browser, on the fixture payloads: the `<script>` fixture produces
zero script elements and renders as visible text, and the `onerror` fixture is
inert.

What was actually broken was the link branch, in two ways:

- **No allow-list on the scheme**, so `[x](javascript:...)` emitted a working
  `javascript:` href. `data:` and `vbscript:` likewise.
- **The quote was not escaped** when the target was interpolated into the
  attribute, so a quote in a link target closed the href and turned the rest of
  the target into attributes of the anchor. This one was confirmed executing a
  real event handler before the fix, and confirmed not to afterwards.

The important property is unchanged and is the reason the item was right to
exist: **nobody introduces this.** It arrives as a consequence of the split,
because the code does not change and the trust model does. There is no diff to
review and no moment where anyone decides to accept the risk.

**Two things to carry from having got it wrong.**

First, the diagnosis was reasoned from the mechanism — `MarkupString`, therefore
raw HTML, therefore XSS — rather than from the rendered page. That is the same
move as the `$ref` impact estimates under *A delta claim needs a
before-measurement*, which ran the other way and understated twice. Here it
overstated. **Overstating a security item is the safer error and it is not a
free one:** it turned two lines into an open design question, and open design
questions get scheduled while two lines get fixed.

Second, and the substantive part: the item asserted a tension that did not
exist. "The answer is not simply escape everything, because `<code>` and `<em>`
are legitimate and wanted" describes a world where raw HTML from a description
renders. It does not. `<code>` in a description renders today as the visible
text `&lt;code&gt;`; the legitimate cases are served by markdown, not by HTML.
So there was no line to draw, and **the rendering question governs the security
question rather than the reverse.** A sanitiser is needed only if someone first
decides raw inline HTML should render at all, and nobody has asked that. It is
still unasked, and `Markdown.cs` flags the adjacent gap in its own doc comment:
the inline subset was measured over one corpus and renders headings and lists
literally.

The fixtures were written deliberately without looking at current behaviour,
which was right, and it means they had never been run in either direction. Four
have now been measured. `description-script-tag`'s three security assertions
already held. `description-javascript-uri`'s three genuinely failed.
`description-image-onerror` is the best-written of them: its raw-HTML half held,
and the clause "or from generated markup" is the half that failed, via the link
path rather than the img path. An assertion written to cover both is why it
caught a defect its own fixture does not contain.

### Blockers that are invisible in the files

**4. The Keel package grant does not transfer and exists in no file.** Keel is a
private package owned by the keel repo; `oas-browser` can restore it only because it
was granted access under **Manage Actions access** on the package, through the
web UI. There is no API for it. A new repo fails with `NU1301 403`, and a missing
developer token and a missing repo grant **fail identically**, so the first
person to hit it will chase the wrong cause. A green workflow run is the only
check. Do this first, before anything depends on a build.

**5. There is no channel for the specs site to consume the browser.** Today one
job publishes the app and copies the specs beside it, in one checkout. After the
split the specs repo needs a *published browser* as an input, and nothing here
produces one: the build workflow uploads a 7-day Actions artifact, which is not
consumable across repositories. A release asset, a container, or a submodule —
none exists. **This is the hardest mechanical consequence of the split and it
appears in no file.**

**6. The browser has no tests, and its only corpus is the thing being removed.**
No test project, no solution file, no test sources anywhere. Verification today
is "render the ten Power Platform specs and look". After the split the browser
repo has no corpus at all, and since it may not contain Power Platform content,
fixtures have to be **written, not copied**. This is the largest piece of work
the file-by-file view does not show, and it is what makes everything else on this
list checkable.

### The C-category work, by weight

- **`Model/SpecNote.cs`** is the deepest. The record, the `Read` shape, the
  grouping and the unknown-grade fallback are all general and correct. Three
  constants, the hardcoded `Order`, `IsObserved => Source == Live`, and the
  titles and caveats naming Microsoft and Terraform are not. **Consequence if
  left:** any non-Power-Platform corpus lands every group in the fallback and the
  whole panel reads as unverified, including grades that corpus considers
  observed. So corpus-declared grades is a correctness fix for the general
  browser, not a tidiness one — it actively understates any other corpus.
  `NotesPanel`'s `IsObserved ? Info : Warning` is the same policy in a ternary,
  and is also the live defect in item 8 above. A corpus-declared tone fixes both.
- **The Learn badge** (`OperationView`): an inline Microsoft flag in four brand
  hex values, the word "Learn", and the title text. Corpus declares one docs
  provider; operations carry `externalDocs.url`.
- **"Where Microsoft files it"** (`ResourcePage`): the *concept* is general and
  worth keeping — this logical resource crosses N of the publisher's own
  groupings — but the wording and the `x-ms-namespace` key are not. Corpus
  declares a grouping-axis label, or the section is omitted.
- **Brand strings** in `Shell` and `index.html`, including the long/short pair
  that is a real responsive affordance. Read from the catalogue.
- **Hardcoded bearer auth** in `SampleBuilder`: an unconditional
  `Authorization: Bearer $TOKEN`, while `components.securitySchemes` is never
  read even though all ten specs declare it. Every Power Platform API happens to
  be OAuth2 bearer, which is why nobody noticed.
- **The catalogue schema** has nowhere to put any of the above. It carries `id`,
  `title`, `url`, `repo` and needs: the grade declaration, the docs provider, the
  grouping label, branding, and its own base.

### The `x-ms-*` reads are narrower than they look

Four of the six extensions read appear in **`ppapi` only** — `x-stub` (1 use),
`x-ms-enum` (2), `x-ms-preview` (4), `x-ms-namespace` (240). Nine of ten specs
render identically without them. So this is not "the browser's Power Platform
knowledge", it is **AutoRest-dialect interop concentrated in one corpus member**,
because `ppapi` is generated from Microsoft's own OpenAPI.

Recommended: keep `x-stub` as the browser's own contract; generalise
`x-ms-namespace` into a corpus-declared grouping axis; make `x-ms-enum` and
`x-ms-preview` interop aliases behind browser-owned keys, since extensible enums
and preview status are real cross-vendor concepts with no OpenAPI 3.0 spelling.

Note the failure mode if they are simply dropped: on another corpus the Preview
badge never appears and nothing distinguishes "this corpus has no preview
operations" from "this corpus spells it differently".

### Delete rather than migrate

Five false statements about the browser's contract, in a repo whose whole job is
stating contracts accurately: `SchemaRef.Example` returns null behind a doc
comment claiming it feeds the sample panes; `ApiVersions` is read and never
rendered; `OverviewPage`'s `Entry` parameter is passed and unused; the
bare-string `x-notes` path has zero corpus instances; the `p.Schema is not null`
filter is dead since `Parameter.Schema` became non-nullable. Also `icon-192.png`,
unreferenced with no manifest.

`app/README.md` migrates already-wrong: it links `wwwroot/css/keel.css` and
`Rendering/Highlighter.cs`, neither of which exists.

### Two collisions worth knowing

`ppapi` is simultaneously the app's JS interop global and the `id` of the first
catalogue entry — one token, two unrelated meanings, in a codebase splitting
along exactly that seam.

`.nojekyll` is load-bearing and sits at the repository root. Both `_framework/` and
`_content/` start with an underscore, which Jekyll excludes. Omit it from a fresh
repo and the failure looks like a broken build rather than a missing file.

## Where this was left, 2026-08-29

Written at a stopping point rather than at a finishing point, because the next
session may be days away and everything below otherwise lives only in a
conversation that will not survive.

**Nothing is in flight.** Working tree clean, nothing unpushed, `main` at
`1a422eb`. Every sub-agent committed before finishing. The checkout at
`/Users/adam/Code/GitHub/AdamCoulterOz/oas-browser` is tens of commits behind:
it is stale, not divergent, and wants a pull rather than a merge.

**Live and working:** `https://adamcoulteroz.github.io/oas-browser/`. The corpus
redirects into it carrying the fragment, the catalogue loads cross-origin, deep
links resolve into non-default specs, and the coverage view renders a real
mapping. 127 tests, 4 warnings, all pre-existing.

### Owed to somebody, in the order they will notice

1. **A second catalogue in the fixtures.** The corpus owner's point and it is
   the sharpest testing observation anyone made: *one is the number at which
   cross-corpus mistakes cannot occur.* The mapping-declaration refusal, the
   origin display and the reserved-id check are all exercised against a single
   corpus, which is the configuration where each of them is unfalsifiable.
2. **The two colour-only cues**, claimed as mine and unfixed: the request line
   (`endpoint__host` against `endpoint__path`, 2.57:1 and colour is the only
   cue) and the property meta line. keel's `#41` is the general case; these two
   are the app's own and do not wait on it.
3. **The validator's `$ref` path-item blindness.** Operations behind a `$ref`
   path item are reported missing. Over-firing, on the one check whose subject
   is in somebody else's repository, and the weakest thing shipped.
4. **Table semantics.** There is no table markup anywhere in this app: property
   and response rows are `div` grids with no roles. keel has taken it as `#52`;
   adopting it is this app's.

### Do corpus-declared grades first. It stopped being a generality concern.

**This app knows three grades. The corpus uses five.** `ps-admin` (54
operations) and `ppac-spa` (133 operations, 22 notes) both fall to the unknown
fallback, and `ppac-spa` is **the most-used grade in the corpus** — the admin
centre's own JavaScript bundles, and the only first-party evidence for the
admin, analytics and athena hosts, since no shipped SDK or PowerShell module
touches them.

Until `f913078` the fallback rendered *"Treat it as unverified"*, so the browser
was instructing readers to discount the corpus's strongest structural evidence
on the authority of not having heard of it. That sentence is gone; the branch
now says what it does not know and leaves the meaning to the corpus. **It is a
stopgap. Corpus-declared grades retires the branch.**

This section previously ranked this below `x-probe-verified` on the reasoning
that it is a correctness fix *for some other corpus*. That was wrong in a way
worth keeping: the argument elsewhere in this file says a hardcoded triple
*"lands every group in the fallback and the whole panel reads as unverified,
including grades that corpus considers observed"* — written as a prediction
about a hypothetical future corpus, and it has landed on the corpus it was
written about. The general-browser argument and the this-corpus argument are the
same argument.

**The grade the corpus owner suggested, in their words rather than my summary,
so it goes into their declaration and not into a `switch` here:** title *"From
the admin centre's own client"*; `IsObserved` false, so it renders with the
other client grades; caveat in the shape of `pac-cli`'s, noting that a bundle
contains every route the client *can* call including branches nobody exercised,
so its **coverage is wider than a capture while its confirmation is weaker**.
They offered to rename the grade to suit this app and were told not to: the
vocabulary is theirs, the renderer's ignorance is mine, and a corpus editing its
terms to fit a consumer's hardcoded list is the failure the split exists to
prevent.

**Two failures produced one symptom, and only an audit found either.** Theirs:
`ppac-spa` was added mid-flow, registered in `conform.py`, and never raised as a
contract question, because the check went green and green read as done — a check
correct about its own layer while the layer it cannot see broke in the same
commit. Mine: `ps-admin` *was* announced and I never wired it, so the
announcement channel failed independently.

**Also**: the three-grade stacking case this document says not to pre-solve has
moved from hypothetical to possible. `bapi` and `ppapi` now have four grades
available within one spec, so an entity attested by a probe, a shipped client
and the admin bundle is reachable. Nobody has gone looking for one. Remeasure
before designing for it.

### Then, next by value

`x-probe-verified` rendering: 419 of 535 nodes need only the
observed/not-observed binary and nothing from keel. Then the six ranked defects,
then issue-backed comments, which remain undesigned and still need an auth model
a static page can hold.

The corpus is now **11 specs, 564 paths, 662 operations** — `flow` (Power
Automate) was added. Every count quoted elsewhere in this file is behind. The
coverage view resolves live and picks new specs up on its own; the prose does
not.

### keel changed hands, and two of its changes land on this code

**keel is owned by a Codex agent now**, addressed as `Keel` in the Codex `Keel`
project. Send gaps to the tracker rather than to the session this document names
elsewhere. Everything the previous owner knew and had not written down is in
their issue **#64**.

**0.4.4 is published and this app is on 0.4.3.** 0.4.3 was announced; 0.4.4 went
out without notice, which the outgoing owner named as theirs. Taking it is
cheap and unblocks removing two local overrides.

Four gaps filed from this repo shipped in it: `KeelChip` gained an overflow axis
(`Wrap` / `Ellipsis` / `NeverTruncate`), `KeelProgressBar` gained `Label`,
`KeelDisclosure` gained `LabelContent` and a trailing slot that can grow, and
`KeelCodeBlock` gained copy-button labels. Adopting them deletes the chip
white-space override and the 59 splatted `aria-label`s, and `Label` becomes
`EditorRequired` in 0.5.0, so adopting now avoids a warning later.

**Two changes coming in 0.5.0 break this app rather than improving it, and both
are single-site.**

1. **`--text-on-accent` is being removed. This app's one use of it wants
   `--danger-on`, NOT `--accent-on`.**

   `#blazor-error-ui` (`app.css:479`) paints a **danger** fill. `--accent-on` is
   ink for the **accent** fill. The two resolve identically today — white in
   light, near-black in dark — so replacing with `--accent-on` would look
   correct and be correct *by coincidence*. That is the token-chosen-by-
   appearance failure this document already has a worked example of, and keel
   has not promised the two stay equal. I wrote `--accent-on` here first and
   keel corrected it; the wrong token in a handover is worse than no note,
   because it is the instruction a successor follows without checking.

   Measured by keel, in dark against `--danger` `#ff8178`: near-black **8.12:1**,
   white **2.42:1**. In light against `#d12a22`, white **5.17:1**. So
   `--danger-on` fixes the site in *both* themes rather than only dark.

   Related, and the reason the light figure improved: `--danger` itself moved in
   0.4.3 from `#e5322a` to `#d12a22`, because at the old value nothing was
   legible on it in either direction — white 4.36, black 4.82 as the ceiling.
   **A fill nothing can be written on is broken whichever ink a component
   reaches for, so the fill moved rather than the ink.**
2. **The nav bar gains horizontal padding, shifting its container-query collapse
   threshold by 32px of window.** This app's rail switches at 880px keyed to
   keel's `Size.Lg` and **sits exactly on that boundary** — `app.css:100`, `119`
   and a container query at `290`. The outgoing owner flagged it as mine to
   re-check, and it was already flagged in the 0.4.3 notes for the same reason.
   Re-check against their corrected arithmetic rather than assuming the two
   still coincide; the failure mode is a burger and a rail both showing, or
   neither, in a 32px band.

**Also decided and not built, with this app as the named case in two of three:**
`KeelWithheld` for the refused-link gap (#42), the categorical palette (#23,
this app's verb map is the case), and the pivot control (#51 and #52), whose
margin-not-matrix shape was decided by this repo's sparsity measurements.

### What the other boundaries are holding

**keel** is building the projection control — `#51` became part of `#52` after
Adam reframed table, matrix and unit chart as one thing: records projected onto
zero, one or two dimensions with a composed cell. Also open: `#42` deliberately
withheld content, `#53` the navigable list row, `#54` progress-bar naming and
disclosure label composition, `#55` chip wrapping versus a never-truncate
guarantee. The coverage view ships with chips meanwhile and swaps later.

**The specs corpus** carries the object catalogue, the id index, `coverage` in
its reserved union, and the seven connectivity and governance operations the
provider's call graph found. Its conformance check keeps a literal copy of the
reserved set as fast feedback; this repo now holds the authoritative one.

**The provider mapping** is on a branch, not merged, at
`AdamCoulterOz/terraform-provider-power-platform`. When it merges the raw URL
moves to a `main` path and the coverage view's default should point at it. Five
calls remain unresolved by design: two are a casing defect awaiting `#1257`,
three are an approximate branch-tracking limit.

## State

The extraction is done. `oas-browser` exists, builds in CI against the keel
package grant, and publishes an output that has been checked to boot. The
relocated app was verified to render identically to the original by hashing the
rendered markup of 1313 pages rather than by counting them. The `$ref` resolver
fix that this section once said the release must wait for landed before the
move, so athena, dataverse and licensing operations render their parameters.

**Nothing is deployed.** `build.yml` says so in its own header: it builds and
checks, and there is nothing publishing this yet. So the two items below marked
*before first publish* are still ahead of the thing they gate, which is the
good case and not a reprieve to spend.

A fixture set of 63 documents carrying 241 assertions is in `tests/`, 121 of
them deliberately failing because they describe correct behaviour rather than
current behaviour. **Treat 121 as a claim rather than a count.** The statuses
were set by an agent reading the implementation, which is the reasoning-from-the-
mechanism move this document catalogues, and they have never been executed. Four
of the security assertions have since been measured and the reading was wrong in
both directions: the whole of `description-script-tag` already holds, and all of
`description-javascript-uri` genuinely failed. There is no runner yet. When
there is one, run all 241 in both directions including the 120 marked
implemented, since those were established the same way, and trust the runner
over the sidecars.

Open, in priority order:

1. **The two differentiating features are unbuilt.** GitHub-issue-backed
   comments on operations, and the coverage view. These are the entire reason
   the browser exists instead of Stoplight Elements. Until they exist, this is a
   good spec browser that could still have been Elements.
2. **The routing contract and the catalogue mechanism**, both recorded under
   *Decide these before the first publish* below, both now decided and neither
   yet built.
3. The sidebar rail and the two disclosures, both waiting on keel.
4. **Two tone mappings here choose by appearance, both waiting on keel issue
   23.** Accepted by keel as a real missing axis: a *categorical* palette, whose
   colours assert only "these N things differ" and make no state claim, as
   distinct from tones which assert a state. Both of these belong to it:

   - `Rendering/MethodTone.cs` maps HTTP verbs onto tones. This one is purely
     categorical: a GET is not healthy, a DELETE is not failed, a PUT is not a
     warning. Verbs differ without ranking, so a palette asserting only "these N
     differ" is the whole answer.

   **Leave the verb map as it is until issue 23 lands.** It is known,
   single-site and documented, which is a better position than an unrecorded
   one, and churning it twice costs more than waiting. Do not resolve it by
   reaching for a ramp value.

   **The evidence grades are NOT the same case, and an earlier draft of this
   document had that wrong.** Grades carry an *induced order*: `live` is stronger
   evidence than `pac-cli`, which is stronger than `provider`, and that ordering
   is the entire reason the panel exists. Moving them wholesale onto a
   categorical palette would flatten it, which is the merge failure in a new
   costume: not collapsing three groups into one, but keeping three groups while
   dropping what makes them unequal.

   This does not contradict "the axis is provenance, not confidence". Provenance
   decides *which* grade is assigned, and you must never pick by how sure you
   feel. But provenance *implies* evidential weight at render time, because a
   wire observation really is stronger than a third party's model of the API. The
   order is a consequence of the provenance, not a second independent axis. Both
   hold at once.

   See the live defect in item 8, which is the part of this that is actually
   broken.

   **A third instance, and the sharpest, because it arrived inside a single
   component.** The coverage view needs four states: called fully, called
   conditionally, not called, and called-but-absent-from-the-spec. I asked keel
   for a grid that could show four states, having counted them and not looked at
   them. keel's reading:

       called fully / conditionally / not called   an ordered ramp
       called but absent from the spec             not on that ramp at all

   **A set of states is not automatically one axis.** Three are positions on a
   scale and the fourth is a different kind of claim — an anomaly, not a further
   position. Putting all four on one visual channel collapses that, and it is
   exactly the ordered-versus-unordered problem above arriving one level down.

   Their answer is worth carrying as a technique: **fill level carries the
   ordered scale** (filled, half, empty — ordered by construction, survives
   greyscale, needs no legend), **a shape overlay carries the anomaly**, and
   colour is redundant reinforcement on both. That satisfies the
   colour-must-not-be-the-sole-cue rule *by construction rather than by
   discipline*, which is the difference between a rule that holds and a rule
   everyone remembers to follow.

   The test before mapping N states onto one channel: **are these all on one
   axis, or have I counted them rather than looked at them?**

   A footnote on how that was found, because it is a distinction worth keeping.
   The page had already put the anomaly in its own callout rather than as a
   fourth mark, so the design was right before the reasoning was stated, and I
   called that luck. keel's correction: the reasoning was present *in the design
   decision* and absent from *the description I gave them*. That is a gap
   between what you knew and what you said, which is a far smaller problem than
   a gap between what you knew and what was true — but it is the one that makes
   a reviewer unable to help, because they can only see the description.

5. **Three ink uses of `--accent` fail AA in dark** (4.42:1 and 4.24:1): the
   schema type link, the operation summary on a schema page, and the current rail
   item. Reported, and keel is fixing it: `--accent` was outside the original
   fill/ink/on scope because it clears in light, and dark `--accent-text` now
   takes a lifted rung. Fixed by taking their release, nothing to do here.
6. **`#blazor-error-ui` ink fails in both themes** (4.36:1 light, 2.42:1 dark).
   The `--danger` fill is meaning-correct, the app really did fail to boot; the
   ink is not, because `--text-on-accent` is hard-wired to `--gray-0` with no
   dark override. It needs an on-danger ink, which keel is adding for every tone.
   Note the correct answers **invert** between themes: light danger wants white
   ink, dark danger wants near-black at 6.94:1. Do not assume an on-colour ink is
   the light one.
7. **Adopt `--text-link`** on the two genuine link uses (`PropertyRow` type link,
   `SchemaPage` operation summary). No keel component reads it, which is a gap in
   keel rather than evidence the token is surplus; keel has explicitly asked for
   it to be used. Not yet done.

8. **`pac-cli` and `provider` render identically. Live defect, latent today.**

   `NotesPanel.ToneFor` is `g.IsObserved ? Tone.Info : Tone.Warning`, and
   `IsObserved` is `Source == Live`. So both non-observed grades get the same
   tone, the same weight and the same icon, and are separable only by reading
   the title. That fails the criterion this project adopted: *you must be able to
   tell them apart at a glance, without reading the words.*

   It was correct while there were two grades and became a defect the moment the
   third landed. I introduced it, and I missed it because I verified that
   `provider` rendered as Warning *correctly* and never asked whether
   Warning-against-Warning was distinguishable. The seam again: the new thing was
   checked, the relationship between the new thing and its neighbour was not.

   **It is not visible on any page today**, because no entity in the corpus
   carries both `pac-cli` and `provider`. It is waiting for the first one that
   does, and on that day the page will look completely fine. Fix it before that
   entity exists.

   The fix is narrower than recolouring the grades. **Tone keeps ranking**
   (observed against modelled, Info against Warning, which is what governs
   whether a reader should trust a claim). A second distinction then separates
   `pac-cli` from `provider` *within* the warning tier.

   Be careful how that second distinction is stated. An earlier draft said
   "category subdivides, tone ranks", which is tidy and slightly false: the two
   non-observed grades **are** ordered, because Microsoft's own shipped client is
   better evidence than a third party's model. What is true is that *the gap
   between them is much smaller than the gap between either and observed*, which
   is why the tonal break sits where it does. A difference of magnitude, not of
   kind. The clean phrasing was more quotable than the truth, which is how it
   travelled upstream before being caught.

   So: **prefer two variants of one glyph** (filled against outline, or a weight
   difference) over two unrelated glyphs. Unrelated glyphs assert "different
   origin, no ranking", which renders that small falsehood into the interface,
   where it becomes load-bearing the moment a reader reasons from the rendering
   back to the model. An evidence panel actively invites exactly that. If only
   unrelated glyphs are available, take them: still a large improvement over two
   identical Warnings, and the residual imprecision is far smaller than the
   defect it fixes.

   Prefer shape over hue either way. keel's own Info and Warning callouts
   separate by glyph as well as colour, which is what makes them survive a
   blue/yellow deficiency; two hues inside one tone would hand the whole burden
   back to colour for precisely the readers the glyph choice protects. Needs
   something from keel regardless: `KeelCallout` has `ShowIcon` but no way to
   supply an icon.

   Test cases: the only `provider`-graded entity in the corpus is dataverse
   `PATCH /api/data/v9.2/systemusers({systemUserId})`. The two-grade pages are
   ppapi `environmentmanagement/environments/{environmentId}/settings` GET and
   `governance/ruleBasedPolicies/assignments` GET, both `live` plus `pac-cli`.

## Next batch: six defects, ranked by what they cost a reader

Found while fixing the `$ref` resolver, all in the browser, none are spec
defects. The ranking principle came from the spec owner and is the right one:

> **Being invisible is better than being wrong.**

Three of these produce a *wrong* result for someone who trusts the page. Three
hide content that exists. Take the wrong ones first, even though the invisible
group contains the larger and more interesting work.

### These make a reader's call fail

1. **Path-item-level `parameters` are ignored.** `OpenApiSpec`'s constructor
   loops path-item keys and skips anything that is not an HTTP method, so
   parameters declared once for the whole path never reach `Operation`. copilot
   declares three there, **all `required: true`, two of them the path parameters
   `environmentId` and `botId`**. Both copilot operations therefore render with
   *zero* parameters. Not merely a missing header: the reader cannot see the path
   variables at all, and `x-cci-tenantid` is documented as mandatory and not
   derivable from the token. Both operations are unusable from the site. The fix
   is roughly ten lines: merge path-item parameters, with operation-level
   entries overriding by `name` plus `in`.
2. **817 authored `example` values are ignored, and fabricated ones shown in
   their place.** `SchemaRef.Example` is a stub that always returns null, with a
   doc comment claiming it feeds the sample panes. The samples synthesise
   placeholders instead. Showing nothing would be honest; showing a plausible
   invented value where the corpus supplied a real one is a false statement the
   reader cannot detect.
3. **`servers[].variables` is dropped.** Only `url` is read. Eight templated
   server entries across seven specs, including athena's
   `{azureRegionPrefix}{clusterUriSuffix}` and dataverse's `{organizationHost}`.
   For those two APIs resolving the host is the *first* problem a caller has, and
   the site shows raw braces it never explains.

### These hide content that exists

4. **`x-probe-verified` and `x-source` are never read.** See below; this is the
   largest single piece of work here.
5. **Composite schemas render as one word.** `Unwrapped` collapses `allOf` only
   when it has exactly one member, and `Properties` never looks inside members,
   so 19 schemas print the literal keyword. `ppapi/ActionEvent`'s members show
   "Properties allOf" with base class and properties both gone; `ppapi/Clause`
   shows "Properties oneOf" for its 9 variants. The model half is a merge; the
   oneOf/anyOf half needs a `SchemaTree` branch.
6. **`Constraints` is a six-key allow-list**, dropping `readOnly` (16 uses) and
   `title` (5). A reader cannot tell a server-set field from one they must
   supply. The allow-list-versus-generic mistake again, one level down.
7. **Notes do not resolve through a `$ref`, but the description on the same row
   does.** A property row asks the *written* schema node for its notes, and asks
   the written node, then the unwrapped node, then the resolved target for its
   description. So two fields sitting on the same object take different paths and
   only one arrives: put a note on a component schema and reference it, and the
   description shows while the note vanishes.

   This is not the parameter-object case below; it is one layer deeper and it
   affects every `$ref`'d node, which in this corpus is most of them.

### Where notes may live: state this in the contract

Established by fixture rather than by reading, and currently inconsistent:

| Node | Read today |
| --- | --- |
| Operation object | yes |
| Tag | yes |
| Component schema | yes |
| Inline schema property | yes |
| Parameter's `schema`, written inline | yes |
| Parameter's `schema`, reached through a `$ref` | **no** (item 7 above) |
| Parameter **object** | **no** — the type has no notes accessor |
| Response **object** | **no** — never asked |

The corpus only ever writes notes where they happen to work, so nothing has
surfaced this: 66 on operations, 15 on component schemas, 4 on inline properties,
3 on inline parameter schemas, 2 on `components/parameters/*.schema`, and **zero**
on a parameter object or a response object.

That is a convention holding by luck rather than by contract. Decide which nodes
may carry notes, make the reader consistent with that decision, and say so —
rather than leaving a corpus author to discover by absence which placements are
silently ignored.

### Small, deferred deliberately

- **Say in the source what the unresolved-ref path means.** Nothing in the
  corpus dangles: 0 unresolvable refs across 1,174 parameters, 1,836 responses,
  100 request bodies and 313 headers. So if the unresolved branch ever fires on
  real content, that is a resolver bug and not a spec defect, which makes it a
  clean signal rather than an ambiguous one. That currently lives only in a
  report. Two lines on `Follow`'s doc comment puts it where the next reader meets
  the branch. Worth adding the companion point in the same place: the corpus
  proves the resolver *resolves*, and the 40 synthetic-document assertions prove
  it *fails loudly*. Neither test set can establish the other, which is why the
  synthetic set exists at all.

  Deferred only because an independent release gate was mid-run against that
  exact tree, and amending it would have bought two lines for the price of a full
  re-verification.

### Also outstanding, same batch

- **`OperationView` discards each parameter's own description.** `ToProperty`
  builds a `SchemaProperty` from three of the parameter's five fields, and
  `PropertyRow` then reads the *schema's* description. The corpus puts parameter
  prose on the parameter object, so **every parameter row on the site has no
  description**. Pre-existing and independent of the resolver fix; it applied
  equally to the 830 parameters that already rendered.
- `OrderedParameters`' `p.Schema is not null` filter is now dead code and can be
  deleted: `Parameter.Schema` is non-nullable and an unresolvable ref gets a
  stand-in that renders as `unresolved #/...` rather than vanishing.

## Rendering `x-probe-verified`, when you get to it

This is a **documented reader-facing contract**, not tooling metadata. All ten
spec READMEs define it in reader terms and quote the ratio as the spec's headline
trust statement. It is also the larger half of the provenance story: `x-notes`
covers 44 contradictions, `x-probe-verified` covers the baseline trust of 423
operations and 786 schemas. A reader who cannot see it cannot tell whether the
operation they are about to call has ever been called.

**Most of it does not depend on keel.** 535 nodes carry provenance markers: 419
have `x-probe-verified` only, 115 have `x-source: pac-cli`, 13 have both. So 78%
of the work is the observed/not-observed binary, which is Info against Warning
and needs nothing from anyone. Only the 115 want the glyph pair from item 8.
Build the binary first and add the subdivision when keel lands; blocking 419
nodes of settled work behind a decision about 115 is holding the trunk hostage
to the branch.

Three constraints, the first two load-bearing:

1. **Not callouts.** 447 markers rendered as callouts would bury the 44 notes
   under noise. That is the dilution argument from the rejected fourth grade, at
   ten times the scale. It wants a compact per-node marker on the operation and
   schema header.
2. **Render both states, not only the true one.** Only 43% of operations and 24%
   of schemas are verified, so unverified is the common case, and a badge that
   appears only when true is unreadable: the reader cannot distinguish "not
   verified" from "this site does not show that". Absence is *documented as
   meaningful*, so it has to be positively rendered. Getting this wrong would be
   the pattern in this document self-inflicted: the marker renders, the meaning
   does not.

   **This rule has now been derived independently three times in this project,
   on three unrelated surfaces**, which is why it is worth stating as a rule
   rather than as three observations. A refused link must say it was refused
   rather than becoming plain prose. An unverified operation must be marked
   unverified rather than left blank. A coverage grid must draw the uncalled
   operations rather than only the called ones. In each case the same sentence
   is the test: **a reader must not be able to confuse "nothing here" with
   "something here and not shown."**

   keel filed the first of those as a vocabulary gap and has linked the three,
   which is the correct home for it: the reason it keeps recurring is that no
   design system has a word for *deliberately withheld*, so every consumer
   invents absence-handling separately and half of them invent nothing.
3. **Reuse the grade vocabulary.** `x-source` is the same axis as note
   provenance: verified live / from Microsoft's shipped client / provider-derived
   is exactly the `live` / `pac-cli` / `provider` triple. Node-level and
   note-level provenance must share one visual language or a reader has to learn
   two. Whatever keel settles for the glyph pair in item 8 applies here unchanged.

## Conventions

- **Keep every diff small enough to read, because that is a review control.**
  A three-description edit once rendered as a 4000-line diff because the writer
  used `indent=2, ensure_ascii=False` where the corpus convention is 1-space and
  `\u`-escaped. Nothing errored, the content was correct, and the only casualty
  was anyone's ability to see what else was in the change: two unrelated app
  files rode along unnoticed. Reformatting defeats review silently, which is the
  same failure shape as everything in the section above, applied to the commit
  instead of the page. The nine hand-owned specs and `enrichment.json` are
  1-space and escaped; `oas.py` writes the generated ppapi spec with
  `ensure_ascii=False`, so literal non-ASCII is correct there only.
- **Stage explicit paths. Never `git add -A` or `git add .`** while more than one
  writer is in the tree. This is necessary but not sufficient: it would not have
  caught the case above on its own, because the sweep was invisible inside an
  unreadable diff.
- **A constraint protecting a shared resource must be addressed to everyone who
  can touch it, not to everyone you are directing.** This failed twice here, the
  same way both times. The `git add -A` rule was given to sub-agents and not to
  the other session working in the same tree, and a commit from that session
  swept in-progress app files. Later, a release gate was running against a fixed
  tree, sub-agents were told not to touch it (a wanted two-line change was
  deliberately deferred), the other session was not told, and a commit landed
  mid-run that would have produced a false failure. The instinct is to scope
  instructions to the people you are managing. The resource does not care who
  manages whom.

  There is a counterpart rule for the other side, and it is the cheaper of the
  two: **before committing to a shared tree, ask whether anything is running
  against it, rather than assume you would have been told.** The asymmetry is
  what makes it worth stating. The person holding the gate knows it exists; the
  person committing does not. So the cost of asking is one question, and the cost
  of remembering to announce is remembering every time, for every party, forever.
  Where a defence can sit on either side, put it on the side that does not have
  the information.
- No `Co-Authored-By` trailers on commits.
- Commit messages and anything outward-facing: plain, direct, first person, no
  em dashes. Explain the reasoning, not just the change.
- Descriptions state what an API does, not how the spec was built. The same rule
  applies to notes.
- Justification sits adjacent to the thing it justifies. A spec that overrides
  its documentation must say why, next to the override.
