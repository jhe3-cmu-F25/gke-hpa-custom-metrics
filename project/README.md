# Inverted Index Search Engine — Client

A lightweight Flask web application that provides a UI for interacting with a
distributed inverted-index search engine.  The client does **no heavy
processing** itself; all computation is delegated to a backend (Hadoop/Spark on
GCP Dataproc) via Kafka message passing.

---

## Project Structure

```
project/
├── client/
│   ├── app.py              # Flask application — routes and Kafka orchestration
│   ├── kafka_client.py     # KafkaProducer / KafkaConsumer wrapper
│   ├── gcp_config.py       # GCP/Dataproc config loader + placeholder job trigger
│   ├── templates/
│   │   └── index.html      # Single-page UI (vanilla JS, no framework)
│   ├── requirements.txt    # Python dependencies
│   ├── Dockerfile          # Multi-stage Docker image
│   └── docker-compose.yml  # Compose file — passes .env into the container
├── .env.example            # Template for required environment variables
└── README.md               # This file
```

---

## Quick Start

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in real values for KAFKA_BROKER, GCP_PROJECT_ID, etc.
```

### 2. Run with Docker Compose

```bash
cd client/
docker compose up --build
```

The app will be available at `http://localhost:5000`.

### 3. Run locally (dev)

```bash
cd client/
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
flask run --port 5000
```

---

## Environment Variables

All variables are documented in [`.env.example`](.env.example).  Key ones:

| Variable | Description |
|---|---|
| `KAFKA_BROKER` | `<ip>:9092` — external GKE LoadBalancer address |
| `KAFKA_TOPIC_*` | Request/response topic names |
| `KAFKA_RESPONSE_TIMEOUT` | Seconds to wait for backend response (default 120) |
| `GCP_PROJECT_ID` | GCP project for Dataproc |
| `GCP_REGION` | GCP region (e.g. `us-central1`) |
| `DATAPROC_CLUSTER_NAME` | Name of the provisioned Dataproc cluster |

---

## Kafka Message Schema

### `search-request` (produced by client)
```json
{ "correlation_id": "<uuid>", "scholar_url": "https://scholar.google.com/..." }
```

### `search-response` (consumed by client)
```json
{ "correlation_id": "<uuid>" }
```

### `search-term-request` (produced by client)
```json
{ "correlation_id": "<uuid>", "term": "neural network" }
```

### `search-term-response` (consumed by client)
```json
{
  "correlation_id": "<uuid>",
  "results": [
    { "doc_id": "10.1109/...", "url": "https://ieeexplore.ieee.org/...",
      "doc_name": "Paper Title", "citations": 42, "frequency": 7 }
  ],
  "execution_time": 0.342
}
```

### `topn-request` (produced by client)
```json
{ "correlation_id": "<uuid>", "n": 10 }
```

### `topn-response` (consumed by client)
```json
{
  "correlation_id": "<uuid>",
  "results": [
    { "term": "machine learning", "total_frequency": 198 }
  ]
}
```

---

## Kafka Deployment Plan

Kafka will be deployed on **Google Kubernetes Engine (GKE)** using the
**Confluent Kafka Helm chart**, provisioned entirely via **Terraform**.

### Infrastructure provisioning (Terraform)

1. **GKE Cluster** — a dedicated node pool is created for Kafka brokers using
   the `google_container_cluster` and `google_container_node_pool` Terraform
   resources.

2. **Confluent Kafka Helm release** — the official
   `confluentinc/cp-helm-charts` chart is installed into the cluster via the
   `helm_release` Terraform resource.  The chart deploys ZooKeeper (or KRaft
   in newer versions) and one or more Kafka broker pods.

3. **Topic creation** — topics are created declaratively via a Terraform
   `null_resource` that runs a startup script inside the Kafka pod:

   ```hcl
   resource "null_resource" "kafka_topics" {
     depends_on = [helm_release.kafka]

     provisioner "local-exec" {
       command = <<-EOT
         kubectl exec -n kafka deploy/kafka -- \
           kafka-topics.sh --bootstrap-server localhost:9092 --create \
             --topic search-request         --partitions 3 --replication-factor 1
         kubectl exec -n kafka deploy/kafka -- \
           kafka-topics.sh --bootstrap-server localhost:9092 --create \
             --topic search-response        --partitions 3 --replication-factor 1
         kubectl exec -n kafka deploy/kafka -- \
           kafka-topics.sh --bootstrap-server localhost:9092 --create \
             --topic search-term-request    --partitions 3 --replication-factor 1
         kubectl exec -n kafka deploy/kafka -- \
           kafka-topics.sh --bootstrap-server localhost:9092 --create \
             --topic search-term-response   --partitions 3 --replication-factor 1
         kubectl exec -n kafka deploy/kafka -- \
           kafka-topics.sh --bootstrap-server localhost:9092 --create \
             --topic topn-request           --partitions 3 --replication-factor 1
         kubectl exec -n kafka deploy/kafka -- \
           kafka-topics.sh --bootstrap-server localhost:9092 --create \
             --topic topn-response          --partitions 3 --replication-factor 1
       EOT
     }
   }
   ```

4. **External access** — a Kubernetes `LoadBalancer` Service is created for
   each Kafka broker.  GKE automatically provisions a GCP Network Load Balancer
   and assigns a static external IP address.

5. **Client connectivity** — the external IP is stored in the `.env` file as
   `KAFKA_BROKER=<external-ip>:9092`.  The Docker container reads this value at
   startup and the `KafkaClient` class uses it as the `bootstrap_servers`
   address.  No VPN or private networking is required for the client during
   development.

### Architecture diagram

```
┌─────────────────────────────────────────────────────┐
│  Local Machine (Docker)                             │
│  ┌──────────────────────────────────────────────┐   │
│  │  Flask App  ──►  KafkaProducer               │   │
│  │             ◄──  KafkaConsumer               │   │
│  └────────────────────┬─────────────────────────┘   │
└───────────────────────┼─────────────────────────────┘
                        │ KAFKA_BROKER=<external-ip>:9092
                        ▼
┌─────────────────────────────────────────────────────┐
│  GKE Cluster (Terraform + Confluent Helm chart)     │
│  ┌──────────────────────────────────────────────┐   │
│  │  Kafka Broker Pod(s)                         │   │
│  │  Topics: search-request/response             │   │
│  │          search-term-request/response        │   │
│  │          topn-request/response               │   │
│  └──────────────────────────────────────────────┘   │
│                        │                            │
└────────────────────────┼────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  GCP Dataproc (Hadoop MapReduce backend)            │
│  ┌──────────────────────────────────────────────┐   │
│  │  Kafka Consumer → Run MapReduce Job          │   │
│  │  → Kafka Producer (sends results back)       │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## GCP / Dataproc Integration

`gcp_config.py` loads GCP credentials from `.env` and exposes a
`trigger_dataproc_job()` function.  The implementation is currently a
**placeholder** — the TODO comment in the function shows exactly how to wire
up the `google-cloud-dataproc` SDK once the cluster is provisioned.

```python
from gcp_config import trigger_dataproc_job
job_id = trigger_dataproc_job(job_args=["gs://bucket/input", "gs://bucket/output"])
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `Flask` | Web framework |
| `kafka-python` | Kafka producer/consumer |
| `python-dotenv` | Load `.env` into `os.environ` |
| `google-cloud-dataproc` | Submit Hadoop jobs to GCP Dataproc |
