from fastapi.routing import APIRoute
from typing import Any, Callable, List
from string import Formatter


def register_integration(service_name: str):
    """Decorator to register integration methods dynamically in AWSAPIRoute"""

    def decorator(func):
        if not hasattr(AWSAPIRoute, "_integration_registry"):
            AWSAPIRoute._integration_registry = {}
        AWSAPIRoute._integration_registry[service_name] = func
        return func

    return decorator


class AWSAPIRoute(APIRoute):
    """fastapi.apiroute derived class adapted for aws service integrations
    This will provide an openapi json description of an aws service integration
    for a route, allowing the openapi spec to be uploaded as an aws apigw rest
    service automativicly.
    """

    _integration_registry = {}  # registered service integrations

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any):
        """overload the APIRoute constructor

        This has to happen because we cannot just pass kwargs around fastapi.
        Probably for code highlighting or smth but the internal fastapi include_router
        functions copy objects by explicity listing all the fields of the objects, so
        our derived class cannot have custom fields and use the app or router functions.

        Futhermore, the super-constructor removes or resets fields when it is called.

        very frustrating, up yours fastapi
        """
        # validate the route args contain an aws service entry for which we have an integration
        # and an entry for 'aws_iam_arn' for permission to call that service.
        selected_services = set(self._integration_registry).intersection(set(kwargs))

        if not selected_services:
            # no aws integration in this route, so just call super
            return super().__init__(path, endpoint, **kwargs)

        if len(selected_services) > 1:
            raise ValueError(
                f"Exactly one of {self._integration_registry.keys()} is required, but found {selected_services} in {kwargs.keys()}"
            )

        # pop the params from the kwargs to stop fastapi spazzing out
        aws_service_name = selected_services.pop()
        aws_service_value = kwargs.pop(aws_service_name)

        aws_iam_arn = kwargs.pop("aws_iam_arn", None)
        if not aws_iam_arn:
            raise ValueError("'aws_iam_arn' is required for AWS integrations.")

        # extract the path parmaeters
        if hasattr(self, "path_format"):
            path_parameters = self._extract_path_parameters(self.path_format)
        else:
            path_parameters = []

        # extract the mapping templates if present
        aws_request_template = kwargs.pop("request_template", None)
        aws_request_parameters = kwargs.pop("request_parameters", None)
        aws_mapping_template = kwargs.pop("aws_mapping_template", None)
        aws_response_template = kwargs.pop("response_template", None)
        # s3 integration params
        aws_object_key = kwargs.pop("aws_object_key", None)
        # dynamodb item fields
        aws_pk_pattern = kwargs.pop("dynamodb_item_pk_pattern", None)
        aws_sk_pattern = kwargs.pop("dynamodb_item_sk_pattern", None)
        aws_field_pattern = kwargs.pop("dynamodb_item_fields", None)

        # this is hack because fastapi does explict member copies resulting in duplicate
        # objects rather than copy-by-reference (which i expect).
        self.openapi_extra = kwargs.pop("openapi_extra", {})

        # APIRoute clears openapi_extra here if it is set, so preseve it before calling the super constructor
        if "x-amazon-apigateway-integration" in self.openapi_extra:
            integration = self.openapi_extra
        else:
            integration = None

        super().__init__(path, endpoint, **kwargs)

        # if we already have the x-int, it has been copied over the super constructor
        # so do not build a new integration
        if not integration:
            # find the integration which matches one of our kwargs
            integration_fn = self._integration_registry[aws_service_name]

            integration_params = integration_fn(
                aws_service_value,
                iam_arn=aws_iam_arn,
                path_parameters=path_parameters,
                mapping_template=aws_mapping_template,
                request_template=aws_request_template,
                request_parameters=aws_request_parameters,
                response_template=aws_response_template,
                object_key=aws_object_key,  # NB: s3 only
                http_method="GET" if "GET" in self.methods else next(iter(self.methods)),
                pk_pattern=aws_pk_pattern,  # ddb only
                sk_pattern=aws_sk_pattern,  # ddb only
                field_patterns=aws_field_pattern,  # ddb only
            )

            integration = self._create_integration(**integration_params)

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
        request_template: dict = None,
        request_parameters: dict = None,
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
        assert integration_type in ("aws", "aws_proxy")

        assert isinstance(responses, dict), "responses must be a dict [%s]" % str(
            type(responses)
        )
        assert (
            "default" in responses
        ), "expected 'default' in responses (recieved: '%s')" % str(
            list(responses.keys())
        )

        integration = {
            "uri": uri,
            "httpMethod": http_method,
            "type": integration_type,
            "credentials": credentials,
            "responses": responses,
        }

        if request_template is not None:
            # request templates must be a dict of mimetypes to strings
            # https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-integration-requestTemplates.html
            assert isinstance(
                request_template, dict
            ), "request_template must be dict [%s]" % (str(type(request_template)))

            request_template_mimetypes = ("application/json", "application/xml")
            assert all(
                x_ in request_template_mimetypes for x_ in request_template
            ), "only mimetypes are expected in request_templates (found: '%s')" % str(
                list(request_template.keys())
            )
            assert all(
                isinstance(x_, str) for x_ in request_template
            ), "all request templates must be strings (found: '%s')" % (
                str([str(type(x)) for x in request_template.values()])
            )

            integration["requestTemplates"] = request_template

        if request_parameters is not None:
            # TODO: validate against: https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-integration-requestParameters.html
            assert isinstance(
                request_parameters, dict
            ), "request_parameters must be dict [%s]" % str(type(request_parameters))
            integration["requestParameters"] = request_parameters

        return {"x-amazon-apigateway-integration": integration}


from .integrations import *
