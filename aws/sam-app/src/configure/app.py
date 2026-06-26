import json
import os
import requests
import boto3
from constants import NS1_API_KEY_NAME, CS_API_KEY_NAME, ACCESS_TOKEN_NAME, REFRESH_TOKEN_NAME
from secret_handler import SecretHandler

secrets_manager_client = boto3.client('secretsmanager')
cloudformation_client = boto3.client('cloudformation')
logs_client = boto3.client('logs')

# env variables
ns1_api_key = os.environ['NS1_API_KEY']
cloud_sync_api_key = os.environ['CLOUDSYNC_API_KEY']
stack_name = os.environ['STACK_NAME']

def build_response(event, status, data, reason=None):
    """A utility function used to build a response to CloudFormation"""

    response_data = {
        "Status": status,
        "Reason": reason if reason is not None else "",
        "PhysicalResourceId": event['LogicalResourceId'],
        "Data": data,
        "RequestId": event['RequestId'],
        "LogicalResourceId": event['LogicalResourceId'],
        "StackId": event['StackId'],
    }
    return response_data

def configure_application(event, context):
    if ns1_api_key is None and cloud_sync_api_key is None:
        raise Exception("an API key wasn't provided")
    
    secret_handler = SecretHandler()
    
    if ns1_api_key:
        secret_handler.upsert(NS1_API_KEY_NAME, ns1_api_key)
    elif cloud_sync_api_key:
        secret_handler.upsert(CS_API_KEY_NAME, cloud_sync_api_key)

    try:
        request_type = event['RequestType']
        if request_type == 'Create':
            # store api keys in secret manager
            if cloud_sync_api_key:
                secret_handler.upsert(CS_API_KEY_NAME, cloud_sync_api_key)
            else:
                secret_handler.upsert(NS1_API_KEY_NAME, ns1_api_key)

        elif request_type == 'Delete':
            # clean up secrets stored in Secrets Manager
            secret_handler.delete(NS1_API_KEY_NAME)
            secret_handler.delete(CS_API_KEY_NAME)
            secret_handler.delete(ACCESS_TOKEN_NAME)
            secret_handler.delete(REFRESH_TOKEN_NAME)

            # empty CloudTrail bucket and remove it (only if the stack created one)
            bucket_name = event['ResourceProperties'].get('CloudTrailBucketName')
            if bucket_name:
                s3_client = boto3.resource('s3')
                bucket = s3_client.Bucket(bucket_name)
                bucket.objects.all().delete()

            # clean up log groups
            delete_log_groups()

    except Exception as err:
        # Catch any exceptions and ensure we always return a response
        response_data = build_response(event, 'FAILED', {"foo": "bar"}, reason=str(err))
    
    else:
        response_data = build_response(event, 'SUCCESS', {"foo": "bar"})

    # Respond to Cloudformation to let it know we are done
    response_url = event['ResponseURL']
    requests.put(response_url, json=response_data)

    print(response_data)
    return {
        'statusCode': 200,
        'body': json.dumps([response_data])
    }

def delete_log_groups():
    response = cloudformation_client.describe_stack_resources(StackName=stack_name)

    # Iterate over the stack resources
    for resource in response['StackResources']: 
        if resource['ResourceType'] == 'AWS::Lambda::Function':
            try:
                response = logs_client.delete_log_group(
                    logGroupName='/aws/lambda/' + resource['PhysicalResourceId']
                )
            except logs_client.exceptions.ResourceNotFoundException:
                pass
