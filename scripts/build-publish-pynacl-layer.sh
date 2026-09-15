#!/usr/bin/env bash

source ../.env.sh

# 1. Re-create the exact directory structure Lambda expects
mkdir -p pynacl-layer/python

# 2. Download PyNaCl AND its dependencies (cffi, pycparser) for manylinux2014_x86_64
pip install \
  --platform manylinux2014_x86_64 \
  --target ./pynacl-layer/python \
  --only-binary=:all: \
  --implementation cp \
  --python-version 3.12 \
  pynacl cffi

# 3. Verify that _cffi_backend files exist in the layer directory
ls ./pynacl-layer/python/_cffi_backend*

# 4. Zip the directory
cd pynacl-layer
zip -r ../pynacl-layer.zip python
cd ..

# 5. Publish the directory
aws sso login --profile $AWS_POWUSR_PROFILE

aws lambda publish-layer-version \
  --layer-name pynacl-deps \
  --description "PyNaCl binary dependencies for Discord signature verification" \
  --zip-file fileb://pynacl-layer.zip  \
  --compatible-runtimes python3.12 \
  --compatible-architectures x86_64 \
  --profile $AWS_POWUSR_PROFILE

# 6. Clean-up
rm -rf pynacl-layer
rm -f pynacl-layer.zip
