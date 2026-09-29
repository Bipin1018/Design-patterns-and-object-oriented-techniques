# Phase 3 — Abstract Factory questions

**Pattern / focus:** Abstract Factory.

**Read first:** [Guide 03](../../materials/guides/03-abstract-factory.md) · [Requirements](requirements.md)

## How to answer

- Use your own wording. Do not paste teaching-example types (for example warrior/mage class kits) as if they were your greenhouse classes.
- When a question asks about *this application*, refer to device families, provision, and the unified devices API from the lab.
- Short answers are fine when the question is narrow. Write a few sentences when it asks you to explain or compare.
- Write each answer inside the matching **Your Answer** note. Replace the placeholder; leave the question text unchanged.

## A. Pattern

1. State the intent of Abstract Factory in plain language. What goes wrong when related products are chosen independently (`if format` for each piece) instead of as a **family**?

> [!NOTE]
> ***Your Answer***
>
> _(Factory means you ask for a whole set at once, instead of picking the parts one by one. You choose the family first. After that, every part you get comes from that family.If you pick each part on its own, nothing keeps them matching. You can end up with a fake pump and a real sensor in the same greenhouse. They cannot work together. The same check also gets written in several places, and it is easy to miss one.)_


2. Name the main participants (**abstract factory**, **concrete factory**, **abstract products**, **concrete products**, **client**). How does choosing a factory at the start **commit** the client to one family?

> [!NOTE]
> ***Your Answer***
>
> Abstract factory — says a set gets made. Does not say what is in it. 
Concrete factory — one family. Decides the parts and their settings.
Abstract products — the shape all the parts share.
Concrete products — the real parts of one family.
Client — asks for a set. Does not pick the parts.
The client picks a factory once. Everything it gets back comes from that one family. It never handles the parts itself, so it cannot mix them by mistake.


3. When should you use Abstract Factory, and when should you skip it (for example only one product type per request, or mixing siblings is valid)?

> [!NOTE]
> ***Your Answer***
>
> _(Use it when the parts have to match each other, and when there is more than one full setup to switch between.
Skip it when a request only makes one thing, or when mixing parts is fine. Then it is extra classes for nothing. Phase 2 was that case: one sensor at a time, nothing to match.)_


## B. This phase of the application

4. In this lab, what is a **device family**, and what does `create_device_set()` (or your equivalent) return? Why must a simulation kit and an edge kit not mix incompatible siblings?

> [!NOTE]
> ***Your Answer***
>
> _(A device family is a group of devices that are built for the same setup and are meant to be used together. This project has two: simulation, which is fake and runs in software, and edge, which is stub hardware wired to pins.

create_device_set() gives back four devices: a moisture sensor, a light sensor, a water pump and a grow light. All four carry the same family.

Mixing them breaks the kit, because each family reaches its devices in a different way. Simulation reads and writes values in software, so its parts use protocol: sim. Edge talks to real pins, so its parts use gpio-stub and pin numbers. A sim pump cannot be driven by a pin, so a kit with one of each would simply not work, and nothing stored in the row would explain why.


5. Phase 2 Factory Method creators still exist. How does Abstract Factory **compose** them rather than replace them? What would you lose if you deleted the sensor creators and inlined all construction inside the family factory?

> [!NOTE]
> ***Your Answer***
>
> _(Composing means the family factory asks the creators to build the sensors instead of building them itself. Both of my families call get_creator("moisture") and get_creator("light"). They take the sensor that comes back, turn it into a Device, and add the family and the protocol. The settings inside stay the same: the moisture sensor still has unit: vwc and 300 seconds, because the creator chose those, not the family.
If I deleted the creators and wrote the sensors inside each family instead, the same settings would exist in two places and would slowly drift apart. Adding a new sensor type would mean editing every family. And /api/sensors would break, because it calls the creators directly.)_

6. Why add a `device_family` column on the existing `devices` table (with a default/backfill such as `"simulation"`) instead of a new table per family? What happens to Phase 2 sensor rows if you forget the backfill?

> [!NOTE]
> ***Your Answer***
>
> _(A family is not a different kind of thing. It is a label on a device. The columns are the same either way.A table per family would mean copying the table, the model, the repository and the routes every time a family is added. Listing everything would then need a union.
If we forget the backfill, the Phase 2 sensor rows end up with no family at all. The column is NOT NULL, so the migration fails on them. Making the column nullable to dodge that just leaves those rows matching neither family.)_

7. `POST /api/devices/provision` returns a kit (expected size: two sensors and two actuators). `GET /api/devices` can filter by `family` and `role`. Why must the UI be able to filter by family? Why do `/api/sensors` routes from Phase 2 still need to work?

> [!NOTE]
> ***Your Answer***here
>
> _(Both kits live in the same table. Without a filter the list shows simulation and edge side by side. That is the exact mix the pattern exists to stop, so the UI has to ask for one family at a time.

/api/sensors still has to work because the dashboard Sensors section uses it, and later phases build on it. Adding Phase 3 should not break what already works.)_


## C. Compare, contrast, and scenarios

8. Draw the contrast in one paragraph: Factory Method vs Abstract Factory. Use the questions “which **one** product?” versus “which product **line**?” and mention that Abstract Factory often **uses** Factory Method–style methods inside.

> [!NOTE]
> ***Your Answer***
>
> _(Factory Method asks which one product to make. Abstract Factory asks which product line to make. The first gives you one object. The second gives you a set of parts that belong together. They are not rivals, and Abstract Factory usually calls Factory Method style code inside itself. Like: SimulationDeviceFactory.create_device_set() calls the Phase 2 creators for its two sensors, so the family factory answers "which kit" and the creators answer "which sensor" inside it.)_

9. A DTO or HTTP handler constructs concrete simulation/edge device types directly, bypassing the family factory. What consistency bug can that reintroduce? How should HTTP stay on the abstract factory / service instead?

> [!NOTE]
> ***Your Answer***
>
> _(The mix comes straight back. If a handler builds an edge pump itself, nothing checks that the rest of the kit is edge too. Nothing checks the settings match either. A device could be saved with the wrong protocol, or the wrong family, and still look fine in the list.

HTTP should stop at the service.router reads the family from the query and passes it to DeviceFamilyService, then maps what comes back to DTOs. It never names SimulationDeviceFactory and never builds a Device itself.)_


10. Someone proposes a single “god factory” that creates locations, readings, and devices “because we already have a factory.” Why is that a misuse of Abstract Factory?

> [!NOTE]
> ***Your Answer***
>
> _(A factory family holds things that go together and get swapped together. Locations, readings and devices are not alternatives to each other. There is no "simulation location" that must match a "simulation reading" the way a sim pump must match a sim sensor.

A god factory would just be a bag of unrelated create functions, edited again for every new thing. Having a factory is not a reason to put everything in it.)_