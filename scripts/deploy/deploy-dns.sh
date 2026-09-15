#!/usr/bin/env bash

source ../../.env.sh

# Login
aws sso login --profile $AWS_POWUSR_PROFILE

# CloudFormation Deploy
aws cloudformation deploy \
  --template-file ../../templates/minecraft-dns-stack.yaml \
  --stack-name mc-dns \
  --parameter-overrides DomainName=$SUBDOMAIN \
  --profile $AWS_POWUSR_PROFILE

# CloudFormation Describe Stacks
NAME_SERVERS=$(
  aws cloudformation describe-stacks \
    --stack-name mc-dns \
    --query "Stacks[0].Outputs[?OutputKey=='NameServers'].OutputValue" \
    --output text \
    --profile $AWS_POWUSR_PROFILE
)
echo "Name Servers: $NAME_SERVERS"
