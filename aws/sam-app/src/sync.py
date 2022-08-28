# must be the first import in files with lambda function handlers
import lambdainit  # noqa: F401

import os
import json

import requests

import boto3
from botocore.exceptions import ClientError

def build_response(event, status):
    """A utility function used to build a response to CloudFormation"""

    response_data = {
        'Status': status,
        'Reason': 'Success',
        'PhysicalResourceId': 'myapp::{}'.format(event['LogicalResourceId']),
        'Data': {},
        'RequestId': event['RequestId'],
        "LogicalResourceId": event["LogicalResourceId"],
        "StackId": event["StackId"],
    }
    return response_data


def delete_logs():
    logs_client = boto3.client('logs')
    if (stack_name := os.environ.get('STACK_NAME')) is None:
        return

    delete_logs_with_prefix = '/aws/lambda/{0}'.format(stack_name)
    output = logs_client.describe_log_groups(logGroupNamePrefix=delete_logs_with_prefix)

    for record in output['logGroups']:
        logs_client.delete_log_group(logGroupName=record['logGroupName'])

def snapshot():
    route53 = boto3.client('route53')

    response = route53.list_hosted_zones()
    zones = {zone['Id'].split('/')[-1]: {'fqdn': zone['Name']} for zone in response['HostedZones']}

        

def handler(event, context):
    try:
        request_type = event['RequestType']

        if request_type == "Create":
            pass
        elif request_type == "Delete":
            delete_logs()

        response_data = build_response(event, 'SUCCESS')

    except Exception:
        # Catch any exceptions and ensure we always return a response
        response_data = build_response(event, 'FAILED')
    
    # Respond to Cloudformation to let it know we are done
    response_url = event['ResponseURL']
    result = requests.put(response_url, data=json.dumps(response_data))

    return result