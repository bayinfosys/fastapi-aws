from fastapi.routing import APIRoute
from fastapi import APIRouter
from fastapi.types import DecoratedCallable
from typing import Any, Callable, Dict, List, Optional, Type, Union
from string import Formatter
import json
from enum import Enum
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi_path

# Custom APIRoute class
class AWSAPIRoute(APIRoute):
    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        aws_integration_uri: Optional[str] = None,
        **kwargs: Any
    ):
        self.aws_integration_uri = aws_integration_uri
        super().__init__(path, endpoint, **kwargs)

    def get_openapi_operation(self, *, operation_id: Optional[str] = None) -> Dict[str, Any]:
        operation = super().get_openapi_operation(operation_id=operation_id)
        if self.aws_integration_uri:
            path_parameters = self._extract_path_parameters(self.path_format)
            integration = self._default_lambda_call(self.aws_integration_uri, path_parameters)
            operation["x-amazon-apigateway-integration"] = integration["x-amazon-apigateway-integration"]
        return operation

    @staticmethod
    def _extract_path_parameters(path: str) -> List[str]:
        formatter = Formatter()
        return [fname for _, fname, _, _ in formatter.parse(path) if fname]

    def _default_lambda_call(self, uri: str, path_parameters: List[str]) -> Dict[str, Any]:
        request_template = {
            "body": "$input.json('$')",
            "httpMethod": "$context.httpMethod",
            "resource": "$context.resourcePath",
            "path": "$context.path",
        }

        if path_parameters:
            request_template["pathParameters"] = {
                name: f"$input.params('{name}')"
                for name in path_parameters
            }

        return {
            "x-amazon-apigateway-integration": {
                "uri": uri,
                "httpMethod": "POST",  # For Lambda proxy integration, this remains POST
                "type": "aws_proxy",
                "credentials": "${lambda_invoke_iam_role_arn}",  # Adjust as needed
                "requestTemplates": {
                    "application/json": json.dumps(request_template)
                },
                "responses": {
                    "default": {
                        "statusCode": "200"
                    }
                }
            }
        }
