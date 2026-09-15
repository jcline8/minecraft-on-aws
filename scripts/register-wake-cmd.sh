#!/usr/bin/env bash

source ../.env.sh

curl -X POST "https://discord.com/api/v10/applications/$DISCORD_APP_ID/commands" \
  -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "wake",
    "description": "Wake up the Minecraft ECS Fargate server."
  }'
