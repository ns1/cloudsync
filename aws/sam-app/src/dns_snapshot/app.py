import os
import json
import requests
import logging

import boto3
from crhelper import CfnResource

logger = logging.getLogger(__name__)
helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL', sleep_on_delete=120, ssl_verify=None)

MAX_PAGE_SIZE = 100 # in terms of records

try:
    route53 = boto3.client('route53')
    endpoint = os.environ.get('ENDPOINT')

except Exception as e:
    helper.init_failure(e)


def retrieve_secret(secret_id): 
    url = f'http://localhost:2773/secretsmanager/get?secretId={secret_id}'
    headers = { "X-Aws-Parameters-Secrets-Token": os.environ.get('AWS_SESSION_TOKEN') }
    response = requests.get(url, headers=headers)

    # will raise an exception if not 200
    response.raise_for_status()
    response = response.json()

    logger.debug(response)

    # this key will be there unless the request fails
    return response['SecretString']


def snapshot_zone(zone, aws_account_id, endpoint):
    page_counter = 0
    marker = None

    while True:
        kwargs = {
            'HostedZoneId': f"/hostedzone/{zone['Id']}",
            'MaxItems': str(MAX_PAGE_SIZE)
        }

        if marker is not None:
            kwargs.update(marker)

        response = route53.list_resource_record_sets(**kwargs)
        page_counter += 1

        msg = {
            'source': 'AWS-Route53',
            'version': 1,
            'account_id': aws_account_id,
            'auth_key': retrieve_secret(os.environ['SECRET_NAME']),
            'msg_type': 'snapshot',
            'page': page_counter,
            'truncated': response['IsTruncated'],
            'num_records': len(response['ResourceRecordSets']),
            'zone_id': zone['Id'],
            'zone_name': zone['Name'],
            'payload': response['ResourceRecordSets']
        }
        
        json_payload = json.dumps(msg)
        headers = {
            'content-type' : 'application/json',
            'content-length' : str(len(json_payload))
        }

        put_response = requests.put(endpoint, data=json_payload, headers=headers)

        if put_response.status_code != 200:
            logger.error(f"PUT to {endpoint} failed with {put_response.status_code}: {put_response.content}")
            raise Exception

        if not response['IsTruncated']:
            break

        marker = {
            'StartRecordName': response['NextRecordName'],
            'StartRecordType': response['NextRecordType'],
            'StartRecordIdentifier': response['NextRecordIdentifier']
        }


@helper.create
def create(event, context):
    aws_account_id = context.invoked_function_arn.split(":")[4]
    marker = None

    if endpoint is None:
        logger.error("ENDPOINT env variable not set")
        raise Exception

    endpoint = f"{endpoint}/dns"

    while True:
        kwargs = dict()
        if marker is not None:
            kwargs['Marker'] = marker

        response = route53.list_hosted_zones(**kwargs)

        for zone in response['HostedZones']:
            snapshot_zone(zone, aws_account_id, endpoint)

        if not response['IsTruncated']:
            break

        marker = response['NextMarker']


def lambda_handler(event, context):
    helper(event, context)