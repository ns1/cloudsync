import os
import boto3
import json

from common import dns_post
from secret_handler import SecretHandler

route53_client = boto3.client('route53')

secret_handler = SecretHandler()

endpoint = os.environ.get('ENDPOINT')
account_id = os.environ.get('ACCOUNT_ID')
snapshot_dest = os.environ.get('SYNC_DEST')


def lambda_handler(event, context):
    try:
        process_health_checks()
        return {"status": "ok", **event}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def process_health_checks():
    paginator = route53_client.get_paginator('list_health_checks')

    for page in paginator.paginate():
        handle_health_checks(page['HealthChecks'], page['IsTruncated'])

def handle_health_checks(health_check_list, is_truncated):
    msg = {
        'source': 'route53',
        'dest': snapshot_dest,
        'version': 1,
        'account_id': account_id,
        'msg_type': 'snapshot',
        'data_type': 'health-checks',
        'zone_name': 'health-checks',
        'zone_id': 'health-checks',
        'page': 1,
        'truncated': is_truncated, 
        'payload': health_check_list
    }
    
    response = dns_post(endpoint, msg, secret_handler)

    if response.status_code != 202:
        raise Exception(f"POST to {endpoint} failed with {response.status_code}: {response.content}")
        