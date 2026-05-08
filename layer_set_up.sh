# get submodules
git submodule update

# Copy psycopg2 package from submodule into layer
cp -r awslambda-psycopg2/psycopg2-3.9 layer/python/lib/python3.9/site-packages/psycopg2

# pip install other packages
pip install -t layer/python/lib/python3.9/site-packages/ msgpack

# zip it
pushd layer
rm farm_data_layer.zip
zip -r farm_data_layer.zip python -x \*__pycache__* -x \*dist-info*
popd

# push layer to AWS
aws lambda publish-layer-version --layer-name farm_data_layer --compatible-runtimes python3.9 --compatible-architectures x86_64 --zip-file fileb://layer/farm_data_layer.zip --no-cli-pager

# Set the Lambda to use the layer
lambda_arn=`aws lambda list-layer-versions --layer-name farm_data_layer --query 'LayerVersions[0].LayerVersionArn' --output text`

aws lambda update-function-configuration --function-name farm_post_data --layers $lambda_arn --no-cli-pager
aws lambda update-function-configuration --function-name farm_return_details --layers $lambda_arn --no-cli-pager
aws lambda update-function-configuration --function-name farm_receiver_authenticator --layers $lambda_arn --no-cli-pager
