from typing import Any, Dict, List


from ..route import register_integration


@register_integration("aws_lambda_arn")
def lambda_integration(
    service_value: str,
    iam_arn: str,
    integration_type="aws_proxy",
    path_parameters: List[str] = None,
    vtl_request_template: str = None,
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

    if vtl_request_template:
        vtl_request_template = {"application/json": vtl_request_template}

    # TODO: add responses_template
    responses = {"default": {"statusCode": "200"}}

    if responses_template:
        responses["default"].update(responses_template)

    return dict(
        uri=service_value,
        integration_type=integration_type,
        http_method="POST",
        credentials=iam_arn,
        vtl_request_template=vtl_request_template,
        request_parameters=request_parameters,
        responses=responses,
    )


@register_integration("aws_lambda_direct_uri")
def lambda_direct_integration(
    service_value: str,
    iam_arn: str,
    integration_type="aws",
    path_parameters: List[str] = None,
    vtl_request_template: str = None,
    responses_template: str = None,
    **kwargs,
) -> Dict[str, Any]:
    """a direct lambda integration calls the lambda with no extra info
    This allows the request and response template mappings to do all the work rather than inside the lambda.
    NB: the difference is `integration_type=aws` for direct, `integration_type=aws_proxy` for extra request data.
    """
    return lambda_integration(
        service_value,
        iam_arn,
        integration_type="aws",
        path_parameters=path_parameters,
        vtl_request_template=vtl_request_template,
        responses_template=responses_template,
        **kwargs,
    )
