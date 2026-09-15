#!/usr/bin/env bash

source ../../.env.sh

# Login
aws sso login --profile $AWS_ADMIN_PROFILE

# CloudFormation Deploy
aws cloudformation deploy \
  --template-file ../../templates/minecraft-iam-stack.yaml \
  --stack-name mc-iam \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides MinecraftDnsStackName=mc-dns \
  --profile $AWS_ADMIN_PROFILE
