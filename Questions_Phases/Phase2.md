A. Pattern
1.State the intent of Factory Method in plain language. What problem appears when callers scatter new / constructors (or a growing if type == ...) across the application?
Note

Your Answer

Factory Method is a pattern where a class defines a method for creating an object, but lets its subclasses decide which object that method actually returns.
When constructors are spread around, every type's details are spread around too. Add a new type and we have to find and change every one of those places.if we  Miss one and something breaks quietly. One growing if type == ... is the same problem.

2.Name the main participants of Factory Method (product, concrete product, creator, concrete creator, client). For each, give one sentence: what it is responsible for.
Note

Your Answer

Product — the thing being made.
Concrete product — one real version of it.
Creator — says a thing whicch is made, but does not pick which one.
Concrete creator — picks which one, and its settings.
Client — asks for a thing. Does not pick the class.

3.How do you add a new product variant when creators are polymorphic (new class + registry entry) versus when creation lives in one shared if/elif function? Why does that difference matter for extension?
Note

Your Answer

With creators: write one new class, add one line to the list. Nothing else is touched.

With one big if: you have to open code that already works and change it.

difference: Adding new code cannot break the old code. Editing it can.

B. This phase of the application
4.In this lab, what is the product and what are the concrete creators? Why must the API handler (or sensor service) go through a creator/registry instead of constructing MoistureSensor / LightSensor itself?
Note

Your Answer

The product is Sensor. The creators are MoistureSensorCreator and LightSensorCreator
The route asks get_creator instead of making the sensor itself. Otherwise the settings would live in the web code, and every new type would mean editing the route.

5.POST /api/sensors accepts a short type key such as "moisture" or "light", while the stored/returned field is device_type (for example moisture_sensor). Why are those two fields different? Who decides the stored device_type and default_config?
Note

Your Answer

type is the short word the user sends, like moisture. device_type is what we store, moisture_sensor.the creator picks the stored device_type and the default_config. The user cannot set them.

6.Why is there a single devices table with role="sensor" instead of a dedicated sensors table? What later phase does that choice prepare for?
Note

Your Answer

Pumps, vents and lamps are devices too and fit the same columns. role says which kind each row is.
Phase 3 adds them. One table means they are just new rows, not a new table with its own code.

7.What should happen when the client posts an unknown type? Where should that rejection be decided (registry/service vs router constructing a concrete class anyway)?
Note

Your Answer

When the client posts an unknown type, the API should send back 400 and say which types are valid. Nothing should be saved.
The registry decides this. get_creator does not recognise the key, so it raises an error, and the router turns that into a 400.

C. Compare, contrast, and scenarios
8.Contrast Factory Method with a simple factory (one function full of if type == ...). When is the simple factory “good enough,” and why does this phase still want polymorphic creators?
Note

Your Answer

A simple factory is one function with a list of ifs. That is good enough with two or three types that are not going to grow.
We use creators because more types are coming, and because each creator is a place to put that type's own behaviour later.


9.Contrast Factory Method with Abstract Factory (Phase 3). Factory Method answers which question? Abstract Factory answers which different question? Why is Factory Method enough for Phase 2 sensors?
Note

Your Answer

Factory Method answers: which one do I make?

Abstract Factory answers: which matching set do I make?

Phase 2 makes one sensor at a time, so the first question is enough. Phase 3 needs a sensor and an actuator that go together so Factory method is only enough for phase 2.

A classmate puts SQLAlchemy session commits (or FastAPI request parsing) inside a concrete creator. Why is that a trap? Where should persistence and HTTP stay instead?
Note

Your Answer

It is a trap because the domain would then need the database and the web framework to work at all. My creator tests run right now with nothing else started, and that would stop being true
Saving belongs in DeviceRepository, and HTTP belongs in the router. The service is what puts the two together: it asks the creator for a sensor, then hands it to the repository.