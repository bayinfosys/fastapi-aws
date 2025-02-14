# FastAPI AWS ApiGateway Integration

This extension enables routes to be defined in FastAPI with extra decorator parameters for AWS integrations.

The exported `private_openapi.json` will then contain integrations for:
+ `AWS Lambda function`
+ `AWS Step function`
+ `AWS S3 bucket`

Secured via:
+ `AWS Cognito User Pools`
+ `AWS Lambda Authorizer`

This specification can be uploaded to AWS APIGateway as a definition for a REST API (see below for automatation with terraform). CORS definitions for routes are also auto-generated.

This allows your AWS APIGateway REST API to be defined in python, reference pydantic models, integrated into your application code, etc.

A `public_openapi.json` is also produced which can be presented to swagger and other tools for use in documentation.


## Usage

### Endpoints

Import the `AWSAPIRouter` which uses the default `AWSAPIRoute` to define routes.
Simply use one of the following integration keywords to define the `openapi_extra` contents:
+ `aws_lambda_uri` trigger a lambda function
+ `aws_sfn_sync_arn` invoke a step-function synchronously
+ `aws_s3_bucket` s3 object access from apigw
+ `mock_response` fixed apigw responses (TBD)
+ `dynamodb` dynamodb queries via apigw endpoints (TBD)

The keyword-argument is used to define the format of the `x-amazon-apigateway-integration` added to the `openapi_extra` parameter.

**NOTE**: the default `FastAPI.router` should be replaced with a new `AWSAPIRouter` **before** adding any routes. If routes are added to the router, and the `app.include_router(aws_router)` is called, the `app.include_router` method will fail to pass the aws kwargs and cause the `AWSAPIRoute` to throw a `ValueError`. This is due to FastAPI sanitizing the kwargs to routes.


```python
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from fastapi.security import HTTPBearer

from fastapi_aws import AWSAPIRouter

# Instantiate the custom router
router = AWSAPIRouter()

# Create the FastAPI app and include the router
# NB: the router must be overridden **before** creating any routes
app = FastAPI()
app.router = router
# app.include_router(router) will cause the @router.get decorator to fail to add routes correctly

# Use the custom router to define routes so we can use the .get, .post, etc methods
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
```

### Authorization

`fastapi_aws.authorizers` exports a number of authorizers which can be added to endpoints for security.

These classes will also export the correct AWS integrations to build and associate authorizers with API Gateway endpoints.

+ `CognitoAuthorizer` enables AWS Cognito user pool authorization,
+ `LambdaAuthorizer` enables custom AWS Lambda function authorizers.

Both classes export the authorizers in the openapi spec, so an authorizer should **NOT** be provisioned in infrastructure.

To add custom header fields for the authorizers use the `header_names` parameter.

```python
from fastapi import Security
from fastapi_aws import AWSAPIRouter, LambdaAuthorizer

bearer_auth = LambdaAuthorizer(
    authorizer_name="${bearer_authorizer_name}",
    aws_lambda_uri="${lambda_authorizer_uri}",
    aws_iam_role_arn="${lambda_authorizer_iam_role_arn}",
    header_names=["Authorization", "x-api-key"]
)

router = AWSAPIRouter()

@router.get(
    "/user/{name}",
    aws_lambda_uri="${user_function_arn}",
    description="Get a user profile information",
    summary="Username",
    tags=["user"],
)
async def get_user_profile_information(name: str, username=Security(bearer_auth)):
    return {"status": "ok", "name": "hello, world"}
```

In the above example, the `/user/{name}` endpoint will only succeed if the correct credentials are provided in either the `Authorization` or `x-api-key` header fields.

**NB**: the assignment `user=Security...` is required to ensure export to OpenAPI.

## Export OpenAPI specification

The module will create an OpenAPI spec from a routes file, and output two specifications:
1. A private OpenAPI spec with the (optional) CORS definitions and `x-amazon-apigateway-integration` definitions for consumption by AWS ApiGateway REST API, and
2. A public OpenAPI spec which can be presented for public consumption via swagger documentation etc.

NB: the python code for these endpoints will not be executed in anyway, they are purely descriptive.

Given a `my-routes.py`:
```python
from pydantic import BaseModel
from fastapi import Security

from fastapi_aws import AWSAPIRouter, LambdaAuthorizer


class UserRequest(BaseModel):
    username: str


class UserResponse(BaseModel):
    username: str


class UserPublicResponse(BaseModel):
    username: str


lambda_auth = LambdaAuthorizer(
    authorizer_name="${lambda_authorizer_name}",
    aws_lambda_uri="${lambda_authorizer_uri}",
    aws_iam_role_arn="${lambda_authorizer_iam_role_arn}",
)

router = AWSAPIRouter()

@router.post(
    "/user",
    description="post some user information",
    response_model=UserResponse,
    aws_lambda_uri="${polling_start_lambda_arn}",
    aws_iam_arn="${polling_start_lambda_iam_role_arn}",
    tags=["users"],
)
async def user(body: UserRequest, user=Security(lambda_auth)):
    return UserResponse()


@router.get(
    "/public/user",
    description="retrieve public user information",
    response_model=UserPublicResponse,
    aws_lambda_uri="${user_public_data_lambda_arn}",
    aws_iam_arn="${user_public_data_lambda_iam_role_arn}",
    tags=["users"],
)
async def fetch_user_info():
    return UserPublicResponse()
```


These specifications are created from the module via:
```bash
fastapi_aws \
  --title my-api \
  --router my-routes.py \
  --out-public ./api_public.json \
  --out-private ./api_private.json \
  --version 0.0.1
```

or via the docker image with:
```bash
docker run -it --rm \
  -v $(shell pwd)/my-api:/app/routes:ro \
  -v $(shell pwd)/terraform/rest-definition:/out \
  fastapi_aws \
    --title my-api \
    --router routes.routes:router \
    --out-public /out/api_public_definition.json \
    --out-private /out/api_private_definition.json \
    --version 0.0.1
```


## Terraform integration

The `openapi.json` can be used to define a `REST API` in `AWS ApiGateway`.

By setting the `aws_integration_uri` to a placeholder string compatible with terraform templates,
the exported `openapi.json` file can be loaded with `templatefile`.
The template can then substitute the placeholder string with the actual lambda function arns from the terraform resources.

```terraform
# Define a lambda function which we want to invoke from the API endpoint
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

## Example

The following `Makefile` produces the openapi specs during a CICD process with:

```makefile
APP_NAME=Example-App
GIT_TAG=$(shell git describe --tags)

build/api-definition:
  docker run -it --rm \
    -v $(shell pwd)/package/src/api:/app/routes:ro \
    -v $(shell pwd)/terraform/rest:/out \
    fastapi_aws \
      --title $(APP_NAME) \
      --router routes.routes:router \
      --out-public /out/api_public_definition.json \
      --out-private /out/api_private_definition.json \
      --version $(GIT_TAG)

build/infrastructure:
  terraform init
  terraform plan -out new.plan
  terraform apply && rm new.plan
```