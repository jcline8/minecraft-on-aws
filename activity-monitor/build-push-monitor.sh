#!/usr/bin/env bash

source ../.env.sh

aws sso login --profile $AWS_POWUSR_PROFILE

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile $AWS_POWUSR_PROFILE)

aws ecr get-login-password --region $AWS_REGION --profile $AWS_POWUSR_PROFILE | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

docker build -t $MONITOR_ECR_REPO_NAME .

docker tag $MONITOR_ECR_REPO_NAME:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$MONITOR_ECR_REPO_NAME:latest

docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$MONITOR_ECR_REPO_NAME:latest
