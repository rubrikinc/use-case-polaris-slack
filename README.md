# Rubrik Polaris Slack Slash Command

Integrate Rubrik Polaris, AWS Lambda, and Slack to automate the creation of new Polaris users.

<p></p>
<p align="center">
  <img src="https://user-images.githubusercontent.com/8610203/41611198-c0fa265c-73b4-11e8-9b7b-e7311c2f86f0.png" alt="Polaris Slash Command"/>
</p>

[Slack Slash Commands](https://api.slack.com/slash-commands) require a response within 3 seconds so in order to avoid timeout errors we need to utillize two seperate Lambda functions -- a response function and a worker function.


## Response Function: `slack_response.py`

The main purpose of the `slack_response` function is to send a 200 status code back to Slack as quickly as possible in order to avoid timeout errors. The function also collects all of the relevant variables and passes those to the `worker_function` through the [Amazon Simple Notification Service (SNS)](https://aws.amazon.com/sns/).

The function will be triggered through the [Amazon API Gateway](https://aws.amazon.com/api-gateway/) that the Slash Command will initially call. The URL provided by the API Gateway will need to be populated in the `Request URL` field when creating the Slash Command.

<p></p>
<p align="center">
  <img src="https://user-images.githubusercontent.com/8610203/41612298-139901d2-73b8-11e8-9e44-e7928f0c548f.png" alt="Lambda Designer"/>
</p>

You'll also need to populate the follow Envrionment variables which will be ready by the function. The `kmsEncryptedToken`, which corresponds to the Slash Commands `Verification Token`, and the `polaris_password` will need to be encrypted.

The `sns_arn` field corresponds to the Amazon Resource Name of the SNS topic that is subscribed to the `worker_function`.


<p></p>
<p align="center">
  <img src="https://user-images.githubusercontent.com/8610203/41612299-13ae821e-73b8-11e8-9665-ca3c7b1efde2.png" alt="Environmental Variables"/>
</p>

## Worker Function: `worker_function.py`

Once the `worker_function` is triggered by Amazon SNS it will parse all of the variables sent by the `slack_response` function and then validate the information that was provide by the user through Slack. Once those checks have completed it will connect to the Rubrik Polaris account and attempt to create a new user. From there it will send a response to Slack with either a success message or relevant error message in human readable format if possible.

