import logging

from typing import Any, Dict, List
import json


from .route import register_integration


logger = logging.getLogger(__name__)


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
                    "application/json": json.dumps({"status": "not implemented"})
                },
            }
        },
    )


@register_integration("aws_lambda_uri")
def lambda_integration(
    uri: str,
    iam_arn: str,
    integration_type="aws_proxy",
    path_parameters: List[str] = None,
    request_template: str = None,
    responses_template: str = None,
    **kwargs,
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

    NB: if `integration_type` is `aws_proxy` the lambda must return cors headers directly.
    NB: use "type": "aws" to pass request.body directory, or "aws_proxy" to get request context
    """
    if path_parameters:
        if not isinstance(path_parameters, list):
            raise ValueError("path_parameters must be a list of strings")

        request_parameters = {
            "integration.request.path.%s" % k: "method.request.path.%s" % k
            for k in path_parameters
        }
    else:
        request_parameters = None

    if request_template:
        request_template = {"application/json": request_template}

    # TODO: add responses_template
    responses = {"default": {"statusCode": "200"}}

    if responses_template:
        responses["default"].update(responses_template)

    return dict(
        uri=uri,
        integration_type=integration_type,
        http_method="POST",
        credentials=iam_arn,
        request_template=request_template,
        request_parameters=request_parameters,
        responses=responses,
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
        "application/json": json.dumps(
            {
                "input": mapping_template,
                "stateMachineArn": sfn_arn,
                "region": "${region}",
            }
        )
    }

    # FIXME: take response templates as parameters so we can handle errors nicely.
    responses = {
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
        http_method="POST",
        credentials=iam_arn,
        request_template=request_template,
        responses=responses,
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
    :param path_parameters: list of path parameters in the apigw request path; if `object_key` is None, the last value here is used as as the object key to lookup
    :param http_method: HTTP method (GET, PUT, DELETE) to use for the integration.
    :param object_key: [optional] fixed object key to return from the bucket

    # TODO: path_parameters could be merged to allow multiple names
    # TODO: object_key_prefix: allow a key prefix to be used for accessing objects by path parameter

    Example OpenAPI integration:

    "x-amazon-apigateway-integration": {
        "uri": "arn:aws:apigateway:${region}:s3:path/{bucket}/{key}",
        "httpMethod": "GET",
        "type": "aws",
        "credentials": "${iam_role_arn}",
        "requestParameters": {
            "integration.request.path.bucket": "bucket_name",
            "integration.request.path.key": "method.request.path.key"
        },
        "responses": {
            "default": {
                "statusCode": "200",
                "responseParameters": {
                    "method.response.header.Content-Type": "'application/octet-stream'"
                }
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
    # NB: i think uri should be the bucket arn
    uri = f"arn:aws:apigateway:${{region}}:s3:path/{bucket_name}"

    if object_key:
        uri = "/".join((uri, object_key))
    elif path_parameters:
        uri = "/".join([uri] + path_parameters)
    else:
        raise ValueError("expected one of: 'object_key', 'path_parameters'")

    # response mapping (simple passthrough)
    # FIXME: take the integration response content type to get the object content type
    default_response_parameters = {
        "default": {
            "statusCode": "200",
            #            "responseParameters": {
            #                "method.response.header.Content-Type": "integration.response.header.Content-Type"
            #            },
        },
        "4xx": {"statusCode": "404"},
        "403": {"statusCode": "404"},
        "404": {"statusCode": "404"},
    }

    responses = kwargs.get("responses") or default_response_parameters

    # generate apigw integration config
    integration = dict(
        uri=uri,
        http_method=http_method,
        integration_type="aws",
        credentials=iam_arn,
        responses=responses,
    )

    return integration


@register_integration("aws_dynamodb_table_name")
def dynamodb_integration(
    table_name: str,
    iam_arn: str,
    path_parameters: List[str] = None,
    http_method: str = "POST",
    mapping_template: str = None,
    pk_pattern: str = None,
    sk_pattern: str = None,
    field_patterns: str = None,
    query_expr: str = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Returns an AWS API Gateway integration for DynamoDB PutItem.

    - POST maps to PutItem.
    - Required fields in body: owner, project, eventname, timestamp.
    - PK will be pk_pattern or the default
    - SK will be sk_pattern or the default
    - item fields will be field_patterns or 'timestamp=request.time'

    Optional:
    - mapping_template: override the default template if provided.
    """
    def create_put_item_mapping_template(table_name, ttl, pk_pattern, sk_pattern, fields):
        return """
#set($body = $util.parseJson($input.body))

#set($nowEpochSeconds = $context.requestTimeEpoch / 1000)
#set($expiration = $nowEpochSeconds + {ttl})

{{
  "TableName": "{table_name}",
  "Item": {{
    "PK": {{ "S": "{pk_pattern}" }},
    "SK": {{ "S": "{sk_pattern}" }},
    {fields}
  }}
}}""".format(table_name=table_name, ttl=ttl, pk_pattern=pk_pattern, sk_pattern=sk_pattern, fields=fields)

    def create_query_mapping_template(table_name: str, query_expr: str):
        """we cannot parameterise this, the user must supply vtl.
        ref: https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_Query.html#API_Query_Examples

        example:
    {
    "IndexName": "PostedBy-Index",
    "Limit": 3,
    "ConsistentRead": true,
    "ProjectionExpression": "Id, PostedBy, ReplyDateTime",
    "KeyConditionExpression": "Id = :v1 AND PostedBy BETWEEN :v2a AND :v2b",
    "ExpressionAttributeValues": {
        ":v1": {"S": "Amazon DynamoDB#DynamoDB Thread 1"},
        ":v2a": {"S": "User A"},
        ":v2b": {"S": "User C"}
    }"""
        return """
{{
    "TableName": "{table_name}", {query_expr}
}}""".format(table_name=table_name, query_expr=query_expr)

    assert table_name is not None
    # default mapping template if not provided
    assert mapping_template is None, "mapping_template must be none"

    # Define the AWS service integration URI
    # FIXME: i think we should let the caller set the entire mapping template
    if http_method == "POST":
        default_pk_pattern = "$input.path('$.owner')#$input.path('$.project')"
        default_sk_pattern = "$input.path('$.project')#$input.path('$.eventname')#$input.path('$.timestamp')"
        fields_block = field_patterns or '"timestamp": { "S": "$context.requestTime" }'
        default_ttl = 2592000

        uri = "arn:aws:apigateway:${region}:dynamodb:action/PutItem"
        mapping_template = create_put_item_mapping_template(table_name, ttl=default_ttl, pk_pattern=pk_pattern or default_pk_pattern, sk_pattern=sk_pattern or default_sk_pattern, fields=fields_block)
    elif http_method == "GET":
        assert query_expr is not None
        uri = "arn:aws:apigateway:${region}:dynamodb:action/Query"
        mapping_template = create_query_mapping_template(table_name, query_expr=query_expr)
    else:
        raise ValueError(f"Unsupported HTTP method {http_method} for DynamoDB integration. Only POST (PutItem) or GET (Query) is allowed.")

    logger.info("mapping_template: %s", str(mapping_template))

    request_template = {"application/json": mapping_template}

    request_parameters = kwargs.pop("request_parameters", {})

    # set up request parameters if needed to propagate the request params
    if any(("$input.params('origin')" in (field or "") for field in [pk_pattern, sk_pattern, field_patterns, query_expr])):
        request_parameters.update({"integration.request.header.origin": "method.request.header.origin"})

    responses = {
        "default": {"statusCode": "200"},
        "4xx": {"statusCode": "400"},
        "5xx": {"statusCode": "500"},
    }

    return dict(
        uri=uri,
        integration_type="aws",
        http_method="POST",
        credentials=iam_arn,
        request_template=request_template,
        responses=responses,
        request_parameters=request_parameters
    )
