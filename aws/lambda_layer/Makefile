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

.PHONY: gen-layer
gen-layer:
	@mkdir ./python && \
	pip install -q -r ./requirements.txt -t ./python

.PHONY: push-lambda-layer
push-lambda-layer: checks gen-layer
push-lambda-layer:
	@zip -r layer.zip ./python && \
	rm -rf ./python && \
	aws s3 cp layer.zip s3://${BUCKET}/layer.zip --profile ${PROFILE} && \
	rm layer.zip
	