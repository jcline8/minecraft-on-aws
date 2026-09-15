#!/usr/bin/env bash

source ../../.env.sh

# Login
aws sso login --profile $AWS_POWUSR_PROFILE

# CloudFormation Deploy
aws cloudformation deploy \
  --template-file ../../templates/minecraft-control-stack.yaml \
  --stack-name mc-control \
  --parameter-overrides \
    DiscordPublicKey=$DISCORD_PUBLIC_KEY \
    PyNaClLayerArn=$PYNACL_ARN \
    MinecraftIamStackName=mc-iam \
    MinecraftDnsStackName=mc-dns \
  --profile $AWS_POWUSR_PROFILE

# CloudFormation Describe Stacks
API_ENDPOINT=$(
  aws cloudformation describe-stacks \
    --stack-name mc-control \
    --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
    --output text \
    --profile $AWS_POWUSR_PROFILE
)
echo "API Endpoint: $API_ENDPOINT"
