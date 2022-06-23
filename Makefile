SHELL := /bin/bash
BUCKET := cloudsync-v2-lambda
PROFILE := dev-ns1dhcpipam

.PHONY: check-aws-cli
check-aws-cli:
	@if ! which aws > /dev/null; then \
	  echo "aws cli not installed"; \
	fi

.PHONY: checks
checks: check-aws-cli

.PHONY: update-lambda
update-lambda: check-aws-cli
	@aws lambda update-function-code --function-name r53cloudsync-LambdaFunctionRoute53-yv9toPYNmtlH --s3-bucket ${BUCKET} --s3-key cloudsync-lambda.zip --profile ${PROFILE}

.PHONY: update-layer
update-layer: check-aws-cli
	@aws lambda publish-layer-version --layer-name LambdaFunctionRequestsLayer --content S3Bucket=${BUCKET},S3Key=layer.zip --compatible-runtimes python3.9 --profile ${PROFILE}

.PHONY: push-lambda-func
push-lambda-func: checks
push-lambda-func:
	@zip -r ./cloudsync-lambda.zip . -i ./aws/lambda/app.py && \
	aws s3 cp ./cloudsync-lambda.zip s3://${BUCKET}/cloudsync-lambda.zip --profile ${PROFILE} && \
	rm ./cloudsync-lambda.zip

.PHONY: gen-layer
gen-layer:
	@mkdir ./aws/lambda_layer/python
	pip install -q -r ./aws/lambda_layer/requirements.txt -t ./aws/lambda_layer/python


.PHONY: push-lambda-layer
push-layer: checks gen-layer
push-layer:
	@zip -r layer.zip ./python && \
	rm -rf ./python && \
	aws s3 cp layer.zip s3://${BUCKET}/layer.zip --profile ${PROFILE} && \
	rm layer.zip && \

.PHONY: push-lambda
push-lambda: push-lambda-func push-lambda-layer

# For extending makefile in each
# TODO maybe this can be generic as well
-include build.makefile
