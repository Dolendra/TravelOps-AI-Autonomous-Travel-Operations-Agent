# Deployment & DevOps Configuration

This document outlines the configurations required to build, deploy, and scale the TravelOps AI platform across local, Docker, and Kubernetes environments.

---

## 📋 Environment Configuration (`.env`)

Create a `.env` file at the project root with the following parameters:

```env
# Database Schema Engine
DATABASE_URL=sqlite:///travelops.db

# JWT Signature Cryptography
JWT_SECRET=travelops-auth-secret-super-key-2026

# Cognitive Gateway Keys (Groq)
GROQ_API_KEY=gsk_your_groq_api_key_here

# External Integrations (Optional)
GOOGLE_MAPS_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
TWILIO_FROM_WHATSAPP=
SMTP_SERVER=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@travelops.ai
```

---

## 🐳 Container Deployment (Docker Compose)

To orchestrate the platform services locally using Docker, run:
```bash
docker-compose up --build
```

### `docker-compose.yml` Services
* **db**: Relational Postgres container storing persistent bookings and audits.
* **backend**: FastAPI server exposing endpoints and launching workflow runtimes.
* **frontend**: React SPA compiled with Vite and served on port `5173`.

---

## ☸️ Cloud Orchestration (Kubernetes)

The project includes production-ready Kubernetes manifests located under the `/kubernetes` directory:

```
kubernetes/
├── backend-deployment.yaml    # Configures FastAPI backend Pod replicas
├── service-backend.yaml       # Exposes internal backend cluster ports
├── frontend-deployment.yaml   # Configures frontend client served via NGINX
├── service-frontend.yaml      # Exposes frontend server ports
└── ingress.yaml               # Sets path routes mapping host traffic to services
```

### Apply Configurations
Deploy all service resources to your active Kubernetes cluster:
```bash
kubectl apply -f kubernetes/
```

### Scaling Configurations
The backend deployment includes horizontal scaling and health checking specs:
* **Replicas**: Multi-pod deployment (e.g. `replicas: 3`).
* **Probes**: Configures `livenessProbe` and `readinessProbe` checking the `/health` endpoint to automatically restart degraded pods.
