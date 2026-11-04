Here's a consolidated **Odysseus Docker Cheat Sheet** that you can keep handy.

---

# 🚀 Start Odysseus

Start all services:

```bash
docker compose up -d
```

---

# 🛑 Stop Odysseus

Stop all services:

```bash
docker compose down
```

---

# 🔄 Restart

Restart everything:

```bash
docker compose restart
```

Restart only the Odysseus container:

```bash
docker compose restart odysseus
```

---

# 🏗️ Clean Rebuild (Recommended after updates)

Keeps all chats, documents, and settings.

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

# 🧹 Factory Reset (Deletes EVERYTHING)

⚠️ Deletes:

* Chats
* Documents
* Settings
* Database
* Docker volumes

```bash
docker compose down -v --rmi local
docker compose build --no-cache
docker compose up -d
```

---

# 📜 View Logs

All services:

```bash
docker compose logs -f
```

Only Odysseus:

```bash
docker compose logs -f odysseus
```

Last 100 lines:

```bash
docker compose logs --tail=100 odysseus
```

---

# 📊 Check Status

Docker Compose services:

```bash
docker compose ps
```

Running Docker containers:

```bash
docker ps
```

---

# 🖼️ Docker Images

```bash
docker images
```

---

# 💾 Docker Volumes

```bash
docker volume ls
```

---

# 🐚 Open a Shell in the Container

Using Bash:

```bash
docker compose exec odysseus bash
```

If Bash isn't available:

```bash
docker compose exec odysseus sh
```

---

# 📦 Install a Temporary Python Package

(Only lasts until the container is recreated.)

```bash
docker compose exec odysseus pip install <package>
```

Example:

```bash
docker compose exec odysseus pip install PyMuPDF
```

---

# 🔍 Inspect Files Inside the Container

Show specific lines:

```bash
docker compose exec odysseus sed -n '860,900p' /app/routes/chat_routes.py
```

Search for text:

```bash
docker compose exec odysseus grep -n "_explicit_web_intent" /app/routes/chat_routes.py
```

---

# 🔄 Update Odysseus

Pull the latest code:

```bash
git pull
```

Rebuild:

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

# 🧾 Check the Running Git Commit

```bash
docker compose exec odysseus git rev-parse --short HEAD
```

---

# 📈 Docker Disk Usage

```bash
docker system df
```

---

# 🧹 Clean Up Unused Docker Resources

Remove unused containers, networks, and cache:

```bash
docker system prune
```

Remove **everything** unused, including old images:

```bash
docker system prune -a
```

⚠️ Only use `-a` if you're okay with Docker deleting unused images.

---

# ⭐ Commands You'll Use Most Often

### Daily Start

```bash
docker compose up -d
```

### Daily Stop

```bash
docker compose down
```

### Check Logs

```bash
docker compose logs -f odysseus
```

### After Pulling Updates

```bash
git pull
docker compose down
docker compose build --no-cache
docker compose up -d
```

### If Something Breaks

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
docker compose logs -f odysseus
```

These commands will cover nearly everything you'll need while using and contributing to Odysseus.
