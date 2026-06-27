# Contributor Guidelines

We welcome contributions to TravelOps AI. To ensure code quality, safety, and reliability across our event-driven architecture, please follow these guidelines.

---

## 🛠️ Registering New Tools

To register a tool for use by cognitive agents and workflow compiler templates:
1. **Define the Tool Logic**: Write a Python function in `backend/tools/travel_tools.py` or create a new service module.
2. **Expose Signatures**: Annotate arguments with strict type hints (e.g. `origin: str`) and add docstrings describing parameters.
3. **Register Globals**: Add the tool definition to the global registry mapping in `backend/tools/travel_tools.py` specifying:
   - Tool name
   - Execute handler function
   - Circuit breaker configuration parameters (e.g. failure thresholds)
   - Idempotency naming patterns

---

## 📝 Compiling Custom Workflows

To create a new declarative workflow:
1. Add a new `.yaml` template file in `backend/workflows/definitions/`.
2. Ensure the template defines target tasks, dependencies, parallel switches, and rollback compensation handlers.
3. Ensure no circular dependencies exist. The workflow compiler will reject graphs with dependency cycles.

---

## 🧪 Testing Guidelines

### 1. Writing Unit Tests
All new features, tools, or agents must include unit tests. Add test cases under the `tests/` directory matching the pattern `test_*.py`.

### 2. Mocking LLM Requests
For test reliability and cost prevention, avoid executing live HTTP requests in unit tests. Use mock adapters to stub LLM inputs and model router answers. Refer to `tests/test_runtime_context.py` for examples.

### 3. Execution Commands
Before submitting code, ensure the entire test suite passes:
```bash
# Discover and run all tests
.venv/Scripts/python -m unittest discover -s tests -p "test_*.py"

# Run integration tests
.venv/Scripts/python -m unittest tests/test_integrations.py
```
---

## ✍️ Coding & Commit Conventions

* **Typing**: Enforce strict PEP 484 type annotations for all public functions.
* **Comments**: Preserve all docstrings and explainability logs detailing design choices.
* **Commits**: Use conventional commits (e.g., `feat(agent): register new weather solver`, `fix(workflow): solve circular compile errors`).
