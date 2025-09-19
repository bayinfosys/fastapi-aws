from typing import Any, Dict, List
import json


from ..route import register_integration


def step_function_integration_base(
    uri: str,
    sfn_arn: str,
    iam_arn: str,
    vtl_mapping_template: Dict[str, str],
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
    if vtl_mapping_template is None:
        vtl_mapping_template = "$input.json('$')"
    elif isinstance(vtl_mapping_template, dict):
        vtl_mapping_template = json.dumps(vtl_mapping_template)

    vtl_request_template = {
        "application/json": json.dumps(
            {
                "input": vtl_mapping_template,
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
        vtl_request_template=vtl_request_template,
        responses=responses,
    )


@register_integration("aws_sfn_sync_arn")
def step_function_sync_integration(
    sfn_arn: str,
    iam_arn: str,
    path_parameters: List[str] = None,
    vtl_mapping_template: dict = None,
    **kwargs,
) -> Dict[str, Any]:
    """returns an aws integration for sync invocation of a step function from apigw."""

    return step_function_integration_base(
        "arn:aws:apigateway:${region}:states:action/StartSyncExecution",
        sfn_arn,
        iam_arn,
        vtl_mapping_template,
    )


@register_integration("aws_sfn_arn")
def step_function_integration(
    sfn_arn: str,
    iam_arn: str,
    path_parameters: List[str] = None,
    vtl_mapping_template: dict = None,
    **kwargs,
) -> Dict[str, Any]:
    return step_function_integration_base(
        "arn:aws:apigateway:${region}:states:action/StartExecution",
        sfn_arn,
        iam_arn,
        vtl_mapping_template,
    )
