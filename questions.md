Phase 1 — Skeleton questions
Pattern / focus: Course intro and an empty-but-running three-tier skeleton (no GoF pattern this phase).

Read first: Guide 01 · Requirements

How to answer
Use your own wording. Do not paste textbook definitions or teaching-example class names as if they were your greenhouse types.
When a question asks about this application, refer to what you built (or what the lab required): layers, routes, and tooling.
Short answers are fine when the question is narrow. Write a few sentences when it asks you to explain or compare.

A. Pattern

1.In your own words, what is a design pattern? What is it not?
Design pattern is a way of solving a  certain problem. is is a pattern that erveryone can use while dealing with the same sorts of problems which comes frequently in a code.
It is not the actual code or the libraries used in the code is just the way of dealing the problem in the code. 

2.Name the three GoF pattern families. For each family, give one-sentence: what kind of design problem it addresses. Then place Factory Method and Strategy into the correct family.

A. creational: Problems about how objects are made.
B: Structural: problems about how classes and object are put together into bigger parts.
C: Behavioural: problems about how object talk to each other and divide the work.

Factory Method belongs to the creational family. Strategy belongs to the behavioural family.

3.A teammate wants to add a pattern “because it is on the course list,” even though the feature is small and unlikely to grow. When should you skip a pattern? What risk do you take if you apply one too early?

we can skip it when the feature is small, when there is only one case to deal with, and we  have no real sign that more cases are coming.
If we add too early it will be more complicated since unnecessray classes and code are created. 

B. This phase of the application
4.Why does Phase 1 ship a vertical slice that does almost no greenhouse business logic? What does “empty but running” prove that a folder of unimplemented classes would not?

Because it proves the whole chain of broweser API and database works and if anythiing is broken will show up.
empty classes prove nothing. The code compiles, but we do not know if the container starts, if the port is free, or if the API can log in to the database. 

5.List the four backend layer packages used in this course (domain, application, infrastructure, interfaces/api). For each, state what belongs there and give one example of something that must not live in domain.
The four backend layers:
domain- the greenhouse ideas themselves and the rules about them
application- the use cases. The steps needed to get something done, using the domain.
infrastructure- the technical side. In my project this is settings.py (reads the environment) and db.py (the SQLAlchemy engine, the session).
interfaces/api- the HTTP side. Routes, and the shapes that go in and out over the network.

Something that must not live in domain: a database table definition, web routes and the shapes used for requests and replies.


6.What does GET /health return, and why does it check the database instead of only reporting that the HTTP process is up? Why is API documentation served at /scalar, and why is /docs disabled?

GET /health sends back a short message with two parts: how things are overall, and whether the database answered. All well means ok and ok. Database down means degraded and fail.

It checks the database because the API can be running while the database is not. The app then looks fine but can do nothing.

The docs sit at /scalar because that is the one this course uses. The other doc page is off, so there is only one place to look.


7.Phase 1 requires Alembic (or equivalent) with a baseline migration and no business tables such as devices. Why introduce the migration toolchain before any product schema? What would go wrong if you created tables by hand in Postgres and only added migrations later?

To test the tool while there is nothing to lose. The first migration makes no tables. If something is set up wrong, I find out now, not in next part

Tables made by hand leave no record. Someone else cannot build the same database. And the tool, added later, does not know what is already there, so its first run either fails or has to be faked.

C. Compare, contrast, and scenarios
8.Explain dependency direction in this skeleton: which layers may import which? Why must domain code not import FastAPI, SQLAlchemy, or Pydantic models used as HTTP schemas?

Domain uses nothing from the others. Application may use domain. Infrastructure does the technical work and may know the domain. The API sits on the outside and may use application and infrastructure.
Domain should not touch the web or database tools, because those change. If we Swap the database later, and the greenhouse rules should stay the same. It also lets the rules be tested with nothing else running.

9.The frontend cannot show a healthy badge. A classmate blames “the patterns.” What should you check first (stack, CORS/proxy, health JSON), and why is that a Phase 1 concern rather than a later pattern concern?

There are no patterns yet, so they cannot be the cause. What I check, in order:
Is everything running: the database container, the backend, the frontend.
Does the API answer on its own when I call /health? If it says the database failed, the problem sits between the API and the database.
If the API is fine but the badge is not, i will look in the browser. Then it is CORS, or the frontend pointing at the wrong address.

This is a Phase 1 thing because it is all wiring: ports, settings, and whether the browser may call the API. Patterns only makeup code better we already wrote. It is no help if the two sides never talk.


10.Course completion is at Phase 12, not Phase 1. What is still missing after a successful skeleton, and how do later phases add behaviour without rewriting the foundations you laid here?
Almost everything. No devices, no readings, no limits, no rules no login, hardly any tests, nothing about putting it online.

Later phases fill the empty spaces instead of moving them. New greenhouse things go in domain, new jobs in application, new tables come as new migrations on top of the first one, new routes in the API folder. So Phase 2 can fill the Sensors box without touching the layout.