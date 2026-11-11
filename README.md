# ParcelOps — minimal land parcel verification application

A very small application built primarily to demonstrate DevOps. Users register **synthetic** parcel records, view a dashboard, and update status (Pending, Validated, Disputed).

## Start in WSL Ubuntu with Docker Desktop / Docker Engine

```bash
cd ~/projects/parcelops
cp .env.example .env
docker compose up --build -d
docker compose ps
```

Open **http://localhost:8000**. Register parcel `PAR-001` in locality `Agbarho`. Then set its status to **Validated**.

Verify the technical endpoints:

```bash
curl http://localhost:8000/health
curl -s http://localhost:8000/metrics | grep parcelops_http_requests_total | head
```

View logs and shut down:

```bash
docker compose logs -f app
# Ctrl+C exits log display
docker compose down
```

`docker compose down` keeps the PostgreSQL data volume. **Do not run `docker compose down -v` unless you intend to erase demo data.**

## DevOps elements

- Docker image and Docker Compose with a persistent PostgreSQL volume.
- GitHub Actions runs tests and builds a Docker image on push/PR.
- FastAPI endpoints: `/health` and `/metrics` (Prometheus format).
- JSON not needed for the UI: HTML form submit and status updates are enough.
- Container logs are available via `docker compose logs`.

**Next planned phase:** add Prometheus and Grafana services, then deploy to AWS EC2 and build a GitHub Actions deployment job. The starter CI workflow **does not deploy to AWS yet**.

## Run tests without Docker (optional)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Tests use in-memory SQLite only; the actual Compose deployment uses PostgreSQL.

## Important constraints

- Use **synthetic data only**. No real owner details, titles, or sensitive land records.
- There is no user authentication or authorization. This is a classroom demo, **not** a production land registry.
- Before cloud deployment, create a strong `.env` password and limit AWS security-group inbound access to what is necessary; never expose PostgreSQL publicly.
- `.env` is ignored by Git and excluded from the Docker build context.

## Folder structure

```
app/                  FastAPI code, model, templates, CSS
.github/workflows/    GitHub Actions continuous integration
compose.yaml          Application and PostgreSQL service definitions
Dockerfile            Docker image recipe
.env.example          Local configuration template
requirements.txt      Python dependencies
tests/                Automated API/UI workflow tests
```
