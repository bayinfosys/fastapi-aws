from fastapi.routing import APIRoute
from typing import Any, Callable, Dict, List
from string import Formatter
import json


class AWSAPIRoute(APIRoute):
    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any):
        self.aws_integration_uri = kwargs.pop("aws_integration_uri", None)
        super().__init__(path, endpoint, **kwargs)

        if self.aws_integration_uri:
            path_parameters = self._extract_path_parameters(self.path_format)
            integration = self._default_lambda_call(
                self.aws_integration_uri, path_parameters
            )

            if self.openapi_extra is None:
                self.openapi_extra = {}

            self.openapi_extra.update(integration)

    @staticmethod
    def _extract_path_parameters(path: str) -> List[str]:
        formatter = Formatter()
        return [fname for _, fname, _, _ in formatter.parse(path) if fname]

    def _default_lambda_call(
        self, uri: str, path_parameters: List[str]
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
        credentials = "${lambda_invoke_iam_role_arn}"  # FIXME: parameterize this

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

        return {
            "x-amazon-apigateway-integration": {
                "uri": uri,
                "httpMethod": "POST",  # For Lambda proxy integration, this remains POST
                "type": "aws_proxy",
                "credentials": credentials,
                "requestTemplates": {"application/json": json.dumps(request_template)},
                "responses": response_template,
            }
        }
