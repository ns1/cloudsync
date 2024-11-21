import boto3 

class SecretHandler():
    def __init__(self):
        self.client = boto3.client('secretsmanager')
        self.cache = {}

    def get_if_present(self, secret_id: str):
        if secret_id in self.cache:
            return self.cache.get(secret_id)
        
        try:
            res = self.client.get_secret_value(SecretId=secret_id)
        except self.client.exceptions.ResourceNotFoundException:
            return None

        if res['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise Exception(f"Failed to retrieve {secret_id} secret from secret manager")
        
        if len(res['SecretString']) == 0:
            raise Exception(f"{secret_id} secret has no value")

        self.cache[secret_id] = res['SecretString']
        return res['SecretString']

    def upsert(self, secret_id : str, secret_value: str, tags=[]):
        try:
            res = self.client.update_secret(
                SecretId=secret_id,
                SecretString=secret_value
            )
        except self.client.exceptions.ResourceNotFoundException:
            res = self.client.create_secret(
                Name=secret_id,
                SecretString=secret_value,
                Tags=tags
            )

        if res['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise Exception(f"Failed to update {secret_id} secret on secret manager")
        
        self.cache[secret_id] = secret_value   

    def delete(self, secret_id):
        try:
            res = self.client.delete_secret(
                SecretId=secret_id,
                ForceDeleteWithoutRecovery=True
            )

            if res['ResponseMetadata']['HTTPStatusCode'] != 200:
                raise Exception(f"Failed to delete {secret_id} secret on secret manager")

        except self.client.exceptions.ResourceNotFoundException:
            pass
