#!/usr/bin/env bash

source ../../.env.sh

# Login
aws sso login --profile $AWS_POWUSR_PROFILE

# CloudFormation Deploy
aws cloudformation deploy \
  --template-file ../../templates/minecraft-compute-stack.yaml \
  --stack-name mc-compute \
  --parameter-overrides \
    MinecraftEcrImageUri=$SERVER_URI \
    ActivityMonitorEcrImageUri=$MONITOR_URI \
    MinecraftIamStackName=mc-iam \
    MinecraftCoreStack=mc-core \
    RconPassword=$RCON_PASSWORD \
  --profile $AWS_POWUSR_PROFILE
