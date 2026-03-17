# Running Guard Demo in Docker

These instructions work on **Mac** (Docker Desktop), **Windows** (Docker Desktop), and **Linux** (Docker Engine).

---

## Build the image

From the project root (where the Dockerfile is):

```bash
docker build --no-cache -t guard-demo .
```

---

## Run the container

**Mac / Windows:**

```bash
docker run -it -p 3000:3000 guard-demo
```

**Linux** (so the app can reach host services like ToolHive via `host.docker.internal`):

```bash
docker run -it -p 3000:3000 --add-host=host.docker.internal:host-gateway guard-demo
```

Then open **http://localhost:3000** in your browser.

---

## Connecting to ToolHive (or other host services)

When the app runs **inside** the container, `127.0.0.1` refers to the container, not your machine. ToolHive and other MCP servers usually run on the **host**, so the app must use the host address.

- **Mac / Windows:** Use the hostname **`host.docker.internal`** in your tool URLs.
- **Linux:** Use the run command above with `--add-host=host.docker.internal:host-gateway`, then use **`host.docker.internal`** in your tool URLs.

**Example:** If ToolHive gives you an endpoint like `http://127.0.0.1:51003/mcp`, configure the tool in Admin → Tool Management as:

```text
http://host.docker.internal:51003/mcp
```

Use the same port ToolHive shows; only change `127.0.0.1` to `host.docker.internal`.

---

## Use the pre-built image (no local build)

Supports **amd64** and **arm64**:

```bash
docker run -it -p 3000:3000 vmummer/guard-demo
```

On Linux, add `--add-host=host.docker.internal:host-gateway` if you need to reach ToolHive or other host services from inside the container.
