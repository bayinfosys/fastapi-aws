import unittest
from fastapi import FastAPI, Security
from fastapi.openapi.utils import get_openapi
from fastapi_aws import LambdaAuthorizer


class TestLambdaAuthorizer(unittest.TestCase):
    def test_lambda_authorizer_openapi_spec(self):
        app = FastAPI()

        # Instantiate LambdaAuthorizer
        authorizer_name = "MyLambdaAuthorizer"
        lambda_uri = "${lambda_authorizer_uri}"
        iam_role_arn = "${lambda_authorizer_iam_role_arn}"
        header_name = "Authorization"
        ttl = 60

        lambda_auth = LambdaAuthorizer(
            authorizer_name=authorizer_name,
            aws_lambda_uri=lambda_uri,
            aws_iam_role_arn=iam_role_arn,
            header_names=[header_name],
            ttl=ttl,
        )

        # Define a test route using the lambda_auth
        @app.get("/lambda-auth-test", dependencies=[Security(lambda_auth)])
        async def lambda_auth_test_route():
            return {"message": "This is a test"}

        # Generate the OpenAPI schema
        openapi_schema = get_openapi(
            title="Test API",
            version="1.0.0",
            description="API for testing LambdaAuthorizer",
            routes=app.routes,
        )

        # Extract the security schemes from the OpenAPI schema
        security_schemes = openapi_schema.get("components", {}).get(
            "securitySchemes", {}
        )

        # Assertions
        self.assertIn(
            authorizer_name,
            security_schemes,
            "Authorizer not found in security schemes",
        )
        authorizer_scheme = security_schemes[authorizer_name]

        # Assert that x-amazon-apigateway-authtype is present and correct
        self.assertIn(
            "x-amazon-apigateway-authtype",
            authorizer_scheme,
            "x-amazon-apigateway-authtype not found in authorizer scheme",
        )
        self.assertEqual(
            authorizer_scheme["x-amazon-apigateway-authtype"],
            "custom",
            "Incorrect x-amazon-apigateway-authtype value",
        )

        # Assert that x-amazon-apigateway-authorizer is present and correct
        self.assertIn(
            "x-amazon-apigateway-authorizer",
            authorizer_scheme,
            "x-amazon-apigateway-authorizer not found in authorizer scheme",
        )

        authorizer_details = authorizer_scheme["x-amazon-apigateway-authorizer"]

        # Check the authorizer details
        self.assertEqual(
            authorizer_details["type"],
            "request",
            "Incorrect authorizer type",
        )
        self.assertEqual(
            authorizer_details["authorizerUri"],
            lambda_uri,
            "Incorrect authorizerUri",
        )
        self.assertEqual(
            authorizer_details["authorizerCredentials"],
            iam_role_arn,
            "Incorrect authorizerCredentials",
        )
        self.assertEqual(
            authorizer_details["identityValidationExpression"],
            "^x-[a-z]+",
            "Incorrect identityValidationExpression",
        )
        self.assertEqual(
            authorizer_details["identitySource"],
            f"method.request.header.{header_name}",
            "Incorrect identitySource",
        )
        self.assertEqual(
            authorizer_details["authorizerResultTtlInSeconds"],
            ttl,
            "Incorrect authorizerResultTtlInSeconds",
        )
