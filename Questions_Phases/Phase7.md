# Phase 7 — Facade questions

**Pattern / focus:** Facade.

**Read first:** [Guide 07](../../materials/guides/07-facade.md) · [Requirements](requirements.md)

## How to answer

- Use your own wording. Do not paste teaching-example types (for example a video publish pipeline) as if they were your greenhouse classes.
- When a question asks about _this application_, refer to the location overview, the facade, and the dashboard Overview page from the lab.
- Short answers are fine when the question is narrow. Write a few sentences when it asks you to explain or compare.
- Write each answer inside the matching **Your Answer** note. Replace the placeholder; leave the question text unchanged.

## A. Pattern

1. State the intent of Facade in plain language. What problem appears when every HTTP handler (or every UI screen) repeats the same multi-step dance across repositories and services?

> [!NOTE]
> **_Your Answer_**
>
Facade puts one simple front door in front of a group of parts that work together. The caller asks one question and gets one answer, without knowing how many parts were involved.

Without it, every handler or screen that needs the same picture repeats the same steps: load the location, then the zones, then the devices, then the readings, then the strategy. That code gets copied, the copies drift apart, and one change means fixing every copy. With a facade the steps live in one place.


2. A facade **orchestrates** collaborators. What should it **not** become (a god object that owns all domain logic)? Where should irrigation policy, sensor translation, and persistence stay instead?

> [!NOTE]
> **_Your Answer_**
>
A facade should collect and combine, not decide. If it starts comparing moisture to thresholds or converting sensor values, it turns into a god object, and every change in the app ends up in that one class.

The rules stay where they already are. Irrigation policy stays in the strategy classes, and the facade only calls evaluate. Sensor translation stays in the adapters, so the facade only sees readings that are already stored. Persistence stays in the repositories, which is why LocationOverviewFacade has no SQL in it.


3. When should you use Facade, and when should you skip it (a single repository call is enough; or you actually need to **translate** a mismatched interface)?

> [!NOTE]
> **_Your Answer_**
>
Use it when a caller needs several parts at once and the same combination is needed in more than one place. Our overview fits: five sources, one picture, and a dashboard that should not care where each piece comes from.

Skip it when one repository call already gives the answer, because wrapping a single call adds a layer with nothing to hide. Skip it when the real problem is a mismatched interface, like a vendor sending permille, because that is Adapter’s job. A facade makes things simpler to call. It does not translate.


## B. This phase of the application

4. What does `GET /api/locations/{location_id}/overview` return? Name the main pieces of the overview DTO: location, assigned device counts, and `zones` (thresholds, assigned devices, and those devices’ latest readings, including `tracking_enabled` and `sampling_interval_seconds`), plus strategy key and last recommendation. Why may those reading rows come from the sampler or MQTT ingest, not only from `POST /read`? Why is overview scoped by `location_id`?

> [!NOTE]
> **_Your Answer_**
>
It returns one overview object with five parts. The location, with its id and name. Device counts, with sensors and actuators counted only when they are assigned to a zone. A list of every zone, even empty ones, each with its two moisture thresholds, its assigned devices, and the latest reading for each of those devices, including tracking_enabled and sampling_interval_seconds copied from the device. The saved strategy key. The last recommendation, with its action and reason.

Readings can come from the sampler or MQTT because every reading goes through the same ReadingIngest into the same sensor_readings table. Where it came from does not matter. Showing only manual reads would hide most of the real data.

It is scoped by location_id because that is how the app has been organised since Phase 4. Zones belong to a location, devices are placed through zones, and the strategy is saved per location.


5. Why does this phase **not** require a new business table? What already exists from Phases 2–6 that the facade only **composes**?

> [!NOTE]
> **_Your Answer_**
>
The overview only reads and combines data that already exists. Nothing new has to be remembered, so no new table is needed. Saving the overview would make it worse, because it would go out of date as soon as a new reading arrived.

It combines devices from Phases 2 and 3, locations and zones from Phase 4, sensor_readings from Phase 5, and the saved strategy and evaluate from Phase 6. The recommendation is worked out each time instead of being saved. I skipped the optional view because the existing tables are enough.


6. The overview HTTP handler should call **only** the facade, not reading/strategy/device repositories directly. Why? How does that help tests and later changes to the query shape?

> [!NOTE]
> **_Your Answer_**
>
If the handler called the repositories itself, the overview rules would live in the HTTP code: which devices count as assigned, which reading is newest, when to call evaluate. That brings back the same “every caller repeats it” problem. Our route has one dependency, the facade, and only does three things: call it, return the result, and turn errors into 404 or 400.

For tests, the facade can be checked on its own, and the API test only checks the HTTP side. For later changes, the queries are hidden. If the way we fetch the newest readings changes, only the repository changes. The route and the JSON stay the same.


7. The location selector may use the existing locations list. The Overview cards come from **one** overview fetch, and Refresh repeats that same fetch. Why must the React page not stitch device, reading, and automation calls together to build the same snapshot? How does a new reading or a saved strategy show up on overview without extra frontend glue?

> [!NOTE]
> **_Your Answer_**
>
If React called devices, readings and automation separately and merged them, the browser would own the overview rules. The same rules would exist in two places and could disagree. The calls could also come back at different moments, so a card might show an old reading next to a new recommendation.

Our panel uses the locations list only to fill the dropdown. Every card comes from one fetchOverview call, and Refresh just repeats it. The facade reads the database on every request, so a new reading or a newly saved strategy shows up on the next fetch automatically. The frontend never has to be told that something changed.


## C. Compare, contrast, and scenarios

8. Contrast Facade with **Adapter**. One makes an existing interface usable; the other makes a subsystem simpler to call. Which is which, and how do both appear in this greenhouse app (Phase 5 vs Phase 7)?

> [!NOTE]
> **_Your Answer_**
>
Adapter makes an existing interface usable. Facade makes a group of parts simpler to call.

In Phase 5 the vendor adapter wraps one thing that speaks the wrong language. It turns permille and milliseconds into a normal reading. In Phase 7 the facade wraps many things that already work, the locations, devices, readings and automation, and puts them behind one call, get_overview.

They work together. The readings the facade shows were already translated by an adapter when they were stored.


9. This phase mentions **N+1** queries. What is an N+1 problem in an overview that lists latest readings for many devices, and what can the facade (or its repository) do about it without putting SQL in the router?

> [!NOTE]
> **_Your Answer_**
>
N+1 means one query to get a list, then one more query for every item in it. For the overview, that would be one query for the devices, then a separate latest-reading query for each device. Ten devices make eleven queries, and a hundred make a hundred and one. It looks fine with one test sensor and gets slow in real use.

We fix it in the repository, not the router. OverviewRepository loads all assigned devices in one query, then the newest reading for all of them in one more query. Matching readings to zones happens in memory, so the number of queries stays the same however many devices there are. Evaluate still looks up moisture once per zone, and that stays inside the automation service on purpose.


10. A classmate hides every error behind a generic “overview failed,” so a missing location, a DB outage, and a strategy error look the same. Why is that a trap for a facade?

> [!NOTE]
> **_Your Answer_**
>
A facade sits in front of many parts, so their errors all pass through it. Turning every failure into one “overview failed” message throws away the thing the caller most needs to know: what went wrong.

The three cases need different answers. A missing location is the user’s mistake and should be a 404. A database outage is our problem and should be a 500, so someone fixes the server. A broken strategy key is a setup problem and should be a 400 that names the key. If they all look the same, the user cannot fix their own mistake, the real outage stays hidden, and debugging becomes guessing. Our route maps each error to its own status. Hiding complexity is the facade’s job. Hiding errors is not.