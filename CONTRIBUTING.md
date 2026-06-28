# Contributing to TravelOps AI

We welcome contributions to TravelOps AI! Follow this guide to set up your environment, write clean code, and run tests.

---

## 🛠️ Local Development Guidelines

1. **Format Code**:
   Always format code using `black` before pushing:
   ```bash
   black .
   ```
2. **Lint Code**:
   Run `ruff` check to identify syntax code smells and import sorting:
   ```bash
   ruff check .
   ```

---

## 🧪 Testing Guidelines

This project maintains a robust suite of unit and integration tests. Run tests before submitting a PR:

```bash
# Run the complete test suite
pytest

# Run tests with code coverage metrics
pytest --cov=backend --cov=agents
```

### Writing New Tests
- Place new test files in the `tests/` directory.
- Name files with `test_` prefix (e.g. `test_new_provider.py`).
- Implement async tests using `@pytest.mark.asyncio` decorator.

---

## 🔌 Provider Integration Layer Guide

To add support for a new transit provider:
1. Subclass `BaseTravelProvider` in a new file inside `backend/providers/`.
2. Implement required interfaces: `search_buses()`, `hold_seat()`, `confirm_booking()`, `cancel_booking()`.
3. Register the new provider inside the `ProviderRouter` initialization block in `backend/providers/router.py`:
   ```python
   self.register_provider(NewProviderClass())
   ```

---

## 🤖 Registering New Agents
To register a new specialized agent:
1. Create your agent class in `agents/`.
2. Use the `@register_agent` decorator and define capability tags and version identifiers:
   ```python
   @register_agent(capabilities=["flight_booking"], version="1.0.0")
   class FlightAgent:
       # Agent logic
   ```
