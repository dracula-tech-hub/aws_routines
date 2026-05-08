# Create the zip package
rm lambda.zip
zip -r lambda.zip app/ -x \*__pycache__*

# Upload the zip to AWS
aws lambda update-function-code --function-name ${PWD##*/} --zip-file fileb://lambda.zip --no-cli-pager
