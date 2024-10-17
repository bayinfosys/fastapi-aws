import unittest
from fastapi import FastAPI, Security, Depends
from fastapi.security import APIKeyHeader
from fastapi_aws import AWSAPIRouter, CognitoAuthorizer


class TestOpenAPIExtract(unittest.TestCase):
    def test_apikey_security_schema(self):
        app = FastAPI(default_route_class=AWSAPIRouter)

        API_KEY_NAME = "x-api-key"
        api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

        # Use dependencies at the route level
        @app.get("/secure-endpoint", dependencies=[Depends(api_key_header)])
        async def secure_endpoint():
            return {"message": "Secure Content"}

        openapi_spec = app.openapi()

        # Check if 'securitySchemes' is present
        self.assertIn("securitySchemes", openapi_spec.get("components", {}))
        self.assertIn("APIKeyHeader", openapi_spec["components"]["securitySchemes"])

        # Check if 'security' is specified at the path level
        self.assertIn("security", openapi_spec["paths"]["/secure-endpoint"]["get"])
        self.assertIn(
            {"APIKeyHeader": []},
            openapi_spec["paths"]["/secure-endpoint"]["get"]["security"],
        )

    def test_cognito_security_schema(self):
        app = FastAPI(default_route_class=AWSAPIRouter)

        cognito_auth = CognitoAuthorizer(authorizer_name="test-auth")

        # Use dependencies at the route level
        @app.get("/secure-endpoint", dependencies=[Depends(cognito_auth)])
        async def secure_endpoint():
            return {"message": "Secure Content"}

        openapi_spec = app.openapi()

        # Check if 'securitySchemes' is present
        self.assertIn("securitySchemes", openapi_spec.get("components", {}))
        self.assertIn("test-auth", openapi_spec["components"]["securitySchemes"])

        # Check if 'security' is specified at the path level
        self.assertIn("security", openapi_spec["paths"]["/secure-endpoint"]["get"])
        self.assertIn(
            {"test-auth": []},
            openapi_spec["paths"]["/secure-endpoint"]["get"]["security"],
        )


if __name__ == "__main__":
    unittest.main()
