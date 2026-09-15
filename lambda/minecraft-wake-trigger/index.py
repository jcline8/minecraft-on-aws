import os
import json
import logging
import boto3
from botocore.exceptions import ClientError
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment Variables
DISCORD_PUBLIC_KEY = os.environ.get("DISCORD_PUBLIC_KEY", "")
CLUSTER_NAME = os.environ.get("CLUSTER_NAME", "minecraft-cluster")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "minecraft-service")

ecs_client = boto3.client("ecs")

def lambda_handler(event, context):
    logger.info("Received interaction request.")

    # ==========================================
    # 1. PRE-AUTH (Computationally Inexpensive)
    # ==========================================
    headers = event.get("headers", {})
    body = event.get("body", "")

    # 1a. Ensure number of headers is within an expected range
    # API Gateway typically sends 20-40 headers. Reject absurdly large payloads.
    if not (5 <= len(headers) <= 70):
        logger.warning(f"Pre-Auth Failed: Unexpected header count ({len(headers)}).")
        return {"statusCode": 400, "body": "Bad Request"}

    # 1b. Ensure body length is within expected bounds
    # Discord payloads vary in size. PINGs are small, Slash Commands are larger.
    if not (10 <= len(body) <= 2048):
        logger.warning(f"Pre-Auth Failed: Unexpected body length ({len(body)} bytes).")
        return {"statusCode": 400, "body": "Bad Request"}

    # 1c. Ensure required authentication headers are present
    # API Gateway HTTP APIs may lowercase headers
    signature = headers.get("x-signature-ed25519") or headers.get("X-Signature-Ed25519")
    timestamp = headers.get("x-signature-timestamp") or headers.get("X-Signature-Timestamp")
    
    if not signature or not timestamp:
        logger.warning("Pre-Auth Failed: Missing required signature headers.")
        return {"statusCode": 401, "body": "Unauthorized"}

    # =================================================
    # 2. AUTHENTICATE (Ed25519 Signature Verification)
    # =================================================
    try:
        verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
        # The verification string is the concatenation of timestamp and body
        verify_key.verify(f"{timestamp}{body}".encode("utf-8"), bytes.fromhex(signature))
    except (BadSignatureError, ValueError) as e:
        logger.error(f"Authentication Failed: Signature verification failed - {e}")
        # If verification fails, Lambda must immediately return HTTP 401 Unauthorized
        return {"statusCode": 401, "body": "invalid request signature"}

    # Parse the validated JSON body
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Invalid Body Format: Unable to parse and load body as JSON.")
        return {"statusCode": 400, "body": "Invalid JSON format"}

    interaction_type = payload.get("type")

    # Handle Discord Verification PING (Type 1)
    if interaction_type == 1:
        logger.info("Handling Discord PING interaction.")
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"type": 1})  # Required response: {"type": 1}
        }

    # Handle Application Command (Type 2)
    if interaction_type == 2:
        command_name = payload.get("data", {}).get("name")
        
        if command_name != "wake":
            logger.warning("Received unhandled command name.")
            return {"statusCode": 400, "body": f"Unhandled command name: {command_name}"}
    else:
        logger.warning("Received unhandled interaction type.")
        return {"statusCode": 400, "body": f"Unhandled interaction type: {interaction_type}"}

    # ============================
    # 3. QUERY ECS SERVICE STATUS
    # ============================
    logger.info("Querying ECS service status...")
    try:
        response = ecs_client.describe_services(
            cluster=CLUSTER_NAME,
            services=[SERVICE_NAME]
        )
        services = response.get("services", [])
        active_services = [svc for svc in services if svc.get('status') == 'ACTIVE']
        
        if not active_services:
            logger.warning(f"Service {SERVICE_NAME} not found in cluster {CLUSTER_NAME}.")
            message_content = "Error: Minecraft server service could not be found."
            return _build_discord_response(message_content)
            
        service = active_services[0]
        desired_count = service.get("desiredCount", 0)
        running_count = service.get("runningCount", 0)

    except ClientError as e:
        logger.error(f"AWS ECS ClientError: {e}")
        return _build_discord_response("Failed to query server status due to an AWS service error.")

    # =============================
    # 4. EXECUTE STATE TRANSITIONS
    # =============================     
    if desired_count == 0:
        try:
            ecs_client.update_service(
                cluster=CLUSTER_NAME,
                service=SERVICE_NAME,
                desiredCount=1
            )
            logger.info("Server is offline. Scaling up to desiredCount = 1...")
            message_content = "Minecraft server wake-up initiated! It should be ready in 2 to 3 minutes."

        except ClientError as e:
            logger.error(f"AWS ECS ClientError on update_service: {e}")
            message_content = "Failed to trigger server wake-up due to an AWS service error."

    elif desired_count == 1 and running_count == 0:
        logger.info("Server is already in the process of starting up.")
        message_content = "Minecraft server is currently booting up. Please wait a minute and try connecting."
    else:
        logger.info("Server is already running.")
        message_content = "Minecraft server is already online and running!"

    return _build_discord_response(message_content)

def _build_discord_response(message):
    """Helper method to format the Type 4 Discord channel message."""
    # type: 4 stands for CHANNEL_MESSAGE_WITH_SOURCE, which posts a standard reply to the user
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "type": 4,
            "data": {
                "content": message
            }
        })
    }
