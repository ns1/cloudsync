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

.PHONY: push-lambda-func
push-lambda-func: checks
push-lambda-func:
	@zip -r ./cloudsync-lambda.zip . -i ./app.py && \
	aws s3 cp ./cloudsync-lambda.zip s3://${BUCKET}/cloudsync-lambda.zip --profile ${PROFILE} && \
	rm ./cloudsync-lambda.zip
