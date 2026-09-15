Factory Method

Problem

Moisture and light sensors need different settings. A moisture measures in vwc, samples every 5 minutes and has a dryness threshold. A light sensor measures in lux, samples every minute and has a daylight target.

Without a pattern, that choice ends up as a chain of ifs inside the route. Every new sensor type means editing it, and editing every other place that builds a sensor.

Solution

SensorCreator has one method, create_sensor. Each creator below it makes one kind of sensor and knows that kind's settings. Callers ask get_creator for one by short name, so they never pick a class themselves.
An unknown name raises an error, which the API turns into a 400. Nothing is saved.

Where to look
File
backend/src/domain/sensors/entity.py
backend/src/domain/sensors/creators.py	
backend/src/application/sensors/service.py	
backend/src/interfaces/api/sensors.py	
backend/tests/test_creators.py          	

Exercise: add a temperature sensor
Add a TemperatureSensorCreator in creators.py returning temperature_sensor with its own defaults, e.g. unit: celsius and a frost threshold.
Add "temperature": TemperatureSensorCreator() to _CREATORS.
Add a test next to the existing ones.

Nothing else changes. The service, router, repository and dashboard all keep working, because none of them knows the concrete creators exist.