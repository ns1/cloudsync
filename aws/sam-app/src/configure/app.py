import json
import os
import requests
import boto3

# TODO:
# - Clean up logs in CloudWatch on delete

secrets_manager_client = boto3.client('secretsmanager')

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
    try:
        request_type = event['RequestType']

        if request_type == 'Create':
            _ = secrets_manager_client.create_secret(
                Name=os.environ['SECRET_NAME'],
                SecretString=os.environ['API_KEY'],
                Tags=[
                    {
                        'Key': 'APIKey',
                        'Value': 'NS1'
                    }
                ]
            )

        elif request_type == 'Delete':
            # delete the API key stored in Secrets Manager
            _ = secrets_manager_client.delete_secret(
                SecretId=os.environ['SECRET_NAME'],
                ForceDeleteWithoutRecovery=True
            )

            # empty CloudTrail bucket and remove it
            bucket = event['ResourceProperties']['CloudTrailBucketName']
            s3 = boto3.resource('s3')
            bucket = s3.Bucket(bucket)
            for obj in bucket.objects.filter():
                s3.Object(bucket.name, obj.key).delete()

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
