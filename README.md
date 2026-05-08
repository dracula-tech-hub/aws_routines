# aws_routines

Implementation of all AWS Lambda functions

## Install dependencies of each lambda
In the lambda folder:
```
pip3 install --target ./app/.dependencies --system -r app/requirements.txt
```

## Uploading Lambda functions to AWS
The source code is uploaded to AWS from a remote computer.

### Configure AWS CLI
```
cd /tmp
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
aws configure  # and then enter the necessary information
```

### Use AWS CLI to upload the code
Each lambda function is within one folder, which has the same name as the function.
The following commands need to be run in this folder.

```
# Create the zip package
rm lambda.zip  # (optional)
cd app/.dependencies
zip -r9 ../../lambda.zip .
cd ../..
zip -g lambda.zip -r app/ -x \*__pycache__* -x \*.dependencies*

# Upload the zip to AWS
aws lambda update-function-code --function-name ${PWD##*/} --zip-file fileb://lambda.zip

```

or in short:
```
./upload_to_aws.sh
```
test
