# mail-forwarder-ses-imap

This repository contains an [AWS CloudFormation][awscf] template which can be
used to deploy a service to forward emails received in [Amazon SES][aws-ses] to
an IMAP server.

The template is created with [troposphere], and stacks are managed with
[sceptre].

## Usage

### Python Environment

Python is required by the tools used to manage this template. There is a script
to launch a Docker container in [`devel/env`](./devel/env), but you are free to
use any other method to prepare the Python environment (like [virtualenv]).

The tools can be installed with the following command:

    $ pip install -r requirements.txt

### Setup in AWS

The AWS account requires some configuration to be able to receive emails.
This configuration is documented in [Setting up Amazon SES email
receiving][aws-setup-ses].

An [active rule set][rule-set] it is required to be able to receive emails.

### Creating Receiver

For every address to receive emails in [Amazon SES][aws-ses] you have to create
a new stack.

1. Copy the [`mail.yaml.example`][template-example] in the
   `cloudformation/config` directory to a new file:

   ```console
   $ cd cloudformation/config

   $ cp mail.yaml.example mail-something.yaml
   ```

2. Edit the new file (`mail-something.yaml` in the previous example) and change
   the parameters with the values for your email address.

   Please check out the [documentation about resolvers][resolvers] to see
   details about how to define the parameters.

3. Use [sceptre] to create (or update) the stack.

   ```console
   $ cd cloudformation

   $ sceptre create mail-something.yaml
   ```

   To create multiple stacks at the same time you can pass the path as the
   [sceptre] argument:

   ```console
   $ sceptre create .
   ```

### Mail Limit

An alarm in created in Amazon CloudWatch to detect if a single address receives
too many emails. If the alarm is triggered, the receipt rule is disabled, and
the address does not receive any more mails.

By default, it limits 50 emails per day, but this can be modified with the
`MaxEmailsPerDay` parameter.

Once the receipt rule is disabled, it has to be enabled manually to be able to
receive emails again.




[aws-ses]: https://aws.amazon.com/ses/
[aws-setup-ses]: https://docs.aws.amazon.com/ses/latest/dg/receiving-email-setting-up.html
[awscf]: https://aws.amazon.com/cloudformation/
[resolvers]: https://docs.sceptre-project.org/3.0.0/docs/resolvers.html
[rule-set]: https://docs.aws.amazon.com/ses/latest/dg/receiving-email-concepts.html#receiving-email-concepts-rules
[sceptre]: https://github.com/Sceptre/sceptre
[template-example]: ./cloudformation/config/mail.yaml.example
[troposphere]: https://github.com/cloudtools/troposphere
[virtualenv]: https://virtualenv.pypa.io/
