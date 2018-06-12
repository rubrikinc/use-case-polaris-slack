import boto3
import json
import logging
import os


from base64 import b64decode
from urlparse import parse_qs
from botocore.vendored import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ENCRYPTED_EXPECTED_TOKEN = os.environ['kmsEncryptedToken']
ENCRYPTED_POLARIS_PASSWORD = os.environ['polaris_password']


kms = boto3.client('kms')
expected_token = kms.decrypt(CiphertextBlob=b64decode(ENCRYPTED_EXPECTED_TOKEN))['Plaintext']

POLARIS_USERNAME = os.environ['polaris_username']
POLARIS_PASSWORD = kms.decrypt(CiphertextBlob=b64decode(ENCRYPTED_POLARIS_PASSWORD))['Plaintext']
POLARIS_URL = os.environ['polaris_url']
EMAIL_DOMAIN = os.environ['email_domain']


def respond(err, res=None):
    """Return a response to Slack"""
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else json.dumps(res),
        'headers': {
            'Content-Type': 'application/json',
        },
    }


def polaris_new_user(new_user_email):
    """Connect to Polaris and create a new user """
    # New Email to add to Polaris
    new_user_email = new_user_email

    # Connect to Polaris and Get an API Token
    token_header = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    token_body = {
        "username": POLARIS_USERNAME,
        "password": POLARIS_PASSWORD
    }
    logger.info('Attempting to get Polaris Token')
    token_request = requests.post('https://{}/api/session'.format(POLARIS_URL), json=token_body, headers=token_header)

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
    new_user_request = requests.post('https://{}/api/graphql'.format(POLARIS_URL),
                                     json=query, headers=authentication_header)

    if new_user_request.status_code == 200:
        result = new_user_request.json()
        logger.info('Successfully sent the create API call.')
    else:
        logger.info('The create API call failed.')
        raise Exception("Query failed to run by returning code of {}. {}".format(new_user_request.status_code, query))

    if 'errors' in result:
        if result['errors'][0]['message'] == "ALREADY_EXISTS: cant create user as conflicts with existing one":
            return 'The email {} already exsits or has been previously invited to Polaris. See the Forgot password option at https://{} for access.'.format(new_user_email, POLARIS_URL)
        elif result['errors'][0]['message'] == "INVALID_ARGUMENT: cant create user as email address is invalid":
            return 'Please only enter a valid email address (ex: /polaris first.last@{}). You entered /polaris {}.'.format(EMAIL_DOMAIN, new_user_email)
        else:
            return result['errors'][0]['message']
    elif 'data' in result:
        return 'Sucessfully created a new account for {}.'.format(new_user_email)
    else:
        return 'An unknown error has occured.'


def lambda_handler(event, context):
    response_body = parse_qs(event['body'])

    slack_verification_token = response_body['token'][0]

    if slack_verification_token != expected_token:
        logger.error("Request token (%s) does not match expected", slack_verification_token)
        return respond(Exception('Invalid request token'))

    new_user_email = response_body['text'][0]

    try:
        email_check = new_user_email.split('@')
        if email_check[1] != EMAIL_DOMAIN:
            return respond(None, "{} is not a valid @{} email address.".format(new_user_email, EMAIL_DOMAIN))
        else:
            create_new_user = polaris_new_user(new_user_email)
            return respond(None, "%s" % (create_new_user))
    except:
        return respond(None, "{} is not a valid @{} email address.".format(new_user_email, EMAIL_DOMAIN))
