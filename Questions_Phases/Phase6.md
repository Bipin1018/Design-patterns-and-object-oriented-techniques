# Phase 6 — Strategy questions

**Pattern / focus:** Strategy.

**Read first:** [Guide 06](../../materials/guides/06-strategy.md) · [Requirements](requirements.md)

## How to answer

- Use your own wording. Do not paste teaching-example types (for example shipping quotes) as if they were your greenhouse classes.
- When a question asks about *this application*, refer to irrigation (or lighting) policies, location context, and the automation API from the lab.
- Short answers are fine when the question is narrow. Write a few sentences when it asks you to explain or compare.
- Write each answer inside the matching **Your Answer** note. Replace the placeholder; leave the question text unchanged.

## A. Pattern

1. State the intent of Strategy in plain language. How does the **context** use a strategy, and why must “choose which algorithm” stay separate from “run the algorithm”?

> [!NOTE]
> ***Your Answer***
>
> _(Strategy means putting each way of doing a job in its own class, so you can switch between them without changing the code that calls them.

In our app the caller is AutomationService. It fetches the zones, their thresholds and the latest moisture, puts them in a small object, and calls decide. It never checks which strategy it is holding.

Picking and running are separate because they happen at different times. Picking happens once, when someone chooses a key in the dropdown and we save it. Running happens every time you press Evaluate. If the service picked the strategy itself, it would need to know about all of them, and adding a new one would mean editing it again. Only get_strategy turns a key into a class.)_

2. Name the participants (**strategy**, **concrete strategies**, **context**, **client**). What goes wrong when all policies live as `if/elif` inside the context (or inside an HTTP router)?

> [!NOTE]
> ***Your Answer***
>
> _(The strategy is AutomationStrategy, a base class with one method, decide. The two concrete strategies are ConservativeMoistureStrategy and AggressiveMoistureStrategy. The context is AutomationService, which collects the data and calls decide. The client is the API route and the dashboard panel; they send a location and a key, never a class name.

If all the rules were if/elif in the route, the watering rules would live in the file that handles web requests. Adding a rule means editing a function that also handles errors, so a watering change could break a 404. Testing one rule would need a fake web client, when the rule is really just comparing two numbers. And since the chain is written once, two sites could never use different rules. Our route has no if on the key at all.)_

3. When should you use Strategy, and when should you skip it (one algorithm only; or the variation is a **lifecycle mode** rather than a chosen policy)?

> [!NOTE]
> ***Your Answer***
>
> _(Use it when there is more than one sensible way to do the job and somebody outside the code chooses. That is our case: watering early and watering late are both fine, and the person running the greenhouse decides.

Do not use it for a single rule. A base class and a lookup table around one rule is extra work for nothing. Also do not use it when the thing changes by itself as it goes through stages, because that is State. The simple test is who changes it. A person choosing means Strategy. The object changing itself means State.)_

## B. This phase of the application

4. In this lab, what does a strategy’s `decide(context)` return (action + reason)? Give a concrete difference you implemented (or were required to implement) between **conservative** and **aggressive** on the **same** moisture reading and zone thresholds.

> [!NOTE]
> ***Your Answer***
>
> _(It returns a Recommendation: an action, either irrigate or wait, a reason written in plain words, and an optional score for how urgent it is. The reason matters as much as the action, because that is what the dashboard shows.

Say Bench 1 has thresholds 0.25 and 0.45, and the moisture is 0.30. Conservative only looks at the low threshold. 0.30 is still above 0.25, so it waits. Aggressive uses the middle of the band, 0.35. 0.30 is below that, so it waters. Same number, same zone, two different answers. They also look at different things: aggressive checks the light too and waters sooner on a bright day, because bright light dries the soil faster. Conservative ignores light. If the only difference had been a number, one class with a setting would have been enough.)_

5. Where do the numbers in `LocationAutomationContext` (or your equivalent) come from? Latest moisture may already be in `sensor_readings` from a manual read, the simulation sampler, or MQTT translation — why does this phase not add a scheduler or a broker? Why must strategies receive a plain context object, not SQLAlchemy rows or FastAPI types? Why are thresholds read from **zones**, not hardcoded in the strategy class?

> [!NOTE]
> ***Your Answer***
>
> _(The thresholds come from the zones table and the moisture from the sensor_readings table. One query per sensor type picks the newest reading in each zone. A reading only counts for a zone if the device that made it is assigned to that zone, so a zone with no sensor does not borrow someone else’s number. Both strategies just say there is nothing to judge.

We did not add a scheduler or a broker because Phase 5 already built the one place that writes readings. A manual read, the sampler and MQTT all go through ReadingIngest. This phase just reads the table and does not care who filled it. Adding a second sampler would mean two things writing the same rows on different timers, and the next strange reading would be hard to trace.

Strategies get a plain object so their tests need no database and no setup. The context is just numbers and ids. If we passed a database row instead, every test would need a database connection, and the strategies would depend on the table layout.

The thresholds come from zones because each bench has its own. Bench 1 is 0.25 to 0.45 and Bench 2 is 0.20 to 0.50. A number written into the strategy would be the same everywhere, and Phase 4 existed so people could set them per zone. The zone says what the range is; the strategy decides where inside it to act.)_

6. The active `strategy_key` is **persisted** per `location_id` (for example in `automation_rules`). Why must `POST .../automation/evaluate` use the **saved** key rather than a key the client sends only in that request? What happens on the next evaluate after the operator changes strategy but moisture stays the same?

> [!NOTE]
> ***Your Answer***
>
> _(Because the choice belongs to the greenhouse, not to whoever is asking. If the key came in the request, two people could evaluate the same place seconds apart and get different answers, and both would be correct. There would be no way to say what the site is actually set to. Phase 7 needs to show the current strategy, which only works if there is one. It also survives a restart, since the dropdown is just a control and the saved row is the real setting. Our evaluate does not accept a key at all.

Change the strategy and press Evaluate again with the same moisture, and the answer can change. At 0.30 on Bench 1, conservative waits and aggressive waters. The panel warns you if you change the dropdown without saving, because evaluate uses the saved one.)_

7. Strategy **recommends** (irrigate / wait). It should not itself start a pump. Why keep **decide** separate from **execute**? Which later pattern is meant to carry out the action?

> [!NOTE]
> ***Your Answer***
>
> _(Because they go wrong in different ways. Deciding is just maths on numbers you were given, so there is nothing to retry and nothing to undo. Turning on a pump can jam, time out, or run twice. If they were one thing, you could not test the rule without a pump, and you could not retry the pump without deciding again. Keeping them apart means you can see the decision before anything happens, which is what the dashboard does now. That is how you spot wrong thresholds before flooding a bench. It is the same rule as Phase 5: an adapter translates but does not decide, a strategy decides but does not act.

Command, in Phase 9. ActuatorPort and the simulation actuator already exist and are unused, waiting to be wrapped in something that can be queued, logged and undone.)_

## C. Compare, contrast, and scenarios

8. Contrast Strategy with **State** (Phase 8). Both delegate to an object with the same shape. Who typically **changes** the active object, and is the variation a **policy** or a **lifecycle**?

> [!NOTE]
> ***Your Answer***
>
> _(They look the same on paper, so the difference is who does the swapping. With Strategy a person chooses, and the choice is a setting. Our operator picks a key and it stays until someone changes it. The strategies do not know about each other and none of them can switch to another.

With State the object changes itself as it goes along. A watering run goes idle, watering, cooling down, idle, and each stage decides what comes next. Nobody picks cooling down; you end up there because watering just finished. Two quick questions tell them apart: could you stay in it forever, and can the thing switch itself? Conservative is yes and no. Watering is no and yes.)_

9. Contrast Strategy with **Adapter** (Phase 5) and with **Builder** (Phase 4). Which one translates a foreign API, which one assembles a valid aggregate, and which one swaps an algorithm?

> [!NOTE]
> ***Your Answer***
>
> _(Adapter translates. A supplier sends 412 out of a thousand with the time in milliseconds, and the adapter turns it into 0.412 vwc. The format changes, the meaning does not, and it has no opinion about whether that is dry.

Builder assembles. LocationConfigBuilder collects a name and some zones and checks nothing until build, which either gives you a valid setup or raises an error. You get one correct object, not a choice.

Strategy swaps. Two classes answer the same question differently, and the saved key picks one. All three work together rather than competing. One evaluate uses all of them: Builder made the zone and its thresholds, Adapter produced the reading, Strategy compares the two and decides.)_

10. A classmate writes one “mega-strategy” that still contains `if conservative` / `if aggressive` inside a single class. Another strategy class calls the actuator adapter to water immediately. Explain why each is a trap.

> [!NOTE]
> ***Your Answer***
>
> _(The mega-strategy just moved the if/elif one level down. The base class and the saved key are there, but the branch is still inside the single class. Adding a third rule still means editing the file the other two live in, changing one rule can break another, and you cannot test one on its own because there is only one decide. The giveaway is that the class has to be told which of its own behaviours to use. A proper strategy already knows, because the key picked it before decide ran.

The strategy that waters has gone from advising to doing. Its test now needs a pump for what is just comparing two numbers. You can no longer see a decision without it happening, so pressing Evaluate waters the bench, and pressing it twice waters it twice. Retrying a failed pump means deciding again, which may give a different answer because the moisture has moved. Same lesson as Phase 5, and why the simulation actuator stays unused until Command wraps it in Phase 9.)_