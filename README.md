# Module 12 - User & Calculation Routes + Integration Testing

A FastAPI application with user registration and login plus full BREAD
(Browse, Read, Edit, Add, Delete) endpoints for calculations. Passwords are
hashed with bcrypt, sessions use JWT bearer tokens, and every calculation is
scoped to the authenticated user. Integration tests run against a real Postgres
database in CI, and a passing pipeline builds and pushes a Docker image to
Docker Hub.

## Features

- User model with bcrypt-hashed passwords and JWT access/refresh tokens
- `POST /auth/register` (UserCreate: name, email, username, password + confirm, with strength and match validation)
- `POST /auth/login` (returns tokens) and `POST /auth/token` (form login for the Swagger Authorize button)
- Calculation BREAD, all protected by bearer auth and scoped per user:
  - `GET /calculations` browse
  - `GET /calculations/{id}` read
  - `POST /calculations` add
  - `PUT /calculations/{id}` edit
  - `DELETE /calculations/{id}` delete
- Pydantic validation on every request/response
- Integration tests that hit the live HTTP API, plus model, schema, and unit tests
- GitHub Actions CI/CD: runs all tests, then builds and pushes a Docker image

## Docker Hub

Image: https://hub.docker.com/r/YOUR_DOCKERHUB_USERNAME/module12_is601

```bash
docker pull YOUR_DOCKERHUB_USERNAME/module12_is601:latest
```

## Run the App Locally

The app needs Postgres. The simplest path is Docker Compose:

```bash
docker compose up --build
```

Then open:
- API: http://localhost:8000
- Interactive docs (OpenAPI): http://localhost:8000/docs

## Run Tests Locally

1. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start Postgres (Compose works, or run your own):

```bash
docker compose up -d db
```

4. Point DATABASE_URL at it and run the tests:

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fastapi_db
pytest tests/unit/
pytest tests/integration/
```

To run only the live API endpoint tests:

```bash
pytest tests/integration/test_api_endpoints.py -v
```

## Manual Checks via OpenAPI (/docs)

1. Open http://localhost:8000/docs.
2. Expand `POST /auth/register` and register a user. The password needs 8+ characters with an uppercase letter, a lowercase letter, a digit, and a special character, and confirm_password must match.
3. Expand `POST /auth/login`, log in, and copy the `access_token`.
4. Click Authorize (top right) and paste the token so the calculation routes are authenticated.
5. `POST /calculations` with `{"type": "addition", "inputs": [10, 5, 3]}` and confirm the result is 18.
6. Use `GET /calculations` to browse, `GET /calculations/{id}` to read, `PUT /calculations/{id}` to edit, and `DELETE /calculations/{id}` to delete.

## CI/CD Secrets

The deploy job needs two repository secrets under
Settings > Secrets and variables > Actions:

- `DOCKERHUB_USERNAME`: your Docker Hub username
- `DOCKERHUB_TOKEN`: a Docker Hub access token (Docker Hub > Account Settings > Personal access tokens > Generate)
