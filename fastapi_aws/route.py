import json
import logging

from fastapi.routing import APIRoute
from typing import Any, Callable, List
from string import Formatter


logger = logging.getLogger(__name__)


def register_integration(service_name: str):
    """Decorator to register integration methods dynamically in AWSAPIRoute"""

    def decorator(func):
        if not hasattr(AWSAPIRoute, "_integration_registry"):
            AWSAPIRoute._integration_registry = {}
        AWSAPIRoute._integration_registry[service_name] = func
        return func

    return decorator


class AWSAPIRoute(APIRoute):
    """FastAPI APIRoute derived class adapted for AWS service integrations.

    This provides an OpenAPI JSON description of AWS service integrations
    for routes, allowing the OpenAPI spec to be uploaded as an AWS API Gateway
    REST service automatically.
    """

    _integration_registry = {}  # registered service integrations

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any):
        """Overload the APIRoute constructor to handle AWS integrations.

        This has to happen because we cannot just pass kwargs around FastAPI.
        Probably for code highlighting or something, but the internal FastAPI
        include_router functions copy objects by explicitly listing all the fields
        of the objects, so our derived class cannot have custom fields and use the
        app or router functions.

        Furthermore, the super-constructor removes or resets fields when it is called.

        Very frustrating, up yours FastAPI.

        Args:
            path: The route path pattern
            endpoint: The route handler function
            **kwargs: Route parameters, including AWS integration parameters
        """
        # Extract and validate AWS parameters before calling super()
        service_name, service_value, iam_arn, aws_kwargs = self._extract_aws_args(kwargs)

        # Preserve openapi_extra before super() clears it
        # This is a hack because FastAPI does explicit member copies resulting in
        # duplicate objects rather than copy-by-reference (which I expect).
        self.openapi_extra = kwargs.pop("openapi_extra", {})

        # Call FastAPI's constructor with cleaned kwargs
        super().__init__(path, endpoint, **kwargs)

        # If no AWS integration, we're done
        if not service_name:
            return

        # Build and apply the AWS integration
        self._apply_aws_integration(service_name, service_value, iam_arn, aws_kwargs)

    def _extract_aws_args(self, kwargs: dict):
        """Extract AWS-specific arguments from kwargs, leaving FastAPI args intact.

        Validates that route args contain exactly one AWS service entry for which
        we have an integration, and an entry for 'aws_iam_arn' for permission to
        call that service.

        The AWS parameters are removed from kwargs to prevent FastAPI from crashing
        on unrecognised keyword arguments in the super() call, but the values are
        preserved for integration building.

        Args:
            kwargs: The original route kwargs dict (modified in-place)

        Returns:
            tuple: (aws_kwargs dict with extracted parameters, selected_service_name or None)

        Raises:
            ValueError: If multiple AWS services specified or aws_iam_arn missing
        """
        # Find which AWS service integration is requested
        selected_services = set(self._integration_registry).intersection(set(kwargs))

        if not selected_services:
            return {}, None

        if len(selected_services) > 1:
            raise ValueError(
                f"Exactly one of {list(self._integration_registry.keys())} is required, "
                f"but found {selected_services} in {list(kwargs.keys())}"
            )

        selected_service = selected_services.pop()
        service_value = kwargs.pop(selected_service)
        iam_arn = kwargs.pop("aws_iam_arn", None)

        # Validate required parameters
        if not iam_arn:
            raise ValueError("'aws_iam_arn' is required for AWS integrations.")

        # Extract all AWS parameters (removing from kwargs to prevent FastAPI crashes)
        aws_kwargs = {
            # VTL templates
            "vtl_request_template": kwargs.pop("aws_vtl_request_template", None),
            "vtl_responses_template": kwargs.pop("aws_vtl_responses_template", None),
            "vtl_mapping_template": kwargs.pop("aws_vtl_mapping_template", None),

            # Service-specific parameters
            "s3_object_key": kwargs.pop("aws_s3_object_key", None),
            "dynamodb_pk_pattern": kwargs.pop("aws_dynamodb_pk_pattern", None),
            "dynamodb_sk_pattern": kwargs.pop("aws_dynamodb_sk_pattern", None),
            "dynamodb_fields": kwargs.pop("aws_dynamodb_fields", None),
            "dynamodb_query_expr": kwargs.pop("aws_dynamodb_query_expr", None),

            # SNS parameters
            "sns_subject_template": kwargs.pop("aws_sns_subject_template", None),
            "sns_message_template": kwargs.pop("aws_sns_message_template", None),

            # Generic parameters
            "request_parameters": kwargs.pop("aws_request_parameters", None),
        }

        return selected_service, service_value, iam_arn, aws_kwargs

    def _apply_aws_integration(self, service_name: str, service_value: str, iam_arn: str, aws_kwargs: dict):
        """Build and apply AWS integration using extracted parameters.

        Creates the x-amazon-apigateway-integration block for the OpenAPI spec
        by calling the appropriate registered integration function and merging
        the result into openapi_extra.

        Args:
            service_name: The AWS service integration to use (e.g. 'aws_lambda_uri')
            aws_kwargs: Dict of extracted AWS parameters
        """
        # extract path parameters from route path
        path_parameters = self._extract_path_parameters(self.path)

        # get the integration function for this service
        integration_fn = self._integration_registry[service_name]

        # add common parameters to aws_kwargs
        aws_kwargs.update({
            "path_parameters": path_parameters,
            "http_method": "GET" if "GET" in self.methods else next(iter(self.methods)),
        })

        # call the integration
        try:
            integration_params = integration_fn(service_value, iam_arn, **aws_kwargs)
        except Exception as e:
            logger.exception("'%s' does not accept '%s'", str(integration_fn), json.dumps(aws_kwargs))
            raise e

        # FIXME: we want to retain certain parameters (pass-throughs) from the
        # aws_kwargs after the integration_fn __if and only if__ the integration
        # doesn't add it's own. This ensures vtl_response_templates are preserved.
        # Currently, an integration may silently drop some parameters by not returning
        # them and this causes kwargs from the route decorator to disappear.

        # create the final integration object
        try:
            integration = self._create_integration(**integration_params)
        except Exception as e:
            logger.exception("'%s' unable to build integration with '%s'", str(integration_fn), json.dumps(integration_params))
            raise e

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
        responses: dict = None,
        vtl_request_template: dict = None,
        request_parameters: dict = None,
        vtl_responses_template: dict = None,
        http_method: str = "POST",
    ):
        """create the x-amazon-apigateway-integration block for the openapi spec

        This block defines how a request is made to the backend function so is always a POST request

        NB: uri is not required for mock integrations, so it should be optional

        request_template must be a dict of mimetype->string
        request_parameters map request (HTTP) to integration parameter
        responses is a dict of integration response patterns (key) to output transform

        see:
        + general: https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions.html
        + request_templates: https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-integration-requestTemplates.html
        + request_parameters: https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-integration-requestParameters.html
        + responses: https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-integration-response.html
        """
        def validate_template(template):
            """validate a template as best we can"""
            assert isinstance(template, dict), "template must be dict [%s]" % (str(type(template)))

            template_mimetypes = ("application/json", "application/xml")
            assert all(x_ in template_mimetypes for x_ in template), "only mimetypes are expected in templates (found: '%s')" % str(list(template.keys()))
            assert all(isinstance(x_, str) for x_ in template), "all templates must be strings (found: '%s')" % (str([str(type(x)) for x in template.values()]))

        assert integration_type in ("aws", "aws_proxy")

        assert isinstance(responses, dict), "responses must be a dict [%s]" % str(type(responses))
        assert ("default" in responses), "expected 'default' in responses (recieved: '%s')" % str(list(responses.keys()))

        integration = {
            "uri": uri,
            "httpMethod": http_method,
            "type": integration_type,
            "credentials": credentials,
            "responses": responses,
        }

        if vtl_request_template:
            # request templates must be a dict of mimetypes to strings
            # https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-integration-requestTemplates.html
            validate_template(vtl_request_template)
            integration["requestTemplates"] = vtl_request_template

        if request_parameters:
            # TODO: validate against: https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-integration-requestParameters.html
            assert isinstance(request_parameters, dict), "request_parameters must be dict [%s]" % str(type(request_parameters))
            integration["requestParameters"] = request_parameters

        if vtl_responses_template:
            validate_template(vtl_responses_template)
            if "default" not in integration["responses"]:
                logger.warning("expected 'default' response for response_template")
                raise ValueError()
            elif "responseTemplate" in integration["responses"]["default"]:
                logger.warning("existing responseTemplate in 'default', ignoring custom")
                raise ValueError("2")
            else:
                integration["responses"]["default"]["responseTemplates"] = vtl_responses_template

        return {"x-amazon-apigateway-integration": integration}


from .integrations import *
