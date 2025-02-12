"""AWS APIGateway Authorizers defined for openapi spec

Apply these security schemas on routers and endpoints to export an openapi
spec with aws integrations.

TODO: aws can have lambda authorizers as request or token types; however, in
      this implementation the APIKeyAuthorizer accepts token-type auth but
      does not allow lambda definitions, and the lambda definition allows
      lambda uri but only request-type auth. This is a limitation.

refs:
+ https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-api-key-source.html
+ https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-auth.html
+ https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-authorizer.html
"""
from fastapi import Request
from fastapi.security import HTTPBearer
from fastapi.openapi.models import APIKey


class AWSAuthorizer(HTTPBearer):
    """Base class for all AWS authorizers

    type: str, should be one of ("token", "request", "cognito_user_pools")

    ref:
    """

    DEFAULT_HEADER_FIELDNAME = "Authorization"

    def __init__(
        self,
        authorizer_name: str,
        authorizer_type: str,
        auto_error: bool = True,
        header_names: list = None,
        ttl: int = 0,
    ):
        self.scheme_name = authorizer_name
        self.auto_error = auto_error
        self.ttl = ttl

        assert authorizer_type in ("token", "request", "cognito_user_pools")
        self.authorizer_type = authorizer_type

        if header_names is None:
            self.header_names = [AWSAuthorizer.DEFAULT_HEADER_FIELDNAME]
        elif not isinstance(header_names, list):
            self.header_names = [header_names]
        else:
            self.header_names = header_names

        self.model = self._create_model()

    def _create_model(self):
        raise NotImplementedError()

    async def __call__(self, request: Request):
        """this class does not do any actual auth"""
        pass


class CognitoAuthorizer(AWSAuthorizer):
    """Fake cognito authorizer security model.

    NB: we only accept single user_pool_arn at the moment
    """

    DEFAULT_USER_POOL_ARN = "${cognito_user_pool_arn}"

    def __init__(
        self,
        authorizer_name: str,
        auto_error: bool = True,
        user_pool_arn=None,
        header_names=None,
    ):
        """Initialize with the authorizer name.

        Args:
            authorizer_name (str): The name of the Cognito authorizer on AWS.
        """
        self.user_pool_arn = user_pool_arn or CognitoAuthorizer.DEFAULT_USER_POOL_ARN

        super().__init__(
            authorizer_name,
            "cognito_user_pools",
            auto_error=auto_error,
            header_names=header_names,
        )

    def _create_model(self):
        return APIKey(
            **{
                "type": "apiKey",
                "in": "header",
                "name": self.scheme_name,
                "x-amazon-apigateway-authtype": "cognito_user_pools",
                "x-amazon-apigateway-authorizer": {
                    "type": self.authorizer_type,
                    "providerARNs": [self.user_pool_arn],
                    "authorizerResultTtlInSeconds": self.ttl,
                },
            }
        )


class APIKeyAuthorizer(AWSAuthorizer):
    """APIKey authorizers check the header field for a specific value.

    TODO: x-amazon-apigateway-api-key-source implementation required.
    https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-api-key-source.html
    """

    DEFAULT_HEADER_FIELD_NAME = "x-api-key"

    def __init__(
        self, *, authorizer_name: str, auto_error: bool = True, header_names: str = None
    ):
        super().__init__(
            authorizer_name, "token", auto_error=auto_error, header_names=header_names
        )

    def _create_model(self):
        raise NotImplementedError()


class LambdaAuthorizer(AWSAuthorizer):
    """Lambda authorizers run custom authorization code

    TODO: x-amazon-apigateway-api-key-source implementation required.
    https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-api-key-source.html
    """

    def __init__(
        self,
        *,
        authorizer_name: str,
        auto_error: bool = True,
        aws_lambda_uri: str = None,
        aws_iam_role_arn: str = None,
        **kwargs
    ):
        assert aws_lambda_uri is not None
        assert aws_iam_role_arn is not None

        self.aws_lambda_uri = aws_lambda_uri
        self.aws_iam_role_arn = aws_iam_role_arn

        super().__init__(authorizer_name, "request", auto_error=auto_error, **kwargs)

    def _create_model(self):
        authorizer_params = {
            "type": self.authorizer_type,
            "authorizerUri": self.aws_lambda_uri,
            "authorizerCredentials": self.aws_iam_role_arn,
            "identityValidationExpression": "^x-[a-z]+",
            "authorizerResultTtlInSeconds": self.ttl,
        }

        if self.authorizer_type == "request":
            assert (
                self.header_names is not None
            ), "header_names is required when authorizer_type is 'request'"

            mappings = [
                ".".join(("method", "request", "header", name))
                for name in self.header_names
            ]

            authorizer_params.update({"identitySource": ", ".join(mappings)})
            print("%s: identity_source: '%s'" % ("auth", str(authorizer_params)))

        return APIKey(
            **{
                "type": "apiKey",
                "name": self.scheme_name,
                "in": "header",
                "x-amazon-apigateway-authtype": "custom",
                "x-amazon-apigateway-authorizer": authorizer_params,
            }
        )
