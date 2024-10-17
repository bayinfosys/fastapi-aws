from fastapi.routing import APIRoute
from typing import Any, Callable, Dict, List
from string import Formatter
import json


class AWSAPIRoute(APIRoute):
    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any):
        """overload the APIRoute constructor

        This has to happen because we cannot just pass kwargs around fastapi.
        Probably for code highlighting or smth but the internal fastapi include_router
        functions copy objects by explicity listing all the fields of the objects, so
        our derived class cannot have custom fields and use the app or router functions.

        Futhermore, the super-constructor removes or resets fields when it is called.

        up yours fastapi
        """
        required_kwargs = [("aws_lambda_uri", "aws_sfn_sync_arn", "aws_sfn_arn"), "aws_iam_arn"]

        # NB: any kwargs we do not pop will cause an error in super().__init__()
        self.aws_lambda_uri = kwargs.pop("aws_lambda_uri", None)
        self.aws_sfn_sync_arn = kwargs.pop("aws_sfn_sync_arn", None)
        self.aws_sfn_arn = kwargs.pop("aws_sfn_arn", None)
        self.aws_iam_arn = kwargs.pop("aws_iam_arn", None)
        self.aws_mapping_template = kwargs.pop("aws_mapping_template", None)

        # this is hack because fastapi is so shitty that it does explict member copies
        # resulting in duplicate objects rather than the expected copy-by-reference.
        self.openapi_extra = kwargs.pop("openapi_extra", {})

        if not (self.aws_lambda_uri or self.aws_sfn_sync_arn or self.aws_sfn_arn or self.openapi_extra):
            print("kwargs: '%s'" % str(kwargs))
            print("aws_lambda_uri: '%s'" % str(self.aws_lambda_uri))
            print("aws_sfn_sync_arn: '%s'" % str(self.aws_sfn_sync_arn))
            print("aws_sfn_arn: '%s'" % str(self.aws_sfn_arn))
            print("openapi_extra: '%s'" % str(self.openapi_extra))
            raise ValueError("require one of '%s', recieved: '%s'" % ("aws_lambda_uri, aws_sfn_sync_arn, aws_sfn_arn", str(list(kwargs.keys()))))

        # APIRoute clears openapi_extra here if it is set, so we store it in the integration parameter
        if self.openapi_extra and "x-amazon-apigateway-integration" in self.openapi_extra:
            integration = self.openapi_extra
        else:
            integration = None

        super().__init__(path, endpoint, **kwargs)

        if integration:
            # if we already have the x-int, it has been copied over the super constructor
            #assert "x-amazon-apigateway-integration" in self.openapi_extra, "openapi_extra provided without x-amazon-apigateway-integration %s" % str(self.openapi_extra)
            #integration = self.openapi_extra["x-amazon-apigateway-integration"]
            pass
        elif self.aws_lambda_uri:
            path_parameters = self._extract_path_parameters(self.path_format)
            integration = self._default_lambda_call(self.aws_lambda_uri, self.aws_iam_arn, path_parameters)
        elif self.aws_sfn_sync_arn:
            integration = self._default_step_function_sync_call(self.aws_sfn_sync_arn, self.aws_iam_arn, {}, self.aws_mapping_template)
        elif self.aws_sfn_arn:
            integration = self._default_step_function_call(self.aws_sfn_arn, self.aws_iam_arn, {}, self.aws_mapping_template)
        else:
            raise ValueError("expected one of [aws_lambda_uri, aws_sfn_sync_arn, openapi_extra.x-amazon-apigateway-integration]")

        if self.openapi_extra is None:
            self.openapi_extra = {}

        self.openapi_extra.update(integration)

    @staticmethod
    def _extract_path_parameters(path: str) -> List[str]:
        formatter = Formatter()
        return [fname for _, fname, _, _ in formatter.parse(path) if fname]

    def _create_integration(
        self,
        uri: str,
        integration_type: str,
        credentials: str,
        request_template,
        response_template,
    ):
        """create the x-amazon-apigateway-integration block for the openapi spec

        This block defines how a request is made to the backend function so is always a POST request

        NB: uri is not required for mock integrations, so it should be optional
        """
        assert integration_type in ("aws", "aws_proxy")
        assert isinstance(request_template, dict), "request_template must be dict [%s]" % (str(type(request_template)))

        return {
            "x-amazon-apigateway-integration": {
                "uri": uri,
                "httpMethod": "POST",
                "type": integration_type,
                "credentials": credentials,
                "requestTemplates": {"application/json": json.dumps(request_template)},
                "responses": response_template,
            }
        }

    def _default_mock_integration(
        self, uri: str, iam_arn: str, path_parameters: List[str]
    ) -> Dict[str, Any]:
        """returns a mock integration which has a fixed response value
        NB: this function should take parameters for the fixed responses.
        NB: this can currently be used for a 'not implemented' response.
        """
        return self._create_integration(
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

    def _default_lambda_call(
        self, uri: str, iam_arn: str, path_parameters: List[str]
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

        return self._create_integration(
            uri=uri,
            integration_type="aws_proxy",
            credentials=iam_arn,
            request_template=request_template,
            response_template=response_template,
        )

    def _default_step_function_base_call(
        self, uri: str, sfn_arn: str, iam_arn: str, path_parameters: List[str], mapping_template: Dict[str, str]
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

        return self._create_integration(
            uri=uri,
            integration_type="aws",
            credentials=iam_arn,
            request_template=request_template,
            response_template=response_template,
        )

    def _default_step_function_sync_call(
        self, sfn_arn: str, iam_arn: str, path_parameters: List[str], mapping_template: dict,
    ) -> Dict[str, Any]:
        """returns an aws integration for sync invocation of a step function from apigw."""

        return self._default_step_function_base_call(
            "arn:aws:apigateway:${region}:states:action/StartSyncExecution",
            sfn_arn,
            iam_arn,
            path_parameters,
            mapping_template
        )

    def _default_step_function_call(
        self, sfn_arn: str, iam_arn: str, path_parameters: List[str], mapping_template: dict,
    ) -> Dict[str, Any]:
        return self._default_step_function_base_call(
            "arn:aws:apigateway:${region}:states:action/StartExecution",
            sfn_arn,
            iam_arn,
            path_parameters,
            mapping_template
        )
