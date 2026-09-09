from typing import List
import json
import jwt
from datetime import datetime
import requests
import functools
import constants


class UnauthorizedException(Exception):
    """Raised when the token endpoint returns a 4xx response.

    This is a permanent failure — the API key is invalid, revoked, or the
    CloudSync entitlement has expired. SQS messages that trigger this should
    be discarded (not requeued) since retrying will never succeed.
    """
    pass


def parse_token_response(token_res, token_endpoint, context):
    try:
        tokens = token_res.json()
    except requests.exceptions.JSONDecodeError as exc:
        raise Exception(
            f"Token request returned non-JSON response during {context}. "
            f"Status: {token_res.status_code}. "
            f"Endpoint: {token_endpoint}. "
            f"Response: {token_res.text}"
        ) from exc

    if 'data' not in tokens:
        raise Exception(
            f"Token request returned unexpected JSON during {context}. "
            f"Status: {token_res.status_code}. "
            f"Endpoint: {token_endpoint}. "
            f"Response: {token_res.text}"
        )

    return tokens

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

def snapshot_zone(
    route53_client, 
    zone_id, 
    zone_name, 
    endpoint, 
    tags, 
    dest, 
    s3_bucket_name, 
    secret_handler, 
    provider_account_id=None,
    max_page_size=constants.MAX_PAGE_SIZE, 
    marker=None
):
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
        'provider_account_id': provider_account_id,
        'msg_type': 'snapshot',
        'page': page_counter,
        'truncated': response['IsTruncated'],
        'num_records': len(response['ResourceRecordSets']),
        'zone_id': zone_id,
        'zone_name': zone_name,
        'payload': {
            'resource_record_sets': response['ResourceRecordSets'],
            'tags': tags
        }
    }
    
    post_response = dns_post(endpoint, msg, secret_handler)

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
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        endpoint, _, secret_handler = args
        token_endpoint = f"{endpoint}/token"

        # attempt to use existing access token
        access_token = secret_handler.get_if_present(constants.ACCESS_TOKEN_NAME)

        if access_token:
            decoded_token = jwt.decode(access_token, options={"verify_signature": False})
            exp_time = datetime.fromtimestamp(decoded_token['exp'])
            time_to_expire = (exp_time - datetime.now()).total_seconds()

        # renewal if nearing expiry
        if not access_token or time_to_expire < constants.TOKEN_REFRESH_WINDOW:
            refresh_token = secret_handler.get_if_present(constants.REFRESH_TOKEN_NAME)
            tokens = None

            if refresh_token:
                token_res = requests.post(
                    token_endpoint,
                    headers={'Authorization': f"Bearer {refresh_token}"}
                )

                if token_res.status_code == 200:
                    try:
                        tokens = parse_token_response(
                            token_res,
                            token_endpoint,
                            "refresh-token renewal",
                        )
                    except Exception:
                        tokens = None
                elif 400 <= token_res.status_code < 500:
                    # 4xx on refresh token — permanent failure, no point trying
                    # the API key either. Raise immediately so SQS discards
                    # the message rather than requeueing it.
                    raise UnauthorizedException(
                        f"Token refresh rejected (status {token_res.status_code}) — "
                        f"CloudSync entitlement may have expired or refresh token is invalid. "
                        f"Endpoint: {token_endpoint}. "
                        f"Response: {token_res.text}"
                    )

            # if failed to renew with refresh_token, use the api_key
            if tokens is None:
                token_res = get_tokens_using_api_key(token_endpoint, secret_handler)
                tokens = parse_token_response(
                    token_res,
                    token_endpoint,
                    "api-key exchange",
                )

            # update secret manager
            secret_handler.upsert(constants.ACCESS_TOKEN_NAME, tokens['data']['access_token'])
            secret_handler.upsert(constants.REFRESH_TOKEN_NAME, tokens['data']['refresh_token'])

            access_token = tokens['data']['access_token']

        # insert token
        headers = {
            'Authorization' : f"Bearer {access_token}"
        }

        return func(*args[:-1], **kwargs, headers=headers)
    return wrapper
    

@insert_token
def dns_post(endpoint, msg, headers):
    payload = json.dumps(msg)
    headers['content-type'] = 'application/json'
    headers['content-length'] = str(len(msg))
    
    return requests.post(f"{endpoint}/dns", data=payload, headers=headers)


def get_tokens_using_api_key(token_endpoint, secret_handler):
    # get an api key
    ns1_api_key = secret_handler.get_if_present(constants.NS1_API_KEY_NAME)
    cloud_sync_api_key = secret_handler.get_if_present(constants.CS_API_KEY_NAME)

    # set api key in headers
    headers = {}
    if ns1_api_key:
        headers['x-nsone-key'] = ns1_api_key
    elif cloud_sync_api_key:
        headers['x-cloudsync-key'] = cloud_sync_api_key
    else:
        raise Exception("API keys are not set")

    # request tokens from gateway
    token_res = requests.post(token_endpoint, headers=headers)
    if token_res.status_code != 200:
        if 400 <= token_res.status_code < 500:
            # 4xx — permanent failure (expired entitlement, bad/revoked key).
            # Raise UnauthorizedException so the caller can discard the message
            # rather than returning it to the SQS queue for retry.
            raise UnauthorizedException(
                f"Token request rejected (status {token_res.status_code}) — "
                f"CloudSync entitlement may have expired or API key is invalid. "
                f"Endpoint: {token_endpoint}. "
                f"Response: {token_res.text}"
            )
        # 5xx or unexpected status — transient failure, allow SQS to retry.
        raise Exception(
            f"Token request failed (status {token_res.status_code}). "
            f"Endpoint: {token_endpoint}. "
            f"Response: {token_res.text}"
        )

    return token_res
