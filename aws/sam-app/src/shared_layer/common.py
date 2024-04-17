from typing import List
import json
import os

import requests


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


MAX_PAGE_SIZE = 100 # in terms of records

def snapshot_zone(route53_client, zone_id, zone_name, aws_account_id, endpoint, tags, max_page_size=MAX_PAGE_SIZE, marker=None):
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
        'source': 'AWS-Route53',
        'version': 1,
        'account_id': aws_account_id,
        'auth_key': retrieve_secret(os.environ['SECRET_NAME']),
        'msg_type': 'snapshot',
        'page': page_counter,
        'truncated': response['IsTruncated'],
        'num_records': len(response['ResourceRecordSets']),
        # 'zone_id': zone_id,
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

    post_response = requests.post(endpoint, data=json_payload, headers=headers)

    if post_response.status_code != 202:
        print(f"POST to {endpoint} failed with {post_response.status_code}: {post_response.content}")
        raise Exception

    ans = {}
    if response['IsTruncated']:
        ans['StartRecordName'] = response['NextRecordName']
        ans['StartRecordType'] = response['NextRecordType']
        if 'NextRecordIdentifier' in response:
            ans['StartRecordIdentifier'] = response['NextRecordIdentifier']
    ans['IsTruncated'] = response['IsTruncated']

    return ans

# TODO: Handle the case when the secret doesn't exist in Secrets Manager.
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
