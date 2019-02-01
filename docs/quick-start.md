# Use Case: Polaris Account creation via Slack

This quick start provides a walkthrough of the steps needed to automate
new account creation in [Rubrik
Polaris](https://www.rubrik.com/product/polaris-overview/) with
[Slack](https://slack.com/) and
[AWS
Lambda](https://aws.amazon.com/lambda/).

## Abstract

Rubrik’s [API first
architecture](https://www.rubrik.com/product/api-integration/)
allows for integration with a wide array of tools. Slack has gained
popularity among companies embracing DevOps principles such as ChatOps
for similar reasons. Using AWS Lambda as the glue, we can provide a
simple way to provision new accounts in Rubrik Polaris via Slack. Amazon
describes Lambda as a way to “run code without thinking about servers”,
and we will use it to run Python code which interacts with Rubrik
Polaris.

## Prerequisites

* Access to all required AWS services with proper IAM permissions
* AWS CLI Tool [installed](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html) and [configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)
* Admin access to Slack
* Admin access to Rubrik Polaris

## Workflow

![image01](https://user-images.githubusercontent.com/12414122/52096977-ea6f5e00-2596-11e9-82df-a385902d88df.png)

1. A user requests a new Rubrik Polaris account via Slack Slash Command. Slack sends a JSON payload with account information to an Amazon API Gateway.
2. The JSON payload is passed to a Lambda function by the API Gateway.
3. Lamba immediately returns an HTTP 200 (Success) code to Slack to prevent a timeout.
4. A second AWS Lambda function requests the new Polaris account via REST API.
5. Polaris responds once the new account is created.
6. AWS Lambda notifies the requesting user that the account is created.

# Setup

We will begin by configuring a new application in Slack, along with a
corresponding ‘[Slash
Command](https://api.slack.com/slash-commands)’ to trigger
account creation. Slack will pass the account information and other
metadata to AWS Lambda via an [Amazon API
Gateway](https://aws.amazon.com/api-gateway/). Slack requires
that API responses are returned within three seconds, but the Polaris
account creation workflow may take slightly longer. To avoid timeout
errors, we will use two different Lambda functions along with Amazon
[SNS](https://aws.amazon.com/sns/) as a
data transport. Once AWS Lambda creates a new account in Rubrik Polaris,
a notification will be sent back to Slack. Code for the Lambda functions
is available in this [GitHub repo](https://github.com/rubrikinc/use-case-polaris-slack).

## Slack App Creation

Creating new applications in Slack and configuring slash commands is a
complex topic, and it is helpful to review the provided documentation:

* [Slack: Building Slack apps](https://api.slack.com/slack-apps)
* [Slack: Slash commands](https://api.slack.com/slash-commands)

Once you are ready to begin configuration, browse to
[Your Apps](https://api.slack.com/apps)
in the Slack API configuration page and click **Create New App**.

![image02](https://user-images.githubusercontent.com/12414122/52096978-ea6f5e00-2596-11e9-8478-3056d9831989.png)

Specify an **App Name**, choose your **Slack Workspace**, and click
**Create App**. You will be taken to the ‘Basic Information’ screen for
your new application. Scroll down to find the **Verification Token**,
and copy the value to a text editor or other scratch space. You will
submit this value to AWS KMS to be encrypted in a later step. The
encrypted token will be used during the AWS Lambda function setup.

Scroll down to the Display Information section and provide a
description, background color, and an icon if desired. There is an logo image available [here](https://github.com/rubrikinc/use-case-polaris-slack/raw/master/docs/Rubrik_logo.png). Once complete,
click **Save Changes**.

![image03](https://user-images.githubusercontent.com/12414122/52096979-ea6f5e00-2596-11e9-981f-d1691e74372c.png)

## AWS Identity and Access Management (IAM)

IAM is used to control access to resources within AWS. Two new IAM
policies will be created, and along with an AWS managed policy, they
will be used to create a new IAM role. The first new IAM role will allow
the Lambda functions to decrypt KMS encrypted data. Within the AWS
console, browse to **IAM**, click **Policies**, then **Create policy**.
On the ‘Create policy’ page, click the **JSON** tab and paste in the
JSON below.

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "kms:Decrypt"
            ],
            "Resource": "*"
        }
    ]
}
```

Click **Review policy**, and provide a name for the policy. In this
example, we’ll use `AWSLambdaKMSexecutionRole`. Click **Create Policy**,
then repeat this process to create an additional policy, using the JSON
below. This new role will allow Lambda to publish data to SNS, which is
configured in the next section. For our example we will name this second
policy `AWSLambdaSNSPublishPolicyExecutionRole`.

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sns:Publish"
            ],
            "Resource": "arn:aws:sns:*:*:*"
        }
    ]
}
```

After creating new IAM policies, click **Roles**, then **Create role**.
Click **Lambda**, then **Next: Permissions**.

![image04](https://user-images.githubusercontent.com/12414122/52096980-ea6f5e00-2596-11e9-99a6-cff4c78d54fd.png)

On the create role screen, you will search existing policies to create a
new role. One of these roles, `AWSLambdaBasicExecutionRole` is an AWS
managed policy, and the other two were created in the previous step. If
you used different names for the policies you created, search for those
instead.

Search for each of these and check the box beside the matching policy in
the search results.

* `AWSLambdaBasicExecutionRole`
* `AWSLambdaKMSExecutionRole`
* `AWSLambdaSNSPublishPolicyExecutionRole`

Once you’ve found and checked the box for each policy, click **Next:
Tags**. No tags are needed, so click **Next: Review**, and provide a
name for this new Role. For this example we’ll name the role
PolarisCreateUser. Double check the policies listed to verify they’re
correct, and click **Create role**.

![image05](https://user-images.githubusercontent.com/12414122/52096981-eb07f480-2596-11e9-84aa-7db192b004b2.png)

IAM supports granular permissions, and many organizations have strict
requirements for their security policies. The permissions and roles here
are provided as an example, but other more strict policies can be used
if needed. Be sure to have your security team approve new IAM policies
in accordance with company policy.

## AWS Key Management Service (KMS)

Before configuring Lambda, you will need to encrypt the Verification
Token from your Slack App, and your Rubrik Polaris password.

### Create a New Customer Managed Key

These steps assume you have no existing customer managed keys in KMS,
but you can use an existing key as well. Browse to **Key Management
Service** in your AWS console, click **Customer managed keys**, then
**Create key**.

![image06](https://user-images.githubusercontent.com/12414122/52096982-eb07f480-2596-11e9-97a5-1f02b12db3ff.png)

Add an alias and description, and click **Next**. For this example,
we’ll use the alias PolarisCreateUser. Click **Next** on the ‘Add
tags’ screen. On the **Define key administrative permissions screen**,
select any users that will serve as administrators or maintainers for
this workflow and click **Next**. On the **Define key usage permissions
screen**, search for the role you created in IAM in the previous section
(e.g. PolarisCreateUser). Finally, review the resulting key policy and
click **Finish**. Your new customer managed key will be listed, along
with a key ID. This ID will be used to encrypt your Slack verification
token and your Polaris password.

### Encrypt Sensitive Data Using KMS

We will use the AWS CLI tool to encrypt two values with KMS. If you have
not already
[installed](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html)
and
[configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)
the AWS CLI tool, complete those steps before continuing. Use the
following command to encrypt your Slack verification token, then your
Polaris password. Replace the text surrounded by brackets with the
information for your environment. The command will return a long string
representing your encrypted data. Save the encrypted data in a text
editor or other scratch space.

```
aws kms encrypt --key-id \[KMS Key ID\] --plaintext "\[token/password\]"
--output text --query CiphertextBlob
```

The screenshot below demonstrates this process.

![image07](https://user-images.githubusercontent.com/12414122/52096983-eb07f480-2596-11e9-8448-61d2da3754c7.png)

## Amazon Simple Notification Service (SNS)

Amazon SNS provides a way to pass data between the two Lambda functions
we will configure. An SNS topic will need to be created before
configuring Lambda. Within the AWS console, browse to **Simple
Notification Service**, then click **Topics**, and **Create new topic**.
Provide a topic name and press **Create Topic**. The new topic will be
displayed in the AWS console, along with an Amazon Resource Name (ARN).
An ARN is similar to a Fully Qualified Domain Name. It specifies a
unique resource in AWS. The ARN created for your SNS topic will be
referenced while configuring Lambda, so save it in a text editor or
other scratch space.

## AWS Lambda

Two different Lambda functions will be created, based on code in this
[GitHub repo](https://github.com/rubrikinc/polaris-slack).

### Slack Response Function

Within the AWS console, browse to **Lambda**, then click **Functions**,
then click **Create Function**. On the **Create function** page, use
values below, then click **Create function**.

* **Name:** polaris\_new\_user\_slack\_response
* **Runtime:** Python 2.7
* **Role:** Choose an existing role
* **Existing role:** PolarisCreateUser (or the name of your IAM role, if you chose a different name)

![image08](https://user-images.githubusercontent.com/12414122/52096984-eb07f480-2596-11e9-8ac4-cbe38b0d24c0.png)

You will be taken to your new Lambda function. Within the code editor,
erase the sample code and paste the contents of
[**slack\_response.py**](https://github.com/rubrikinc/use-case-polaris-slack/blob/master/slack_response.py).

![image09](https://user-images.githubusercontent.com/12414122/52096985-eb07f480-2596-11e9-889f-69af73a9d876.png)

Scroll down to **Environment variables** and create the following
variables.

| **Variable Name**     | **Value**                                                        |
| --------------------- | ---------------------------------------------------------------- |
| email\_domain         | Domain name users will be associated with (e.g. yourcompany.com) |
| kms\_encrypted\_token | Your encrypted Slack verification token                          |
| polaris\_password     | Your encrypted Rubrik Polaris password                           |
| polaris\_url          | URL of your Polaris dashboard, excluding ‘https://’              |
| polaris\_username     | Your Polaris username                                            |
| sns\_arn              | ARN of your SNS topic                                            |

Click **File** → **Save** in the code editor, then click the **Save**
button in the top right corner. In the **Designer** widget, and click
**API Gateway** in the ‘Add triggers’ list. This will bring up the
**Configure triggers** widget. In the ‘API’ dropdown, choose **Create a
new API**, and under **Security** choose **Open**, then click **Add**.
Click the **Save** button in the top right corner. Note the new API
endpoint displayed in the **API Gateway** widget. This endpoint address
will be used to configure your Slack slash command. Save the endpoint
address in a text editor or other scratch space.

![image10](https://user-images.githubusercontent.com/12414122/52096986-eb07f480-2596-11e9-85e3-d792c20a1b43.png)

### Worker Function

After completing setup for the **Slack Response** function, return to
the **Functions** page, then click **Create Function**. On the **Create
function** page, use values below, then click **Create function**.

* **Name:** polaris\_worker\_function
* **Runtime:** Python 2.7
* **Role:** Choose an existing role
* **Existing role:** PolarisCreateUser (or the name of your IAM role, if you chose a different name)

![image11](https://user-images.githubusercontent.com/12414122/52096987-eb07f480-2596-11e9-9efd-120f26ba0188.png)

You will be taken to your new Lambda function. Within the code editor,
erase the sample code and paste the contents of
[**worker\_function.py**](https://github.com/rubrikinc/use-case-polaris-slack/blob/master/worker_function.py).
Click **File** → **Save** in the code editor, then click the **Save**
button in the top right corner. In the **Designer** widget, click
**SNS** in the **Add triggers** list. This will bring up the **Configure
triggers** widget. Choose the SNS topic that you created previously,
click **Add**, then click **Save**.

## Slack Slash Command Configuration

Return to the configuration page for your Slack App and click **Slash
Commands**, then **Create New Command**.

![image12](https://user-images.githubusercontent.com/12414122/52096988-eb07f480-2596-11e9-9b40-52b36ddf2051.png)

Provide values for the slash command, using the API endpoint address
configured in the Lambda **Slack Response Function** as the **Request
URL**, and click **Save**.

![image13](https://user-images.githubusercontent.com/12414122/52096989-eb07f480-2596-11e9-8056-0027eb7b296f.png)

Click on **Install App** in the left hand menu, then click **Install App
to Workspace**. When prompted, click **Authorize** to finalize
installation of the application.

# Usage

You can use your new slash command anywhere within your Slack workspace.
Simply type

```
/polaris firstname.lastname@yourcompany.com
```

The app will notify you once the account is created, or if an error
occurs. Below is an example of the response after creating a new
account.

![image14](https://user-images.githubusercontent.com/12414122/52096990-eba08b00-2596-11e9-855d-f680704d60c6.png)

# Troubleshooting

The first troubleshooting step is to review your configuration to make
sure there are no errors. Pay special attention to Lamba environment
variables and parameters configured in Slack to verify no mistakes were
made. If you continue to encounter errors, try these steps:

*  **Check logs in Amazon CloudWatch**. Any errors encountered by Lambda functions should show up in the logs.
* **Subscribe to your SNS topic via email**. This will provide visibility into the values passed between the two Lambda functions. Within the AWS console, browse to SNS and click **Create a subscription**. Paste in the ARN of the SNS topic, change the protocol to **Email**, and provide your email address as an endpoint. You will receive an email verification message, which you will have to accept before AWS will activate the subscription. The next time you run the Slack slash command, you will receive an email with the variables passed between the Slack Response Lambda function and the Worker Lambda function. Verify that the variables match their expected values.
* **Check the audit log in Polaris**. Account creation events and related errors will be displayed in the log.

# Additional Reading

* [Slack: Building Slack apps](https://api.slack.com/slack-apps)
* [Slack: Slash commands](https://api.slack.com/slash-commands)
* [Rubrik Polaris Slack Slash Command GitHub repo](https://github.com/rubrikinc/use-case-polaris-slack)

