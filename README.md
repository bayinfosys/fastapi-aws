# FastAPI AWS ApiGateway Integration

This extension allows routes to contain extra information regarding AWS integrations.

The `openapi.json` export will then contain the `x-amazon-apigateway-integration` field, defining integrations to be called when the endpoint is triggered.

This specification can be uploaded to AWS APIGateway as a definition for a REST API.


## Usage

Import the `AWSAPIRouter` which uses the default `AWSAPIRoute` to define routes.
Simple use one of the following integration keywords to define the `openapi_extra` contents:
+ `aws_lambda_uri` trigger a lambda function
+ `aws_sfn_sync_arn` invoke a step-function synchronously
+ `aws_s3_object` s3 object access from apigw (TBD)
+ `mock_response` fixed apigw responses (TBD)

The keyword-argument is used to define the format of the `x-amazon-apigateway-integration` added to the `openapi_extra` parameter.


```
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from fastapi.security import HTTPBearer

from fastapi_aws import AWSAPIRouter

# Instantiate the custom router
router = AWSAPIRouter()

# Use the custom router to define routes
@router.get(
    "/user/{name}",
    aws_lambda_uri="${user_function_arn}",
    description="Get a user profile information",
    summary="Username",
    tags=["user"],
)
async def get_user_profile_information(name: str):
    return {"status": "ok", "name": "hello, world"}

@router.post(
    "/user/{name}",
    aws_lambda_uri="${user_function_arn}",
    description="Set a user profile name",
    summary="Username",
    tags=["user"],
)
async def set_user_profile(name: str):
    return {"status": "ok"}

@router.post(
    "/user-step-function",
    aws_sfn_sync_arn="${step_function_arn}",
    description="trigger a sync step function from this endpoint",
    summary="operation",
    tags=["user", "operation"]
)
async def user_post_data(user_info: UserInfoModel):
    return "goodbye"

# Create the FastAPI app and include the router
app = FastAPI()
app.include_router(router)
```


## Terraform integration

The `openapi.json` can be used to define a `REST API` in `AWS ApiGateway`.

By setting the `aws_integration_uri` to a placeholder string compatible with terraform templates,
the exported `openapi.json` file can be loaded with `templatefile`.
The template can then substitute the placeholder string with the actual lambda function arns from the terraform resources.

```terraform
resource "aws_lambda_function" "user_function" {
  # ... Lambda configuration ...
  function_name = "user-function"
  # Other configurations
}

# Create an IAM role for API Gateway to invoke Lambda functions
resource "aws_iam_role" "api_gateway_role" {
  name = "api-gateway-lambda-invoke-role"

  assume_role_policy = jsonencode({
    "Version": "2012-10-17",
    "Statement": [{
      "Action": "sts:AssumeRole",
      "Effect": "Allow",
      "Principal": {
        "Service": "apigateway.amazonaws.com"
      }
    }]
  })
}

# Attach policy to allow invocation of Lambda functions
resource "aws_iam_role_policy" "api_gateway_policy" {
  name = "api-gateway-lambda-invoke-policy"
  role = aws_iam_role.api_gateway_role.id

  policy = jsonencode({
    "Version": "2012-10-17",
    "Statement": [{
      "Action": "lambda:InvokeFunction",
      "Effect": "Allow",
      "Resource": aws_lambda_function.user_function.arn
    }]
  })
}

# Load the OpenAPI specification and replace placeholders
data "template_file" "openapi_spec" {
  template = file("${path.module}/openapi.json")

  vars = {
    user_function_arn           = aws_lambda_function.user_function.arn
    lambda_invoke_iam_role_arn  = aws_iam_role.api_gateway_role.arn
  }
}

# Create the API Gateway REST API using the OpenAPI specification
resource "aws_api_gateway_rest_api" "api" {
  name = "My API"

  body = data.template_file.openapi_spec.rendered
}

# Deploy the API
resource "aws_api_gateway_deployment" "api_deployment" {
  depends_on = [aws_api_gateway_rest_api.api]
  rest_api_id = aws_api_gateway_rest_api.api.id
  stage_name = "prod"
}
```
