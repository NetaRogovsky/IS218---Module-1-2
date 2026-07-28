# Module 12 Reflection

<!--
This is the separate reflection submission. Fill it in with what actually happened
to you. The grader wants real challenges and how you worked through them, not a
description of the code. Delete these comment blocks before submitting. Keep it to
about a page, written in your own voice.
-->

## What this module involved

<!-- A couple of sentences: adding user register/login and calculation BREAD
endpoints on top of your existing models and schemas, writing integration tests
against Postgres, and wiring CI/CD to push a Docker image to Docker Hub. -->

## Challenges I ran into

<!-- Pick the two or three that were real for you. Some things that genuinely came
up building this on your Module 11 base:
- The bcrypt / passlib version conflict. Newer bcrypt (4.1+/5.x) breaks passlib
  1.7.4 and throws an "error reading bcrypt version" plus a 72-byte password error.
  Pinning bcrypt==4.0.1 in requirements.txt fixed it. This is worth writing about
  because it is a concrete debugging story.
- Moving from the old root main.py (the plain calculator) to app/main.py with an
  auth layer, and updating the Dockerfile and docker-compose command to run
  app.main:app instead of main:app.
- The auth flow: login returns a JWT, the calculation routes require a bearer
  token, and forgetting the Authorize step in /docs gives a confusing 401.
- Setting up DOCKERHUB_USERNAME and DOCKERHUB_TOKEN secrets so the deploy job
  could push, and pointing the workflow at your own repo instead of the hardcoded
  one from Module 11.
- Telling the status codes apart: 422 for schema validation (bad type, too few
  inputs, divide by zero), 400 for business errors (duplicate user), 401 for
  missing or bad auth, 404 for a missing calculation. -->

## How I solved them

<!-- Concrete steps. What you changed, what you ran, what you read. -->

## What I learned or would explore next

<!-- Short. Maybe protecting more routes, testing the refresh-token flow, or
tightening the password rules. -->
