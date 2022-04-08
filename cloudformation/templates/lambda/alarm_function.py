import boto3
import os

SES_RULE_SET = os.environ["SES_RULE_SET"]
SES_RULE_NAME = os.environ["SES_RULE_NAME"]

def handler(event, context):
  print(event)

  # Get current rule configuration and replace the "Enabled" field.

  client = boto3.client("ses")

  response = client.describe_receipt_rule(
    RuleSetName = SES_RULE_SET,
    RuleName = SES_RULE_NAME
  )

  rule = response["Rule"]
  rule["Enabled"] = False

  resp = client.update_receipt_rule(
    RuleSetName = SES_RULE_SET,
    Rule = rule
  )

  print(resp)
