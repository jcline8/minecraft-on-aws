import os
import json
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2_client = boto3.client('ec2')
route53_client = boto3.client('route53')

HOSTED_ZONE_ID = os.environ['HOSTED_ZONE_ID']
DNS_RECORD_NAME = os.environ['DNS_RECORD_NAME']
DNS_TTL = int(os.environ.get('DNS_TTL', '30'))

def extract_eni_id(event):
    # The ENI id lives inside detail.attachments[], on the entry whose
    # type is "eni". We don't assume attachments[0] since other
    # attachment types could theoretically be present.
    attachments = event.get('detail', {}).get('attachments', [])

    for attachment in attachments:
        if attachment.get('type') != 'eni':
            continue
        for item in attachment.get('details', []):
            if item.get('name') == 'networkInterfaceId':
                return item.get('value')

    raise ValueError("No networkInterfaceId found in event attachments")

def get_public_ip(eni_id):
    # The event only carries the ENI's private IP - the public IP has
    # to be looked up separately via EC2.
    response = ec2_client.describe_network_interfaces(NetworkInterfaceIds=[eni_id])
    interfaces = response.get('NetworkInterfaces', [])
    if not interfaces:
        raise ValueError(f"ENI {eni_id} not found")

    association = interfaces[0].get('Association', {})
    public_ip = association.get('PublicIp')
    if not public_ip:
        raise ValueError(f"ENI {eni_id} has no associated public IP")

    return public_ip

def upsert_dns_record(public_ip):
    # UPSERT overwrites whatever value (or absence of one) currently
    # exists for this name/type in a single atomic call - no separate
    # read-then-delete step needed.
    response = route53_client.change_resource_record_sets(
        HostedZoneId=HOSTED_ZONE_ID,
        ChangeBatch={
            'Comment': 'Minecraft server dynamic IP update',
            'Changes': [
                {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': DNS_RECORD_NAME,
                        'Type': 'A',
                        'TTL': DNS_TTL,
                        'ResourceRecords': [{'Value': public_ip}]
                    }
                }
            ]
        }
    )
    return response['ChangeInfo']['Id']

def lambda_handler(event, context):
    try:
        eni_id = extract_eni_id(event)
        logger.info(f"Extracted ENI ID: {eni_id}")

        public_ip = get_public_ip(eni_id)
        logger.info(f"Resolved public IP: {public_ip}")

        change_id = upsert_dns_record(public_ip)
        logger.info(f"DNS record updated successfully. ChangeId: {change_id}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Updated {DNS_RECORD_NAME} to {public_ip}",
                "changeId": change_id
            })
        }
    except Exception as e:
        logger.error(f"Failed to update DNS record: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Failed to update DNS record"})
        }
