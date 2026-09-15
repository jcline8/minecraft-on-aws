#!/usr/bin/env bash

source ../../.env.sh

# Login
aws sso login --profile $AWS_POWUSR_PROFILE

# CloudFormation Deploy
aws cloudformation deploy \
  --template-file ../../templates/minecraft-core-stack.yaml \
  --stack-name mc-core \
  --parameter-overrides AdminIp=$ADMIN_IP \
  --profile $AWS_POWUSR_PROFILE
