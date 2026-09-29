# Phase 4 — Builder questions

**Pattern / focus:** Builder.

**Read first:** [Guide 04](../../materials/guides/04-builder.md) · [Requirements](requirements.md)

## How to answer

- Use your own wording. Do not paste teaching-example types (for example ramen orders) as if they were your greenhouse classes.
- When a question asks about _this application_, refer to locations, zones, `location_id`, and the configuration wizard from the lab.
- Short answers are fine when the question is narrow. Write a few sentences when it asks you to explain or compare.
- Write each answer inside the matching **Your Answer** note. Replace the placeholder; leave the question text unchanged.

## A. Pattern

1. State the intent of Builder in plain language. Why does construction of a complex object need **stepwise assembly** and **validation at the end** (`build()`), instead of a telescoping constructor or a half-filled dict written straight to the database?

> [!NOTE]
> **_Your Answer_**
>
> _(Builder means you put one complicated object together a piece at a time, and check it all at the end.

A telescoping constructor does not work here because the number of zones is not fixed. You would need a different constructor for one zone, two zones, three zones. And a long argument list is easy to get wrong when several of them are the same type.

A half-filled dict written straight to the database is worse. Nothing checks it, so the bad data is already saved by the time anyone notices. Some rules also cannot be checked one piece at a time. You only know whether zone names are unique once you have every zone.)_

2. Name the main participants (**product**, **builder**, **optional director**, **client**). Until `build()` succeeds, is the intermediate object a finished domain product? Why does that distinction matter?

> [!NOTE]
> **_Your Answer_**
>
> _(The participants
Product — the finished thing. Here LocationConfig, a location with its zones.

Builder — collects the parts and checks them. Here LocationConfigBuilder.

Director — optional. Runs a fixed recipe of builder calls. I did not need one, because the client decides how many zones there are.

Client — asks for the parts to be added, then calls build(). Here the config service.)_

Before build() succeeds there is no product, only a name and some drafts the builder is holding.

That matters because a half-made location should never leave the builder. If it did, other code could save it while it was still wrong.

3. List at least three kinds of invalid configuration a location/zone `build()` should reject in **this** lab (name, zones, moisture thresholds). Why must those rules live in the **domain** builder, not only in the HTTP layer?

> [!NOTE]
> **_Your Answer_**
>
> _(WWhat build() rejects
An empty location name.
No zones at all.
Low threshold not below the high one, for example 0.5 and 0.2.
A threshold outside 0.0 to 1.0, since these are vwc.
The same zone name twice in one location.

They live in the domain because that is where the rules belong. A moisture threshold above 1.0 is wrong no matter who asked for it.

If the checks sat only in FastAPI, anything not coming through HTTP would skip them. My builder tests would also need a web server to run. Right now they run with nothing else started.)_

## B. This phase of the application

4. What aggregate does the builder produce (location plus zones)? Why does this course use **`location_id`** (and never `greenhouse_id`) as the name for that scope?

> [!NOTE]
> **_Your Answer_**
>
> _(The builder produces one location together with its zones. The two go together as one unit. A location with no zones is not valid, and a zone with no location has nothing to belong to.

The name is location_id because the row it points at is a location. The product is a smart greenhouse, but one install can have several locations. Later phases join on this column, so it should say what it points at, not what the product is called.)_

5. Describe the path from API request to persistence: DTO → builder steps → `build()` → repository. What must **not** be persisted if `build()` raises `ConfigurationError` (or equivalent)? Why does assigning a device wait until the zone row exists, and why does the client send only `zone_id`?

> [!NOTE]
> **_Your Answer_**
>
> _(The router reads the JSON into BuildLocationConfigRequestDto. The service passes it to the builder, one add_zone per zone, then calls build(). If that passes, the repository saves the location and its zones. The mapper turns the saved rows into LocationConfigDto.

If build() raises ConfigurationError, nothing is written. Not the location, not the zones. The error never reaches the repository, and the router turns it into a 400.

Assignment waits because a zone has no id until it is saved. There is nothing for a device to point at while the builder is still running.

The client sends only zone_id so the two columns cannot disagree. My service reads location_id off the zone row and writes both in one update. That way a device can never claim a location its zone is not in..)_

6. Saving a location and its zones must be **one transaction**. What goes wrong if the location row commits and a later zone insert fails? How does that relate to “no half-built aggregates in the database”?

> [!NOTE]
> **_Your Answer_**
>
> _(If the location commits and a zone insert then fails, the database keeps a location with no zones. The builder would have refused to make that, and it is sitting there anyway.

It confuses everything after it too. The config endpoint returns an empty zone list. The wizard shows nothing to edit. Nobody can tell whether the zones were never added or were deleted later.

My repository does one flush() to get the location id, adds the zones, then commits once. A failure anywhere rolls all of it back, so no half-built location is ever stored.)_

7. The configuration wizard UI collects fields in steps. How does that UI map to Builder without turning React (or the HTTP handler) into the place that owns domain validation?

> [!NOTE]
> **_Your Answer_**
>
> _(The wizard collects the same parts in the same order. First a location name, then zone rows you can keep adding. One submit sends the whole thing. So the shape matches the builder, but the browser is only collecting input.

The wizard does check the fields before sending. That is just to save a trip to the server and show the message next to the box. The real decision is still build().

The test is simple. If I deleted the browser checks, nothing new would become possible, because the API would still answer 400.)_

## C. Compare, contrast, and scenarios

8. Contrast Builder with Factory Method and with Abstract Factory. Which pattern answers “which type?”, which answers “which matching kit?”, and which answers “how do we assemble one **valid whole** in steps?”

> [!NOTE]
> **_Your Answer_**
>
> _(Factory Method answers: which type do I make?

Abstract Factory answers: which matching kit do I make?

Builder answers: how do I put one valid whole together in steps?

Both factories decide something and hand it back in one call. Builder cannot, because the caller decides what goes in and how many pieces there are. Builder also has a checking step at the end. Neither factory has that.)_

9. Fluent method chaining (`builder.add_zone(...).build()`) is a coding style. Why is a fluent interface **not** the same thing as the Builder pattern?

> [!NOTE]
> **_Your Answer_**
>
> _(Chaining only means each method returns self, so the calls can be written in a row. That is a writing style. Any class can do it.

Builder is about what the object does. It holds the parts, then checks them and produces a finished product.

My builder would still be Builder if every call sat on its own line. And a class that chains but has no build(), and checks nothing, is not Builder.)_

10. A classmate validates thresholds only in FastAPI / Pydantic and leaves `build()` empty. Another mutates builder fields after `build()` while treating the product as immutable. Explain why each is a trap.

> [!NOTE]
> **_Your Answer_**
>
> _(Rules only in FastAPI. The domain then has no rules of its own, so anything not coming through HTTP skips them. A script or a test could save a location with inverted thresholds.

Mutating the builder after build(). If the product shares the builder's list, changing the builder later changes an object that was already checked. My build() copies the zones into a new tuple and the entities are frozen, so that cannot happen.)_