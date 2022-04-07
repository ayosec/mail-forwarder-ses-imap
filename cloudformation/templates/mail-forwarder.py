from pathlib import Path
from troposphere import Parameter, Template, Ref, GetAtt, Join, Sub
from troposphere import awslambda, iam, s3, ses, sns, ssm

S3_OBJECTS_PREFIX = "ses/emails"

def resource(res):
  """
  Decorator to assign a method to define a resource in the template.

  If the method is called multiple times, it always returns the same value.
  """

  def inner(f):
    added = []
    def wrapper(self):
      if len(added) == 0:
        added.append(self.template.add_resource(res))
        f(self, res)
      return added[0]

    return wrapper
  return inner



class MailForwarder:
  def __init__(self):
    self.template = Template()

    self.ephemeral_bucket = self.template.add_parameter(
        Parameter("BucketName", Type = "String"))

  @resource(s3.Bucket("EphemeralStorageBucket"))
  def s3_bucket(self, bucket):
    """
    Bucket in S3 to store received emails.
    """

    t = self.template

    exp_days = t.add_parameter(Parameter("MailsExpirationInDays",
      Type = "Number",
      Default = 90,
    ))

    bucket.DependsOn = self.sns_topic_policy()
    bucket.BucketName = Ref(self.ephemeral_bucket)

    bucket.LifecycleConfiguration = s3.LifecycleConfiguration(
      Rules = [
        s3.LifecycleRule(
          Status = "Enabled",
          ExpirationInDays = Ref(exp_days)
        )
      ]
    )

    bucket.NotificationConfiguration = s3.NotificationConfiguration(
      TopicConfigurations = [
        s3.TopicConfigurations(
          Event = "s3:ObjectCreated:*",
          Topic = Ref(self.sns_topic()),
          Filter = s3.Filter(
            S3Key = s3.S3Key(Rules = [ s3.Rules(Name = "prefix", Value = S3_OBJECTS_PREFIX) ])
          )
        )
      ]
    )


  @resource(s3.BucketPolicy("EphemeralStoragePolicy"))
  def s3_bucket_policy(self, policy):
    bucket = self.s3_bucket()
    policy.Bucket = Ref(bucket)
    policy.PolicyDocument = {
      "Version": "2012-10-17",
      "Statement": {
        "Sid": "AllowSESPutObject",
        "Effect": "Allow",
        "Principal": { "Service": "ses.amazonaws.com" },
        "Action": "s3:PutObject",
        "Resource": Sub("arn:aws:s3:::${%s}/%s*" % (self.ephemeral_bucket.title, S3_OBJECTS_PREFIX)),
        "Condition": {
          "StringEquals": { "aws:Referer": Ref("AWS::AccountId") }
        }
      }
    }


  @resource(sns.Topic("NewMailsSNSTopic"))
  def sns_topic(self, topic):
    """
    SNS topic to notify new objects in the S3 bucket to the Lambda function.
    """

    t = self.template

    t.add_resource(sns.SubscriptionResource("NewMailsSubscription",
      TopicArn = Ref(topic),
      Protocol = "lambda",
      Endpoint = GetAtt(self.lambda_function(), "Arn")
    ))


  @resource(sns.TopicPolicy("NewMailsSNSPolicy"))
  def sns_topic_policy(self, policy):
    policy.Topics = [ Ref(self.sns_topic()) ]
    policy.PolicyDocument = {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": { "AWS": "*" },
          "Action": [ "sns:publish" ],
          "Resource": Ref(self.sns_topic()),
          "Condition": {
            "ArnLike": { "aws:SourceArn": Join("", [ "arn:aws:s3:::", Ref(self.ephemeral_bucket) ]) }
          }
        }
      ]
    }


  @resource(awslambda.Function("UploaderFunction"))
  def lambda_function(self, function):
    """Lambda function to upload emails to an IMAP server."""

    t = self.template

    # Parameters

    ImapHost = t.add_parameter(Parameter("ImapHost", Type = "String"))

    ImapPort = t.add_parameter(Parameter("ImapPort",
      Type = "Number",
      Default = 993,
      MinValue = 1,
      MaxValue = 65535
    ))

    ImapMailbox = t.add_parameter(Parameter("ImapMailbox", Type = "String", Default = "Inbox"))

    ImapUser = t.add_parameter(Parameter("ImapUser", Type = "String"))

    ImapPassword = t.add_parameter(Parameter("ImapPassword", Type = "String", NoEcho = True))

    password_param = t.add_resource(ssm.Parameter("ImapPasswordParam",
      Tier = "Standard",
      Type = "String",
      Value = Ref(ImapPassword)
    ))

    # IAM role for the function

    role = t.add_resource(iam.Role("UploaderFunctionRole"))

    role.AssumeRolePolicyDocument = {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Action": "sts:AssumeRole",
          "Effect": "Allow",
          "Principal": { "Service": [ "lambda.amazonaws.com" ] }
        }
      ]
    }

    role.Policies = [
      iam.Policy(
        PolicyName = "LambdaFunctionAccess",
        PolicyDocument = {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Sid": "LambdaLogs",
              "Effect": "Allow",
              "Resource": Sub("arn:aws:logs:${AWS::Region}:*"),
              "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
              ]
            }, {
              "Sid": "EmailReader",
              "Effect": "Allow",
              "Action": [ "s3:GetObject" ],
              "Resource": Join("", [ GetAtt(self.s3_bucket(), "Arn"), "/", S3_OBJECTS_PREFIX, "/*" ]),
            }
          ]
        }
      )
    ]

    # Function instance

    function.Role = GetAtt(role, "Arn")

    code = Path(__file__).parent.joinpath("lambda/forwarder.py").read_text()

    function.Code = awslambda.Code(ZipFile = code)
    function.Runtime = "python3.9"
    function.Handler = "index.handler"
    function.Timeout = 60
    function.MemorySize = 256
    function.Architectures = [ "arm64" ]

    function.Environment = awslambda.Environment(
      Variables = {
        "IMAP_USER": Ref(ImapUser),
        "IMAP_HOST": Ref(ImapHost),
        "IMAP_PORT": Ref(ImapPort),
        "IMAP_MAILBOX": Ref(ImapMailbox),
        "S3_BUCKET": Ref(self.s3_bucket()),
        "S3_PREFIX": S3_OBJECTS_PREFIX
      }
    )

    t.add_resource(awslambda.Permission("SnsToLambdaPermission",
      FunctionName = Ref(function),
      Action = "lambda:InvokeFunction",
      Principal = "sns.amazonaws.com",
      SourceArn = Ref(self.sns_topic())
    ))

  @resource(ses.ReceiptRule("MailSESRule"))
  def ses_rule(self, rule):
    """
    Configuration in SES to receive an email and store it in a S3 bucket.
    """

    t = self.template

    recipient = t.add_parameter(Parameter("Recipient", Type = "String"))
    rule_set_name = t.add_parameter(Parameter("SesRuleSetName", Type = "String"))

    rule.DependsOn = self.s3_bucket_policy()
    rule.RuleSetName = Ref(rule_set_name)

    rule.Rule = ses.Rule(
        Enabled = True,
        ScanEnabled = True,
        Recipients = [ Ref(recipient) ],
        Actions = [
          ses.Action(
            S3Action = ses.S3Action(
              BucketName = Ref(self.ephemeral_bucket),
              ObjectKeyPrefix = S3_OBJECTS_PREFIX
            ))
        ]
    )

  def generate(self):
    """
    Main method to generate the final template.
    """

    self.lambda_function()
    self.s3_bucket()
    self.ses_rule()
    self.sns_topic()
    self.sns_topic_policy()

    return self.template


def sceptre_handler(user_data):
  template = MailForwarder().generate()
  return template.to_yaml()