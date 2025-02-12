from typing import Any, Dict, List
import json


from .route import register_integration


@register_integration("mock")
def mock_integration(
    uri: str, iam_arn: str, path_parameters: List[str], **kwargs
) -> Dict[str, Any]:
    """returns a mock integration which has a fixed response value
    NB: this function should take parameters for the fixed responses.
    NB: this can currently be used for a 'not implemented' response.
    """
    return dict(
        uri="",
        integration_type="mock",
        request_template={"statusCode": 200},
        responses={
            "default": {
                "statusCode": 501,
                "responseTemplates": {
                    "application/json": '{"status": "not implemented"}'
                },
            }
        },
    )


@register_integration("aws_lambda_uri")
def lambda_integration(
    uri: str, iam_arn: str, path_parameters: List[str] = None, **kwargs
) -> Dict[str, Any]:
    """returns an aws integration description for calling lambdas from apigw.
    NB: this return value includes strings relating to resource arns in terraform,
        so the apigw deployment must load this function output and replace these placeholders.
    The return value should look like:
        "x-amazon-apigateway-integration": {
            "uri": "${lambda_function_arn}",
            "httpMethod": "POST",
            "type": "aws",
            "credentials": "${lambda_function_iam_arn}",
            "requestTemplates": {
                "application/json": json.dumps({
                    "body": "$input.json('$')",
                    "httpMethod": "POST",
                    "resource": "/",
                    "path": "/"
                })
            }
        }
      There is also a "responses" key which we should set to reformat the output, but do not yet.
      The optional "path_parameters" parameter is a list of variable path elements
      which are added to the requestTemplate:
        "application/json": json.dumps({
            "body": "$input.json('$')",
            "httpMethod": "POST",
            "resource": "/",
            "path": "/"
            "pathParameters": {...}
        })
      MB: the format of this pathParameters string is important, see the code for details
    """
    request_template = {
        "body": "$input.json('$')",
        "httpMethod": "$context.httpMethod",
        "resource": "$context.resourcePath",
        "path": "$context.path",
    }

    if path_parameters:
        if not isinstance(path_parameters, list):
            raise ValueError("path_parameters must be a list of strings")

        request_template.update(
            {
                "pathParameters": {
                    name: f"$input.params('{name}')" for name in path_parameters
                }
            }
        )

    response_template = {"default": {"statusCode": "200"}}

    return dict(
        uri=uri,
        integration_type="aws",
        credentials=iam_arn,
        request_template=request_template,
        response_template=response_template,
    )


def step_function_integration_base(
    uri: str,
    sfn_arn: str,
    iam_arn: str,
    mapping_template: Dict[str, str],
) -> Dict[str, Any]:
    """returns an aws integration for sync invocation of a step function from apigw.

    NB: the input to the step function is always the json serialized body object.
        we not **not** pass through any path parameters at the moment.

    NB: this return value includes strings relating to resource arns in terraform,
        so the apigw deployment must load this function output and replace these placeholders.

    The return value should look like:
        "x-amazon-apigateway-integration": {
            "uri": "arn:aws:apigateway:${region}:states:action/StartSyncExecution",
            "httpMethod": "POST",
            "type": "aws",
            "credentials": "${sfn_invoke_iam_role_arn}",
            "requestTemplates": {
                "application/json": json.dumps({
                    "input": "$util.escapeJavaScript($input.json(\'$\'))",
                    "stateMachineArn": "${step_function_arn}",
                    "region": "${region}"
                })
            },
            "responses": {
                "default": {
                    "statusCode": "200",
                    "responseTemplates": {
                        "application/json": "#set($output = $util.parseJson($input.path('$.output')))\n$output.body"
                    },
                }
            },
        }
    },
    NB: the format of this pathParameters string is important, see the code for details
    """
    if mapping_template is None:
        mapping_template = "$input.json('$')"
    elif isinstance(mapping_template, dict):
        mapping_template = json.dumps(mapping_template)

    request_template = {
        "input": mapping_template,
        "stateMachineArn": sfn_arn,
        "region": "${region}",
    }

    # FIXME: take response templates as parameters so we can handle errors nicely.
    response_template = {
        "default": {
            "statusCode": "200",
            "responseTemplates": {
                "application/json": "#set($output = $util.parseJson($input.path('$.output')))\n$output.body"
            },
        }
    }

    return dict(
        uri=uri,
        integration_type="aws",
        credentials=iam_arn,
        request_template=request_template,
        response_template=response_template,
    )


@register_integration("aws_sfn_sync_arn")
def step_function_sync_integration(
    sfn_arn: str,
    iam_arn: str,
    path_parameters: List[str] = None,
    mapping_template: dict = None,
    **kwargs,
) -> Dict[str, Any]:
    """returns an aws integration for sync invocation of a step function from apigw."""

    return step_function_integration_base(
        "arn:aws:apigateway:${region}:states:action/StartSyncExecution",
        sfn_arn,
        iam_arn,
        mapping_template,
    )


@register_integration("aws_sfn_arn")
def step_function_integration(
    sfn_arn: str,
    iam_arn: str,
    path_parameters: List[str] = None,
    mapping_template: dict = None,
    **kwargs,
) -> Dict[str, Any]:
    return step_function_integration_base(
        "arn:aws:apigateway:${region}:states:action/StartExecution",
        sfn_arn,
        iam_arn,
        mapping_template,
    )


@register_integration("aws_s3_bucket")
def s3_integration(
    bucket_name: str,
    iam_arn: str,
    path_parameters: List[str] = None,
    http_method: str = "GET",
    object_key: str = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Returns an AWS integration for S3 from API Gateway.

    This allows API Gateway to interact with S3 objects via HTTP methods.

    :param bucket_name: Name of the S3 bucket.
    :param iam_arn: IAM role ARN to assume for the integration.
    :param path_parameters: List of parameters in the API Gateway request path.
    :param http_method: HTTP method (GET, PUT, DELETE) to use for the integration.

    # TODO: how should we pass the object key? hardcoded or path parameters are both sensible

    Example OpenAPI integration:

    "x-amazon-apigateway-integration": {
        "uri": "arn:aws:apigateway:${region}:s3:path/{bucket}/{key}",
        "httpMethod": "GET",
        "type": "aws",
        "credentials": "${iam_role_arn}",
        "requestParameters": {
            "integration.request.path.bucket": "method.request.path.bucket",
            "integration.request.path.key": "method.request.path.key"
        },
        "responses": {
            "default": {
                "statusCode": "200"
            }
        }
    }
    """
    assert http_method in (
        "GET",
        "PUT",
        "DELETE",
    ), "Invalid HTTP method for S3 integration"

    # define the S3 integration URI using API Gateway's S3 service
    # uri = f"arn:aws:apigateway:${{region}}:s3:path/{bucket_name}/{{key}}"
    # FIXME: add the key parameter here to specify an object; but where should the value coem from?
    #        path_parameters? kwargs?
    uri = f"arn:aws:apigateway:${{region}}:s3:path/{bucket_name}"

    if object_key:
        uri = "/".join((uri, object_key))
    elif path_parameters:
        uri = "/".join([uri] + path_parameters)
    else:
        raise ValueError("expected one of: 'object_key', 'path_parameters'")

    # apigw request parameters mapping
    request_parameters = kwargs.get("request_parameters") or {
        "integration.request.path.bucket": "method.request.path.bucket",
        "integration.request.path.key": "method.request.path.key",
    }

    # response mapping (simple passthrough)
    response_template = kwargs.get("response_template") or {"default": {"statusCode": "200"}}

    # generate apigw integration config
    return dict(
        uri=uri,
        http_method=http_method,
        integration_type="aws",
        credentials=iam_arn,
        request_template=request_parameters,
        response_template=response_template,
    )
