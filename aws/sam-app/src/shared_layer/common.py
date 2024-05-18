from typing import List
import json
import os
import boto3
import jwt
from datetime import datetime
import requests

secrets_manager_client = boto3.client('secretsmanager')

class SecretHandler():
    def __init__(self):
        self.cache = {}

    def get_if_present(self, secret_id: str):
        if secret_id in self.cache:
            return self.cache.get(secret_id)
        
        try:
            res = secrets_manager_client.get_secret_value(SecretId=secret_id)
        except secrets_manager_client.exceptions.ResourceNotFoundException:
            return None

        if res['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise Exception(f"Failed to retrieve {secret_id} secret from secret manager")
        
        self.cache[ACCESS_TOKEN_NAME] = res['SecretString']
        return res['SecretString']

    def upsert(self, secret_id : str, secret_value: str, tags=[]):
        try:
            res = secrets_manager_client.update_secret(
                SecretId=secret_id,
                SecretString=secret_value
            )
        except secrets_manager_client.exceptions.ResourceNotFoundException:
            res = secrets_manager_client.create_secret(
                Name=secret_id,
                SecretString=secret_value,
                Tags=tags
            )

        if res['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise Exception(f"Failed to update {secret_id} secret on secret manager")
        
        self.cache[secret_id] = secret_value   

    def delete(self, secret_id):
        try:
            res = secrets_manager_client.delete_secret(
                SecretId=secret_id,
                ForceDeleteWithoutRecovery=True
            )

            if res['ResponseMetadata']['HTTPStatusCode'] != 200:
                raise Exception(f"Failed to delete {secret_id} secret on secret manager")

        except secrets_manager_client.exceptions.ResourceNotFoundException:
            pass

def get_tags_for_zones(route53_client, zone_ids: List[str]) -> dict:
    tags = dict()

    for chunk in (zone_ids[i:i+10] for i in range(0, len(zone_ids), 10)):
        tags_response = route53_client.list_tags_for_resources(
            ResourceType='hostedzone',
            ResourceIds=chunk,
        )

        for tag_set in tags_response['ResourceTagSets']:
            tags[tag_set['ResourceId']] = {t['Key']: t['Value'] for t in tag_set['Tags']}
    
    return tags


TOKEN_REFRESH_WINDOW = 30 # seconds 
MAX_PAGE_SIZE = 100 # in terms of records

NS1_API_KEY_NAME = 'CloudSync/NS1APIKey'
CS_API_KEY_NAME = 'CloudSync/CloudSyncAPIKey'
ACCESS_TOKEN_NAME = 'CloudSync/AccessToken'
REFRESH_TOKEN_NAME = 'CloudSync/RefreshToken'

def snapshot_zone(route53_client, zone_id, zone_name, endpoint, tags, dest, s3_bucket_name, secret_handler, max_page_size=MAX_PAGE_SIZE, marker=None):
    page_counter = 0

    kwargs = {
        'HostedZoneId': f"hostedzone/{zone_id}",
        'MaxItems': str(max_page_size)
    }

    if marker is not None:
        kwargs.update(marker)

    response = route53_client.list_resource_record_sets(**kwargs)
    page_counter += 1

    msg = {
        'source': 'route53',
        'dest': dest,
        'bucket': s3_bucket_name,
        'version': 1,
        'msg_type': 'snapshot',
        'page': page_counter,
        'truncated': response['IsTruncated'],
        'request_id': zone_id, # TODO: what value to use for fifo de-duplication?!
        'num_records': len(response['ResourceRecordSets']),
        'zone_id': zone_id,
        'zone_name': zone_name,
        'payload': {
            'resource_record_sets': response['ResourceRecordSets'],
            'tags': tags
        }
        
    }
    
    json_payload = json.dumps(msg)
    headers = {
        'content-type' : 'application/json',
        'content-length' : str(len(json_payload))
    }

    post_response = dns_post(endpoint, json_payload, headers, secret_handler)

    if post_response.status_code != 202:
        raise Exception(f"POST to {endpoint} failed with {post_response.status_code}: {post_response.content}")

    ans = {}
    if response['IsTruncated']:
        ans['StartRecordName'] = response['NextRecordName']
        ans['StartRecordType'] = response['NextRecordType']
        if 'NextRecordIdentifier' in response:
            ans['StartRecordIdentifier'] = response['NextRecordIdentifier']
    ans['IsTruncated'] = response['IsTruncated']

    return ans

def insert_token(func):
    def wrapper(*args, **kwargs):
        endpoint, _, headers, secret_handler = args

        # attempt to use existing access token
        access_token = secret_handler.get_if_present(ACCESS_TOKEN_NAME)

        if access_token:
            decoded_token = jwt.decode(access_token, options={"verify_signature": False})
            exp_time = datetime.fromtimestamp(decoded_token['exp'])
            time_to_expire = (exp_time - datetime.now()).total_seconds()

        # renewal if nearing expiry
        if not access_token or time_to_expire < TOKEN_REFRESH_WINDOW:
            refresh_token = secret_handler.get_if_present(REFRESH_TOKEN_NAME)

            if refresh_token:
                token_res = requests.post(f"{endpoint}/token", headers={'Authorization': f"Bearer {refresh_token}"})

            # if failed to renew with refresh_token, use the api_key
            if not refresh_token or token_res.status_code != 200:
                token_res = get_tokens_using_api_key(f"{endpoint}/token", secret_handler)
            tokens = token_res.json()

            # update secret manager
            secret_handler.upsert(ACCESS_TOKEN_NAME, tokens['data']['access_token'])
            secret_handler.upsert(REFRESH_TOKEN_NAME, tokens['data']['refresh_token'])

            access_token = tokens['data']['access_token']

        # insert token
        headers['Authorization'] = f"Bearer {access_token}"

        return func(*args[:-1], **kwargs)
    return wrapper
    

@insert_token
def dns_post(endpoint, payload, headers):
    return requests.post(f"{endpoint}/dns", data=payload, headers=headers)


def get_tokens_using_api_key(token_endpoint, secret_handler):
    # get an api key
    cloud_sync_api_key = secret_handler.get_if_present(CS_API_KEY_NAME)
    ns1_api_key = secret_handler.get_if_present(NS1_API_KEY_NAME)

    # set api key in headers
    headers = {}
    if cloud_sync_api_key:
        headers['x-cloudsync-key'] = cloud_sync_api_key
    elif ns1_api_key:
        headers['x-nsone-key'] = ns1_api_key
    else:
        raise Exception("API keys are not set")

    # request tokens from gateway 
    token_res = requests.post(token_endpoint, headers=headers)
    if token_res.status_code != 200:
        raise Exception(f"Failed to retrieve tokens using API Key, status code: {token_res.status_code}")

    return token_res


# TODO: Handle the case when the secret doesn't exist in Secrets Manager.
# TODO: clean up?
def retrieve_secret(secret_id): 
    url = f'http://localhost:2773/secretsmanager/get?secretId={secret_id}'
    headers = { "X-Aws-Parameters-Secrets-Token": os.environ.get('AWS_SESSION_TOKEN') }
    response = requests.get(url, headers=headers)

    # will raise an exception if not 200
    response.raise_for_status()
    response = response.json()

    print(response)

    # this key will be there unless the request fails
    return response['SecretString']
