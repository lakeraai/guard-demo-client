
<img width="599" height="331" alt="image" src="https://github.com/user-attachments/assets/192e685e-ec1a-42e2-a349-811e91116f04" />

# Deploying the Check Point AI Guardrails Demo in Kubernetes Cluster via a Helm Chart

These instructions should work for a standard Kubernetes Cluster. x86 (amd64) & arm64 based deployments

---

## Deploy the Toolhive Operator CRDS and Toolhive Operator
```bash
helm upgrade --install toolhive-operator-crds oci://ghcr.io/stacklok/toolhive/toolhive-operator-crds 

helm upgrade --install toolhive-operator oci://ghcr.io/stacklok/toolhive/toolhive-operator -n checkpoint --create-namespace
```  

## Deploy the Check Point AI Guardrails Demo Helm Chart 
**Mac / Windows:**

```bash
 helm upgrade --install  cpaiguard oci://registry-1.docker.io/vmummer/cpaiguard  --version 0.2.0 -n checkpoint --create-namespace 
```
Options:

  --set guarddemo.volumePaths.data="/home/checkpoint/guard-data" \
  --set guarddemo.volumePaths.upload="/home/checkpoint/guard-data/uploads" \
  --set guarddemo.replicas=1 \
  --set ingress.host="172.20.27.76.nip.io" \
  --set env.OPENAI_BASE_URL="http://your-ollama-url"      <<< Optional - Remove to default to OpenAI API
```


# Admin Console Settings

Verify the Toolhive Fetch is set to the following:

Fetch
Type:  HTTP(MCP Endpoint)
Endpoint:  http://mcp-cpaiguard-fetch-proxy:8080/mcp      (Note:  If you deploy the Toolhive in its own namespace, you must change it here. In this helm chart, it defaults to checkpoint namespace)


Files
Type: MCP (SSE Endpoint)
Endpoint:  http://mcp-cpaiguard-filesystem-proxy:8080/mcp   (Note:  If you deploy the Toolhive in its own namespace, you must change it here. In this helm chart, it defaults to checkpoint namespace)
