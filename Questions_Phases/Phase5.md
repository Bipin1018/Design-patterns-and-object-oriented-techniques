# Phase 5 — Adapter questions

**Pattern / focus:** Adapter.

**Read first:** [Guide 05](../../materials/guides/05-adapter.md) · [Requirements](requirements.md)

## How to answer

- Use your own wording. Do not paste teaching-example types (for example a legacy XML calendar client) as if they were your greenhouse classes.
- When a question asks about *this application*, refer to sensor ports, adapters, readings, and `sensor_readings` from the lab.
- Short answers are fine when the question is narrow. Write a few sentences when it asks you to explain or compare.
- Write each answer inside the matching **Your Answer** note. Replace the placeholder; leave the question text unchanged.

## A. Pattern

1. State the intent of Adapter in plain language. What problem appears when business code speaks a vendor or legacy protocol (odd field names, units, XML, status codes) directly?

> > [!NOTE]
> ***Your Answer***
>
> Adapter lets two things work together that were not built to. You keep the
> interface your code wants, and write a small class that turns someone else's
> version into it.
>
> If business code speaks the vendor's language directly, the vendor's habits
> spread through the whole app. Our supplier reports moisture as a whole number
> out of a thousand instead of a fraction, so 412 means 0.412. Without an
> adapter, the code that saves readings has to know that. So does the sampler.
> So does the part that decides when to water.
>
> Then a second supplier turns up measuring it some other way, and you have to
> edit all three again. The vendor's format has quietly become your format, and
> now neither can change without breaking the other.

2. Name the participants (**target / port**, **adaptee**, **adapter**, **client**). What does the adapter translate, and what must it **not** decide (business policy)?

> > [!NOTE]
> ***Your Answer***
>
> - **Target / port** — the interface the client already expects. `SensorPort`,
>   with one method that returns a `Reading`.
> - **Adaptee** — the thing you cannot change. A supplier's payload, an MQTT
>   message body.
> - **Adapter** — the class in between. It implements the port and reads the
>   adaptee.
> - **Client** — the code that calls the port and never learns which adapter
>   answered.
>
> The adapter translates shape, names and units. 412 out of a thousand becomes
> 0.412. A timestamp in milliseconds becomes a real date.
>
> It must not decide anything about the greenhouse. Whether 0.412 is dry enough
> to water is a policy question, not a translation one, and it belongs in
> Strategy. Put it in the adapter and every new supplier has to repeat the rule,
> and two of them can end up disagreeing about the same reading.

3. GoF distinguishes an **object adapter** (composition) from a **class adapter** (inheritance). Which does modern code prefer, and why?

> > [!NOTE]
> ***Your Answer***
>
> Object adapter.
>
> A class adapter inherits from the adaptee, so it inherits everything the
> adaptee has, useful or not. It needs multiple inheritance to work, and it ties
> you to one adaptee forever.
>
> An object adapter holds the adaptee as a field instead. It exposes only the
> target's methods, and it can swap the adaptee, wrap several, or choose one at
> runtime.

## B. This phase of the application

4. What is `SensorPort` in this lab, and what normalized value type (for example `Reading`) do adapters return? Why do application services depend on the port rather than on a simulation driver or vendor SDK?

>> > [!NOTE]
> ***Your Answer***
>
> `SensorPort` is an abstract class in the domain with one method:
> `read(device) -> Reading`. Adapters return `Reading` — device_id, value,
> unit, source, recorded_at.
>
> Services depend on the port so they stay still while the edges move. A new
> protocol changes the selector and nothing else. It also keeps the domain free
> of FastAPI, SQLAlchemy and broker clients, so the adapter tests run with no
> database.

5. You need three translations onto the same normalized reading: a simulation adapter, a vendor stub, and an MQTT translator that accepts a payload dict. Why is the different raw shape the point of the exercise? How does `source` (`simulation`, `vendor`, or `mqtt`) show which adapter produced the reading, and why must the MQTT translator not open a broker in this phase? Phase 12 may deliver that same dict on a device HTTP route or through an optional broker — why must this phase still not open either transport?
> [!NOTE]
> ***Your Answer***
>
> If all three sent the same shape, no adapter would be doing any work. The
> differences are the exercise. Simulation has no payload — it invents a number
> in range. The vendor sends a whole number out of a thousand and a timestamp in
> milliseconds, so both get converted. MQTT sends a dict that is close already,
> but may carry no timestamp, or write it with a `Z` the parser cannot read.
> Three problems, one `Reading` out of each.
>
> `source` is the adapter's signature. Each one sets its own, so the stored row
> says which translation produced it, and the card shows it as a badge.
>
> The MQTT translator takes a dict and nothing else, so its test needs no
> broker, no socket, no network. Translation is a pure function of its input.
>
> Opening a connection would put transport work inside a class whose job is
> translation. The test would then need a running broker to prove that 0.41
> becomes 0.41, which has nothing to do with connections. Keeping them apart
> means transport can be added later without this class changing at all.

6. Readings are **appended** to `sensor_readings` (history grows). Why not keep only the latest value in memory or overwrite a single row, and which later phase consumes this history? Why do a manual read, the simulation sampler, and (later) MQTT share **one** writer of that table? Why does the sampler skip devices with tracking off and MQTT devices, and why do sensor cards poll the latest stored reading until Phase 12?

> > [!NOTE]
> ***Your Answer***
>
> Keeping it in memory means the value disappears when the app restarts.
> Overwriting one row is not much better — you keep the newest number but throw
> away everything before it. A reading is a record of what a sensor said at a
> moment, so nothing updates or deletes one. Changing it would be lying about
> what happened.
>
> A later phase needs that history: it looks at the most recent moisture for a
> zone and compares it against that zone's limits.
>
> All three ways in go through one writer so there is only one place to change.
> Later on, every reading will need to announce itself, and that only works if
> they all pass through the same method. Three writers means three places to
> remember, and one of them eventually gets forgotten.
>
> The sampler skips devices with tracking off because the user switched them
> off. It skips MQTT devices because those report for themselves — making up a
> value for one would be inventing data the device never sent. That is the same
> reason a manual read on one is refused.
>
> The cards check for new values every few seconds because the browser has no
> other way to find out the sampler wrote something. It is marked temporary in
> the code so nobody mistakes it for the final design.

7. `POST /api/sensors/{id}/read` runs an adapter, persists, and returns a DTO. What HTTP status is appropriate when the device is missing versus when the adapter fails? Why must the router never see vendor-shaped types?

>> [!NOTE]
> ***Your Answer***
>
> **404** when the device is missing. You asked about something that is not
> there.
>
> **400** when the adapter fails. The device exists, but the request could not
> be served — a malformed payload, an unknown device type, or a device that
> cannot be read on demand.
>
> **201** on success, because a read creates a row.
>
> The router must not see vendor types because that is the leak the pattern
> exists to stop. If it imported the supplier's payload class, it would break
> when the supplier changed their format, and a second supplier would mean
> editing the router. It imports the reading DTO, the ingest service and the
> not-found error, and nothing else.
>
> That works because the adapter error is a plain `ValueError` underneath. The
> router catches a built-in type and never has to know the failure came from an
> adapter at all.

## C. Compare, contrast, and scenarios

8. Contrast Adapter with **Facade**. Adapter changes the **shape** of an existing interface; Facade simplifies **how to use** a subsystem. Give a greenhouse-shaped example of each (Adapter this phase; Facade in Phase 7).

> > [!NOTE]
> ***Your Answer***
>
> Adapter changes shape. You have one interface and want another, and the
> adapter converts between them. It usually wraps one thing.
>
> Facade simplifies use. The parts underneath already work fine on their own,
> but calling them in the right order is fiddly. The facade gives you one easy
> way in.
>
> **Adapter, this phase.** The vendor adapter takes the supplier's payload —
> moisture as a whole number out of a thousand, a timestamp in milliseconds —
> and returns a `Reading`. Same information, different shape.
>
> **Facade, Phase 7.** Watering a zone means fetching its moisture, fetching its
> limits, deciding, and then driving the pump. A facade offers one call that
> does all four in order. Nothing is translated. What it removes is the sequence
> you would otherwise have to remember.

9. Contrast Adapter with **Decorator**. Both wrap an object. What is different about the interface they present to the client?

>> [!NOTE]
> ***Your Answer***
>
> A decorator presents the **same** interface as the thing it wraps. An adapter
> presents a **different** one.
>
> That follows from what each is for. A decorator adds behaviour — retry,
> logging, caching — so the caller has to be able to drop it in exactly where
> the original went. If it changed the interface you could not stack two of
> them.
>
> An adapter exists because the interfaces do not match. Changing the interface
> is the job.
>
> `ActuatorPort` will show this later. The simulation actuator is the innermost
> object, and a wrapper around it will have the same `apply` method, so the
> caller cannot tell them apart and you can wrap it again. That is why the port
> exists in this phase even though nothing drives it yet — there has to be
> something to wrap.

10. A classmate puts irrigation policy (“if moisture &lt; 0.3 then water”) inside the vendor adapter. Why is that a trap? Where should that decision live instead (later Strategy), and what should stay in the adapter?
> > [!NOTE]
> ***Your Answer***
>
> It is a trap because the rule is now stuck to one supplier. Devices on the
> simulation adapter never get watered, because that adapter has no such rule.
> Add a second supplier and you either copy the rule or forget to, and copies
> drift apart until they disagree about the same number.
>
> The limit also belongs to a zone, not a supplier. Every zone sets its own, and
> an adapter has no idea which zone a device sits in. Hardcoding 0.3 throws that
> away.
>
> The decision belongs in Strategy, which takes a zone's limits and its latest
> reading and decides. One rule, one place.
>
> The adapter keeps translation: read the payload, fix the units, fix the
> timestamp, set the source, return a `Reading`. It should not know what the
> number means, only what shape it should be in.