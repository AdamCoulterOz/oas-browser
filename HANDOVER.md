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

`<specId>` is the `id` from the catalogue. The fragment is the browser's own
route shape, so a deep link is expressible without the corpus knowing the
browser's URL structure, and it survives the browser being redeployed anywhere.

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

### The coverage mapping (not yet designed)

The contract that prompted the split. The browser must define a format for
"this external artifact maps to these operations", render it as a coverage
view, and know nothing about Terraform or Power Platform in doing so.

Design it as a contract first, publish it, then let the provider fork populate
it. Do not let the first implementation define the format by accident, which is
how the browser ended up with Power Platform in it the first time.

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

- keel: peer name `sch-9d`, session title "keel design system".
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

**One correction from running it.** The protocol's second half is the stronger
half, and not for the reason it was written. Naming the four specs-owner commits
was framed as proving you are working in the repo. It does not: those commits are
in `powerplatform-apis`, so the successor cannot derive them and can only produce
them by having read this document. That is still worth doing, but it verifies
*possession of the handover*, which is a different property from *working in the
browser repo*. The `HEAD` sha verifies the second. Two properties, two checks,
and the document previously described them as one — which is the adjacent-property
error below, committed inside the protocol written to avoid guessing.

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

### Delegate implementation. Keep judgement.

Delegate freely, including review and release mechanics. Sub-agents do the work;
you assign, review and communicate.

**Non-delegable:**

- **Authoring the criteria** a reviewer applies. This is the real skill. A vague
  "review this" delegated is worthless; a specific criterion delegated is as good
  as doing it yourself. Each criterion should name *the specific thing that would
  be missing*, so it is a pass/fail someone without your context can apply.
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

- **0.4.3, additive.** Their component reference generator, which was silently
  understating the size of an enum. `KeelNavBar` gaining horizontal padding and
  moving its burger to the trailing edge. And the new ink tokens
  (`--success-text` and siblings), which add values without changing any, so
  contrast fixes do not wait for the breaking release. Note the nav padding
  shifts the effective container-query collapse threshold, and this app's rail
  switches at 880px keyed to keel's `Size.Lg`, which sits exactly on that
  boundary. Re-check against their corrected arithmetic rather than assuming.
- **0.5.0, breaking.** `Emphasis` gains a `Loud` rung so it becomes a real
  loudness ladder and `New` stops being the one tone that renders differently
  under `Filled`. keel's own components move onto the ink tokens. `KeelCallout`
  gains a density axis, at which point `.notes--compact` here can be deleted.
- **Still open, no date.** A sidebar rail component, and a disclosure primitive
  (their issue 7).

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

**Prove each invariant by making it fail.** Every check in the first version was
run against a synthetic violation and required to go red, including the real
`x-source` collision reverted on purpose. This matters because *a check that has
never failed is indistinguishable from a check that cannot fail*. Both are green,
and no observation separates them except making one fail deliberately. It is the
pattern in this document applied to the test instead of the page.

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

**2. The base href is a build-time literal in three places that must agree.**
`index.html`, `fingerprint-importmap.py` (which reads it to key the import map,
since import-map keys are resolved specifiers), and a `pages.yml` grep asserting
the exact string. A general browser will be hosted at a repo path, at a user-site
root, and at localhost. Make it a publish parameter with one source.

**3. Where the catalogue lives.** `SpecStore` fetches `specs.json` relative, with
`SiteRoot = ""` and a comment stating the app *is* the site. Individual spec
`url`s would already work cross-origin unchanged, because `HttpClient` lets an
absolute URI override the base — but the catalogue itself has no way to be
pointed elsewhere. Decided contract: **entries resolve relative to the
catalogue's own URL, and the catalogue URL is configuration.**

**4. Spec descriptions are rendered as unsanitised HTML, and the split turns that
from tolerable into a vulnerability.**

The browser renders `description` fields by passing markdown output into a
`MarkupString`, which injects raw HTML into the DOM with no escaping.

Today that is defensible: the corpus is first-party content in a repo the same
person controls, so the input is trusted. **A general browser loads a catalogue
from a URL.** Spec content becomes arbitrary third-party input rendering as raw
HTML on the browser's own origin, which is a straightforward XSS vector — a
`<script>` tag, a `javascript:` link href, an `onerror` on an image.

The important property: **nobody introduces this.** It arrives silently as a
consequence of the split, because the code does not change and the trust model
does. That makes it exactly the kind of thing that ships, since there is no diff
to review and no moment where someone decides to accept the risk.

Decide before the first publish that can load an arbitrary catalogue. Note the
answer is not simply "escape everything": `<code>` and `<em>` in a description are
legitimate and wanted, so the real question is where the line sits. Fixtures
exist covering both the attacks and the legitimate cases, deliberately asserting
*safe* behaviour rather than current behaviour.

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
