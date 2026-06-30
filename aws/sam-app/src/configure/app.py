import json
import os
import requests
import boto3
from constants import NS1_API_KEY_NAME, CS_API_KEY_NAME, ACCESS_TOKEN_NAME, REFRESH_TOKEN_NAME
from secret_handler import SecretHandler

secrets_manager_client = boto3.client('secretsmanager')
cloudformation_client = boto3.client('cloudformation')
logs_client = boto3.client('logs')
cloudtrail_client = boto3.client('cloudtrail')
s3_resource = boto3.resource('s3')

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

        elif request_type == 'Update':
            # If CreateCloudTrail is transitioning from true → false (or upgrading
            # from 0.4.3 where CreateCloudTrail did not exist and the trail was always
            # created), the stack will attempt to delete the Trail, TrailS3Bucket and
            # TrailKMSKey resources. The S3 bucket cannot be deleted by CloudFormation
            # while it still has objects in it, so we empty it and delete the trail here
            # before CloudFormation attempts resource deletion.
            # Note: OldResourceProperties will not contain CreateCloudTrail when
            # upgrading from 0.4.3 (the parameter did not exist in that version and
            # the trail was always created). Defaulting to 'true' here means the
            # upgrade path correctly detects the true→false transition and cleans up
            # the old trail and bucket. This is NOT the customer-facing default —
            # the template parameter default is 'false'.
            old_create_trail = event['OldResourceProperties'].get('CreateCloudTrail', 'true')
            # new_create_trail uses 'true' as fallback only for safety — in practice
            # this key will always be present in ResourceProperties from 0.4.4 onwards.
            new_create_trail = event['ResourceProperties'].get('CreateCloudTrail', 'true')

            if old_create_trail == 'true' and new_create_trail == 'false':
                trail_name = event['OldResourceProperties'].get('CloudTrailName', 'NS1CloudSyncTrail')

                # CloudTrailBucketName is not present in OldResourceProperties when
                # upgrading from 0.4.3 — find the bucket by its known name prefix instead.
                bucket_name = event['OldResourceProperties'].get('CloudTrailBucketName')
                if not bucket_name:
                    s3_client = boto3.client('s3')
                    buckets = s3_client.list_buckets().get('Buckets', [])
                    for b in buckets:
                        if b['Name'].startswith('cloudsync-trail-bucket-'):
                            bucket_name = b['Name']
                            break

                # stop and delete the trail so it releases the bucket.
                # Safety guard: only delete trails with names that match known
                # CloudSync-created trail names. We never delete trails that were
                # not created by this stack.
                # Known CloudSync trail names across all versions:
                #   - NS1CloudSyncTrail (default from 0.4.x)
                #   - CloudSyncTrail (used in older deployments)
                # Any other name (e.g. management-events, org trails) is skipped.
                cloudsync_trail_names = {'NS1CloudSyncTrail', 'CloudSyncTrail'}
                if trail_name in cloudsync_trail_names:
                    try:
                        cloudtrail_client.stop_logging(Name=trail_name)
                        cloudtrail_client.delete_trail(Name=trail_name)
                        print(f"Deleted CloudSync-managed trail: {trail_name}")
                    except cloudtrail_client.exceptions.TrailNotFoundException:
                        pass
                else:
                    print(f"Skipping deletion of trail not managed by CloudSync: {trail_name}")

                # empty the S3 bucket so CloudFormation can delete it
                if bucket_name:
                    bucket = s3_resource.Bucket(bucket_name)
                    bucket.objects.all().delete()

        elif request_type == 'Delete':
            # clean up secrets stored in Secrets Manager
            secret_handler.delete(NS1_API_KEY_NAME)
            secret_handler.delete(CS_API_KEY_NAME)
            secret_handler.delete(ACCESS_TOKEN_NAME)
            secret_handler.delete(REFRESH_TOKEN_NAME)

            # empty CloudTrail bucket and remove it (only if the stack created one)
            bucket_name = event['ResourceProperties'].get('CloudTrailBucketName')
            if bucket_name:
                bucket = s3_resource.Bucket(bucket_name)
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
