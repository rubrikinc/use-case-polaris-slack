# This script comes with no warranty use at your own risk
#
# Title: polaris_new_user_slack_response
# Author: Drew Russell - Rubrik Ranger Team
# Date: 06/15/2018
#
# Description:
#
# AWS Lambda Function used in combination with polaris_new_user_slack_response.py to create a new User for Rubrik Polaris. This script will pass validate the
# information passed through the /polaris slash command and then create a new user in the Polaris account. It will then send a response to slack through
# the response_url variable to let the user know of any errors or success

import boto3
import json
import logging
import os
from base64 import b64decode
from botocore.vendored import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def polaris_new_user(new_user_email, polaris_username, polaris_password, polaris_url, email_domain):
    """Connect to Polaris and create a new user """
    # New Email to add to Polaris
    new_user_email = new_user_email

    # Connect to Polaris and Get an API Token
    token_header = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    token_body = {
        "username": polaris_username,
        "password": polaris_password
    }
    logger.info('Attempting to get Polaris Token')
    token_request = requests.post('https://{}/api/session'.format(polaris_url), json=token_body, headers=token_header)

    if token_request.status_code == 200:
        result = token_request.json()
        access_token = result['access_token']
        logger.info('Successfully received the Polaris Token')
    else:
        logger.info('Failed to get Polaris Token')
        raise Exception("Query failed to run by returning code of {}. {}".format(token_request.status_code, token_body))

    # Creat a New User
    authentication_header = {"authorization": "Bearer {}".format(access_token)}

    query = {"operationName": "CreateUser", "variables": {"email": new_user_email},
             "query": "mutation CreateUser($email: String!) {\n  createUser(email: $email)\n}\n"}

    logger.info('Creating new user.')
    new_user_request = requests.post('https://{}/api/graphql'.format(polaris_url),
                                     json=query, headers=authentication_header)

    if new_user_request.status_code == 200:
        result = new_user_request.json()
        logger.info('Successfully sent the create API call.')
    else:
        logger.info('The create API call failed.')
        raise Exception("Query failed to run by returning code of {}. {}".format(new_user_request.status_code, query))

    if 'errors' in result:
        if result['errors'][0]['message'] == "ALREADY_EXISTS: cant create user as conflicts with existing one":
            return 'The email {} already exists or has been previously invited to Polaris. See the Forgot password option at https://{} for access.'.format(new_user_email, polaris_url)
        elif result['errors'][0]['message'] == "INVALID_ARGUMENT: cant create user as email address is invalid":
            return 'Please only enter a valid email address (ex: /polaris first.last@{}). You entered /polaris {}.'.format(email_domain, new_user_email)
        else:
            return result['errors'][0]['message']
    elif 'data' in result:
        return 'Sucessfully created a new account for {}.'.format(new_user_email)
    else:
        return 'An unknown error has occured.'


def slack_notify(slack_response_url, response):

    payload = {'statusCode': '200',
               'Content-Type': 'application/json',
               'text': response}

    requests.post(slack_response_url, data=json.dumps(payload))

    """Return a response with no content to Slack"""


def lambda_handler(event, context):

    response_body = json.loads(event['Records'][0]['Sns']['Message'])

    slack_response_url = response_body['slack_response_url']

    polaris_username = response_body['polaris_username']
    polaris_password = response_body['polaris_password']
    polaris_url = response_body['polaris_url']
    email_domain = response_body['email_domain']
    new_user_email = response_body['new_user_email']

    try:
        email_check = new_user_email.split('@')
        if email_check[1] != email_domain:
            return slack_notify(slack_response_url, "{} is not a valid @{} email address.".format(new_user_email, email_domain))
        else:
            create_new_user = polaris_new_user(new_user_email, polaris_username,
                                               polaris_password, polaris_url, email_domain)

            return slack_notify(slack_response_url, '{}'.format(create_new_user))
    except:
        return slack_notify(slack_response_url, "{} is not a valid @{} email address.".format(new_user_email, email_domain))
