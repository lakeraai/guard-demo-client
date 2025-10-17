#!/usr/bin/env bash
curl -X POST https://api.lakera.ai/v2/guard      -H "Authorization: Bearer $LAKERA_API_KEY"      -H "Content-Type: application/json"      -d '{
  "messages": [
    { "content": "You are a helpful AI assistant for heathcare inquiries.", "role": "system" },
    { "content": "Is it safe to brush my teeth 8 times a day", "role": "user" },
    { "content": "That might be a bit overkill", "role": "assistant" }
  ],
  "project_id": "project-8541012967",
  "metadata": {
    "user_id": "",
    "ip_address": "123.222.121.009",
    "session_id": "randomuuid"
  },
  "breakdown": true,
  "payload": true,
  "dev_info": true
}'