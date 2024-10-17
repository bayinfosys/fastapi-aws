import unittest
from fastapi import FastAPI, Security
from fastapi.openapi.utils import get_openapi
from fastapi_aws import CognitoAuthorizer


class TestCognitoAuthorizer(unittest.TestCase):
    def test_cognito_authorizer_openapi_spec(self):
        # Create a FastAPI app instance
        app = FastAPI()

        # Instantiate CognitoAuthorizer
        authorizer_name = "MyCognitoAuthorizer"
        cognito_auth = CognitoAuthorizer(authorizer_name=authorizer_name)

        # Define a test route using the cognito_auth
        @app.get("/test", dependencies=[Security(cognito_auth)])
        async def test_route():
            return {"message": "This is a test"}

        # Generate the OpenAPI schema
        openapi_schema = get_openapi(
            title="Test API",
            version="1.0.0",
            description="API for testing CognitoAuthorizer",
            routes=app.routes,
        )

        # Extract the security schemes from the OpenAPI schema
        security_schemes = openapi_schema.get("components", {}).get(
            "securitySchemes", {}
        )

        # Check if the authorizer is in the security schemes
        self.assertIn(
            authorizer_name,
            security_schemes,
            "Authorizer not found in security schemes",
        )

        # Get the specific security scheme
        authorizer_scheme = security_schemes[authorizer_name]

        # Assert that x-amazon-apigateway-authtype is present
        self.assertIn(
            "x-amazon-apigateway-authtype",
            authorizer_scheme,
            "x-amazon-apigateway-authtype not found in authorizer scheme",
        )

        # Assert that x-amazon-apigateway-authorizer is present
        self.assertIn(
            "x-amazon-apigateway-authorizer",
            authorizer_scheme,
            "x-amazon-apigateway-authorizer not found in authorizer scheme",
        )

        # Optionally, check the values of these keys
        self.assertEqual(
            authorizer_scheme["x-amazon-apigateway-authtype"],
            "cognito_user_pools",
            "Incorrect x-amazon-apigateway-authtype value",
        )

        authorizer_details = authorizer_scheme["x-amazon-apigateway-authorizer"]
        self.assertEqual(
            authorizer_details["type"],
            "cognito_user_pools",
            "Incorrect authorizer type",
        )
        self.assertIn(
            "${cognito_user_pool_arn}",
            authorizer_details["providerARNs"],
            "Cognito User Pool ARN not found in providerARNs",
        )


if __name__ == "__main__":
    unittest.main()
