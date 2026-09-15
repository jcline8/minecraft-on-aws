#!/usr/bin/env bash

# Run sub-script to isolate manual environment variables
source ../.env.sh

# Login
aws sso login --profile $AWS_POWUSR_PROFILE

# AWS Account Info
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile $AWS_POWUSR_PROFILE)

# Device Info
MY_IP=$(curl -s checkip.amazonaws.com)
echo "Admin IP: $MY_IP/32"

# PyNacl Lambda Layer Arn
PY_NACL_LL_ARN=$(aws lambda list-layers --compatible-runtime python3.12 --profile $AWS_POWUSR_PROFILE | jq -r '.Layers[0].LatestMatchingVersion.LayerVersionArn')
echo "PyNaCl Lambda Layer ARN: $PY_NACL_LL_ARN"

# To get the ECR image URI
echo "Server ECR Repo URI: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$SERVER_ECR_REPO_NAME:latest"
echo "Monitor ECR Repo URI: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$MONITOR_ECR_REPO_NAME:latest"
