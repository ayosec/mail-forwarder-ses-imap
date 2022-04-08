import boto3
import imaplib
import json
import os
import time

IMAP_MAILBOX = os.environ["IMAP_MAILBOX"]
IMAP_HOST = os.environ["IMAP_HOST"]
IMAP_PORT = os.environ["IMAP_PORT"]
IMAP_USER = os.environ["IMAP_USER"]

IMAP_PASSWORD = boto3.client("ssm").get_parameter(Name = os.environ["IMAP_PASSWORD_PARAM"])["Parameter"]["Value"]

def upload_mail(bucket, key, size):
  print(f"Received {bucket}/{key} ({size} bytes)")

  # Get the data from the bucket.

  s3_object = boto3.resource("s3").Object(bucket, key)
  mail_data = s3_object.get()["Body"].read()

  # Connect to the IMAP server and append the mail. The mailbox is created if
  # it does not exist.

  imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
  imap.login(IMAP_USER, IMAP_PASSWORD)

  if imap.select(IMAP_MAILBOX)[0] != "OK":
    imap.create(IMAP_MAILBOX)

  imap.append(IMAP_MAILBOX, None, None, mail_data)

  print("Uploaded.")


def handler(event, context):
  for record in event["Records"]:
    message = json.loads(record["Sns"]["Message"])
    for record in message["Records"]:
      bucket = record["s3"]["bucket"]["name"]
      key = record["s3"]["object"]["key"]
      size = record["s3"]["object"]["size"]
      upload_mail(bucket, key, size)
