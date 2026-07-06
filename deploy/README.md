# Deploying Memora to Alibaba Cloud ECS

Goal: get `docker compose up` running on a real ECS instance on day 1 (Phase 0), so
deployment risk is retired early instead of at hour 45.

## 1. Provision the instance

- Console → ECS → create instance, cheapest tier with 2GB+ RAM (pgvector + redis +
  api + web + caddy all on one box for the hackathon).
- Ubuntu 22.04 LTS image.
- Open security group ports: 22 (SSH), 80, 443.
- Note the public IP — this is your `ECS_HOST`.

## 2. Install Docker on the instance

```bash
ssh user@<ecs-ip>
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# re-login for group to take effect
```

## 3. First deploy

From your workstation:

```bash
cp .env.example .env   # fill in real QWEN_API_KEY, set DEMO_DOMAIN if you have one
ECS_HOST=user@<ecs-ip> ECS_PATH=/opt/memora ./deploy/deploy.sh
```

This rsyncs the repo (minus `.git`/`node_modules`) and runs
`docker compose up -d --build` on the box.

## 4. Verify

```bash
ssh user@<ecs-ip> "docker ps"
curl http://<ecs-ip>/api/health
```

## 5. Redeploy

Re-run `./deploy/deploy.sh` after any change — it's idempotent (rsync + compose up).

## Proof-of-deployment recording checklist (submission requirement)

- [ ] SSH into the ECS instance, `docker ps` showing all 5 services healthy
- [ ] Hit the live public URL in a browser
- [ ] Show the ECS console (instance running, region visible)
