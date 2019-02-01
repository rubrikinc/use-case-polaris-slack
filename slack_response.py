# This script comes with no warranty use at your own risk
#
# Title: polaris_new_user_slack_response
# Author: Drew Russell - Rubrik Ranger Team
# Date: 06/15/2018
#
# Description:
#
# AWS Lambda Function used in combination with polaris_new_user_worker_function.py to create a new User for Rubrik Polaris. This script will pass all
# relevant variables to the worker function via AWS Simple Notification Service and then return a 200 code back to Slack to verify the response was received.

import boto3
import json
import logging
import os


from base64 import b64decode
from urlparse import parse_qs
from botocore.vendored import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# Encypted Passwords passed from Lambda
ENCRYPTED_EXPECTED_TOKEN = os.environ['kms_encrypted_token']
ENCRYPTED_POLARIS_PASSWORD = os.environ['polaris_password']

# AWS KMS Variables
kms = boto3.client('kms')

EXPECTED_TOKEN = kms.decrypt(CiphertextBlob=b64decode(ENCRYPTED_EXPECTED_TOKEN))['Plaintext']

# Slack Variables to pass to the worker lambda function
POLARIS_PASSWORD = kms.decrypt(CiphertextBlob=b64decode(ENCRYPTED_POLARIS_PASSWORD))['Plaintext']
POLARIS_USERNAME = os.environ['polaris_username']
POLARIS_URL = os.environ['polaris_url']
EMAIL_DOMAIN = os.environ['email_domain']
SNS_ARN = os.environ['sns_arn']


def slack_notify(err):
    """Return a response with no content to Slack"""
    return {
        'statusCode': '400' if err else '200',
        'headers': {
            'Content-Type': 'application/json',
        },
    }


def slack_notify_text(err, response=None):
    """Return a response with a text response to Slack"""
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else json.dumps(response),
        'headers': {
            'Content-Type': 'application/json',
        },
    }


def lambda_handler(event, context):
    response_body = parse_qs(event['body'])

    slack_response_url = response_body['response_url'][0]

    slack_verification_token = response_body['token'][0]

    if slack_verification_token != EXPECTED_TOKEN:
        logger.error("Request token (%s) does not match expected", slack_verification_token)
        return slack_notify(Exception('Invalid request token'))

    # Validate the user enters text after the /polaris command
    try:
        new_user_email = response_body['text'][0]
    except:
        return slack_notify_text(None, 'Please enter a valid email address after the /polaris Slash Command (ex: /polaris first.last@{}).'.format(EMAIL_DOMAIN))

    # JSON variables to pass to the worker function
    slack_variables = {}
    slack_variables['slack_response_url'] = slack_response_url

    slack_variables['polaris_username'] = POLARIS_USERNAME
    slack_variables['polaris_password'] = POLARIS_PASSWORD
    slack_variables['polaris_url'] = POLARIS_URL
    slack_variables['email_domain'] = EMAIL_DOMAIN
    slack_variables['new_user_email'] = new_user_email

    # Use AWS Simple Notification Service to trigger the helper function
    client = boto3.client('sns')
    client.publish(
        TargetArn=SNS_ARN,
        Message=json.dumps({'default': json.dumps(slack_variables)}),
        MessageStructure='json'
    )

    return slack_notify(None)
