# CLAUDE.md — Predictive Maintenance Multi-Agent System

## 1. Project Overview

### What This Project Does
This is a **multi-agent predictive maintenance system** for industrial equipment (centrifugal pumps). Four specialized AI agents collaborate to monitor sensor data, diagnose anomalies, recommend maintenance actions, and manage repair workflows — all orchestrated by LangGraph and deployed on Microsoft Azure.

### The Problem It Solves
Industrial factories have hundreds of pumps, motors, and compressors with sensors measuring vibration, temperature, pressure, and power. Currently, human engineers manually monitor dashboards, check manuals, diagnose problems, and create maintenance tickets. This system automates that entire chain using AI agents.

### The Four Agents
- **Monitor Agent**: Watches real-time sensor streams (vibration, temperature, pressure, power). Detects anomalies using ISO 10816 vibration standards and statistical z-score analysis. Outputs anomaly alerts with severity levels.
- **Diagnostics Agent**: Analyzes anomaly patterns against known failure modes from a RAG knowledge base using Claude API. Generates a diagnosis with a confidence score (0.0 to 1.0).
- **Recommendation Agent**: Based on the diagnosis, recommends specific maintenance actions, estimates urgency (immediate/scheduled/monitoring), and calculates cost of inaction in EUR.
- **Workflow Agent**: Orchestrates the response — creates maintenance tickets in PostgreSQL, notifies teams, schedules downtime, and tracks resolution status.

### How Agents Communicate
Agents communicate through LangGraph's shared `AgentState` (a TypedDict). The supervisor graph routes between agents using conditional edges:
- Monitor finds anomaly → routes to Diagnostics
- No anomaly → stops (no wasted API calls)
- Diagnosis confidence > 0.7 → routes to Recommendation
- Diagnosis confidence low → retries (max 2 times)
- Recommended action is "immediate" or "scheduled" → routes to Workflow
- Recommended action is "monitoring" only → stops (no ticket needed)

### Target Domain
Stuttgart industrial market — Bosch, Mercedes-Benz, ZF, Siemens Energy. The anomaly detection uses real engineering standards (ISO 10816) and authentic failure patterns (bearing wear, cavitation, misalignment) based on mechanical engineering knowledge.

### Deployment Target
Microsoft Azure (App Service, no Docker). CI/CD via GitHub Actions.

---

## 2. Tech Stack

### Language
- **Python 3.11+** — all code is Python. No other languages.

### Core Frameworks
| Framework | Version | Purpose |
|-----------|---------|---------|
| LangGraph | latest | Agent orchestration — state machine with conditional routing |
| LangChain-Anthropic | latest | Bridges LangGraph to Claude API |
| Anthropic SDK | latest | Direct Claude API calls for diagnosis and reasoning |
| FastAPI | latest | REST API layer serving the agent system |
| Uvicorn | latest | ASGI server running FastAPI |
| Pydantic | v2+ | Data validation for all models (SensorReading, Diagnosis, etc.) |
| Pydantic-Settings | latest | Environment variable management via .env files |

### AI and Knowledge
| Tool | Purpose |
|------|---------|
| Claude API (Sonnet) | LLM reasoning for diagnosis, recommendations, action planning |
| MCP (Model Context Protocol) SDK | Tool integration — 3 custom MCP servers |
| ChromaDB | Vector database for RAG knowledge base (failure mode docs) |
| PyMuPDF | PDF parsing for maintenance manual ingestion |
| Langfuse | LLM observability — tracing, latency, cost tracking |

### Data and Infrastructure
| Tool | Purpose |
|------|---------|
| NumPy | Sensor data simulation, z-score anomaly detection |
| Redis | Inter-agent event bus (Pub/Sub) |
| PostgreSQL (asyncpg) | Maintenance ticket storage, event logs, audit trail |
| python-dotenv | Loads .env file for local development |

### Azure Services (Production)
| Service | Purpose | Tier |
|---------|---------|------|
| Azure App Service | Hosts FastAPI application | B1 (Basic) |
| Azure Cache for Redis | Agent event bus | Basic C0 |
| Azure Database for PostgreSQL | Ticket and event storage | Burstable B1ms |
| Azure Key Vault | Secure API key storage | Free |
| Azure Monitor | Logging and alerting | Free (5GB/month) |

### Dev Tools
| Tool | Purpose |
|------|---------|
| pytest | Unit and integration testing |
| pytest-asyncio | Testing async agent functions |
| httpx | Testing FastAPI endpoints |
| ruff | Linting and code formatting |
| Git + GitHub | Version control |
| GitHub Actions | CI/CD pipeline |

---

## 3. Architecture Overview

### Directory Structure
```
predictive-maintenance-agents/
├── src/
│   ├── __init__.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── state.py               # Shared state: SensorReading, AnomalyAlert, Diagnosis, MaintenanceAction, AgentState
│   │   ├── supervisor.py           # Main LangGraph graph — orchestrates all 4 agents
│   │   ├── monitor_agent.py        # Anomaly detection (ISO 10816 + z-score)
│   │   ├── diagnostics_agent.py    # Failure mode diagnosis via Claude + RAG
│   │   ├── recommendation_agent.py # Action planning + cost estimation
│   │   └── workflow_agent.py       # Ticket creation + scheduling
│   ├── mcp_servers/
│   │   ├── __init__.py
│   │   ├── sensor_data_server.py   # MCP server: exposes sensor metrics as tools
│   │   ├── knowledge_server.py     # MCP server: RAG knowledge base queries
│   │   └── task_server.py          # MCP server: maintenance ticket CRUD
│   ├── data/
│   │   ├── __init__.py
│   │   ├── simulator.py            # SensorSimulator class — generates fake pump data
│   │   ├── anomaly_injector.py     # Injects bearing_wear, cavitation, misalignment patterns
│   │   └── failure_modes.json      # Known failure mode definitions (JSON)
│   ├── knowledge/
│   │   ├── __init__.py
│   │   ├── ingestion.py            # PDF parsing + embedding pipeline
│   │   ├── vector_store.py         # ChromaDB abstraction layer
│   │   └── docs/                   # Sample maintenance PDF manuals
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application with lifespan
│   │   ├── routes.py               # API endpoint definitions
│   │   └── schemas.py              # Pydantic request/response models
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── dashboard.py            # Streamlit real-time monitoring dashboard
│   │   └── logger.py               # Structured logging + Langfuse integration
│   └── config/
│       ├── __init__.py
│       └── settings.py             # Pydantic Settings — reads .env into typed config
├── tests/
│   ├── conftest.py                 # Shared test fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_simulator.py       # Tests for sensor data generation
│   │   ├── test_monitor_agent.py   # Tests for anomaly detection logic
│   │   └── test_diagnostics_agent.py
│   └── integration/
│       ├── __init__.py
│       └── test_full_pipeline.py   # End-to-end agent pipeline tests
├── .github/
│   └── workflows/
│       └── deploy.yml              # CI/CD: test → deploy to Azure
├── pyproject.toml                  # Project config + all dependencies
├── requirements.txt                # Pinned deps for Azure deployment
├── startup.sh                      # Azure App Service startup command
├── .env.example                    # Environment variable template
├── .env                            # Real API keys (NEVER committed)
├── .gitignore                      # Excludes .env, .venv, __pycache__
├── CLAUDE.md                       # This file — project instructions
└── README.md                       # Public-facing docs with architecture diagram
```

### Data Flow
```
Sensor Data (simulated)
    │
    ▼
Monitor Agent ──── no anomaly? ──── STOP
    │
    │ anomaly detected
    ▼
Diagnostics Agent ──── low confidence? ──── retry (max 2x)
    │
    │ diagnosis ready
    ▼
Recommendation Agent ──── monitoring only? ──── STOP
    │
    │ action needed
    ▼
Workflow Agent ──── creates ticket ──── DONE
```

### Key Files and Their Roles
- **state.py** is the single source of truth for all data models. Every agent imports from here.
- **supervisor.py** contains the LangGraph StateGraph with all nodes and conditional edges.
- **settings.py** is the only file that reads environment variables. Everything else imports `settings`.
- **simulator.py** generates fake data. In production, this would be replaced by real sensor feeds via MCP.

---

## 4. Coding Conventions

### Python Style
- **Python 3.11+ features**: Use `str | None` instead of `Optional[str]`. Use `list[str]` instead of `List[str]`.
- **Type hints everywhere**: Every function parameter and return type must be annotated.
- **Pydantic models for all data**: Never pass raw dicts between functions. Always use typed Pydantic models.
- **Async by default**: All agent nodes and API endpoints are `async def`. Use `await` for I/O operations.
- **Docstrings**: Every class and public method gets a one-line docstring. Use triple double quotes.

### Naming
- **Files**: lowercase with underscores — `monitor_agent.py`, `vector_store.py`
- **Classes**: PascalCase — `SensorSimulator`, `SensorReading`, `AgentState`
- **Functions**: lowercase with underscores — `detect_anomalies`, `build_graph`
- **Constants**: UPPER_SNAKE_CASE — `THRESHOLDS`, `DIAGNOSIS_PROMPT`
- **Private methods**: prefix with underscore — `_with_noise`, `_apply_anomaly`

### Imports
- Standard library first, then third-party, then local imports. Blank line between each group.
- Use absolute imports from `src`: `from src.agents.state import SensorReading`
- Never use `import *`.

### Error Handling
- Wrap all Claude API calls in try/except with retry logic (max 3 retries, exponential backoff).
- MCP server tool calls must handle timeouts (30 second default).
- Never let an agent crash silently — log every error with structured logging.
- Return graceful fallback responses when LLM calls fail.

### Testing
- Every new feature gets a test before or alongside the implementation.
- Test files mirror source files: `src/agents/monitor_agent.py` → `tests/unit/test_monitor_agent.py`
- Use `pytest.mark.asyncio` for all async test functions.
- Use seeded random generators (`seed=42`) for reproducible test data.
- Mock Claude API calls in unit tests — never make real API calls in tests.

### Git Conventions
- Commit messages: present tense, imperative — "Add monitor agent" not "Added monitor agent"
- Commit often: one logical change per commit.
- Branch names: `feature/monitor-agent`, `fix/anomaly-threshold`, `test/simulator-tests`
- Never commit `.env`, API keys, or `__pycache__`.

---

## 5. Common Commands

### Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (Windows CMD)
.venv\Scripts\activate.bat

# Install all dependencies
pip install -e ".[dev]"
```

### Running the Application
```bash
# Run FastAPI server locally
uvicorn src.api.main:app --reload --port 8000

# Run Streamlit dashboard
streamlit run src/monitoring/dashboard.py

# Quick test: generate sensor data
python -c "from src.data.simulator import SensorSimulator; sim = SensorSimulator('PUMP-001'); print(sim.generate(5)[0])"

# Quick test: check settings load
python -c "from src.config.settings import settings; print(settings.environment)"
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run only unit tests
pytest tests/unit/ -v

# Run a specific test file
pytest tests/unit/test_simulator.py -v

# Run tests with print output visible
pytest tests/ -v -s

# Run tests matching a keyword
pytest tests/ -v -k "bearing"
```

### Code Quality
```bash
# Lint all code
ruff check src/ tests/

# Auto-fix lint issues
ruff check src/ tests/ --fix

# Format code
ruff format src/ tests/
```

### Git
```bash
# Check status
git status

# Stage and commit
git add .
git commit -m "Add monitor agent with ISO 10816 thresholds"

# Push to GitHub
git push origin main

# Create a feature branch
git checkout -b feature/diagnostics-agent
```

### Azure Deployment
```bash
# Login to Azure
az login

# Deploy to App Service (after initial setup)
az webapp up --name pred-maint-app --resource-group rg-pred-maintenance --runtime "PYTHON:3.12"

# View live logs
az webapp log tail --name pred-maint-app --resource-group rg-pred-maintenance

# Set environment variable on Azure
az webapp config appsettings set --name pred-maint-app --resource-group rg-pred-maintenance --settings ANTHROPIC_API_KEY=sk-ant-xxxxx

# Generate requirements.txt from installed packages
pip freeze > requirements.txt
```

### Dependencies
```bash
# Add a new dependency: edit pyproject.toml, then reinstall
pip install -e ".[dev]"

# Check what's installed
pip list

# Generate requirements.txt for Azure
pip freeze > requirements.txt
```

---

## 6. Constraints — What NOT To Do

### Security
- **NEVER commit .env or any file containing API keys** to Git. Always check `.gitignore` first.
- **NEVER hardcode API keys** in Python files. Always read from `settings`.
- **NEVER log API keys** or secrets in console output or Langfuse traces.
- **NEVER expose database credentials** in API responses or error messages.

### Code Quality
- **NEVER use raw dicts** for data passing between agents. Always use Pydantic models from `state.py`.
- **NEVER use `print()` for debugging** in production code. Use the structured logger in `monitoring/logger.py`.
- **NEVER use `import *`** from any module.
- **NEVER write agent logic without a corresponding test.**
- **NEVER leave TODO or FIXME comments** in code pushed to main branch.
- **NEVER use `datetime.now()`** — use `datetime.utcnow()` for consistent timestamps.

### Architecture
- **NEVER call Claude API directly from agent nodes** without retry logic and error handling.
- **NEVER modify `state.py` models** without checking all files that import them — they're used everywhere.
- **NEVER create circular imports** — `state.py` imports nothing from the project. Other files import from it.
- **NEVER put business logic in `api/routes.py`** — routes are thin wrappers that call agent functions.
- **NEVER store application state in global variables** — all state flows through `AgentState`.

### LLM Usage
- **NEVER send raw sensor data arrays to Claude** — summarize or aggregate first to save tokens.
- **NEVER trust LLM output without validation** — always parse Claude's response through Pydantic models.
- **NEVER use Claude for simple threshold checks** — the Monitor Agent uses NumPy, not LLM calls.
- **NEVER skip the confidence check** on diagnosis — low confidence triggers a retry, not blind acceptance.

### Azure / Deployment
- **NEVER deploy without running tests first** — the CI/CD pipeline enforces this.
- **NEVER store secrets in Azure App Settings as plain text** — use Azure Key Vault.
- **NEVER use `pip install` directly on Azure** — it reads `requirements.txt` automatically.
- **NEVER forget to generate `requirements.txt`** before deploying — Azure needs this file.

### MCP Servers
- **NEVER make MCP servers depend on each other** — each server is independent and can run alone.
- **NEVER skip timeout handling** on MCP tool calls — set 30-second max per call.
- **NEVER expose internal system details** through MCP tool responses — return clean, structured data only.

### Data
- **NEVER use real company data** in the repository — all data is simulated.
- **NEVER use arbitrary threshold values** for anomaly detection — use ISO standards and engineering knowledge.
- **NEVER generate random anomalies without physical basis** — each pattern must match real failure mechanics.

---

## 7. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key from console.anthropic.com |
| `REDIS_URL` | No (has default) | Redis connection string for agent event bus |
| `DATABASE_URL` | No (has default) | PostgreSQL connection string for ticket storage |
| `LANGFUSE_SECRET_KEY` | No (has default) | Langfuse secret key for LLM tracing |
| `LANGFUSE_PUBLIC_KEY` | No (has default) | Langfuse public key for LLM tracing |
| `ENVIRONMENT` | No (has default) | "development" or "production" |

Only `ANTHROPIC_API_KEY` is required. Everything else has working defaults for local development.

---

## 8. Engineering Context

### ISO 10816 Vibration Severity (Class III — Pumps, Motors, Generators)
| Zone | Vibration (mm/s) | Meaning |
|------|-----------------|---------|
| A (Good) | 0 — 2.8 | Newly commissioned machines |
| B (Acceptable) | 2.8 — 7.1 | Long-term operation acceptable |
| C (Warning) | 7.1 — 11.2 | Not suitable for long-term, plan maintenance |
| D (Critical) | > 11.2 | Damage occurring, stop immediately |

### Anomaly Patterns and Their Physics
| Pattern | Vibration | Temperature | Pressure | Power | Physics |
|---------|-----------|-------------|----------|-------|---------|
| Bearing wear | Gradual rise | Gradual rise | Normal | Normal | Lubricant degrades → friction increases → heat + vibration |
| Cavitation | Erratic spikes | Normal | Sudden drop | Normal | Inlet pressure below vapor pressure → bubble collapse |
| Misalignment | Constant high | Normal | Normal | +15% | Shaft offset → uneven load distribution → motor works harder |

### Sensor Baselines (Centrifugal Pump)
| Sensor | Baseline | Unit | Warning | Critical |
|--------|----------|------|---------|----------|
| Vibration | 2.8 | mm/s | 4.5 | 11.2 |
| Temperature | 62.0 | °C | 85.0 | 105.0 |
| Pressure | 5.5 | bar | < 2.0 or > 8.5 | > 10.0 |
| Power | 45.0 | kW | ±20% deviation | ±40% deviation |
