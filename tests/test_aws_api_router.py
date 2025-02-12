import unittest
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_aws import AWSAPIRouter, AWSAPIRoute


class TestAWSAPIRoute(unittest.TestCase):
    def check_aws_api_route_with_lambda_uri(
        self, method, path, aws_lambda_uri, aws_iam_arn, expected_request_template
    ):
        # Create a new FastAPI app and router for each test to avoid conflicts
        app = FastAPI(default_route_class=AWSAPIRoute)
        router = AWSAPIRouter()
        app.router = router

        # Define the endpoint dynamically
        async def endpoint():
            return {"status": "not implemented"}

        # Get the method decorator (get, post, etc.) from the router
        decorator = getattr(router, method)

        # Apply the decorator to the endpoint
        decorator(
            path,
            aws_lambda_uri=aws_lambda_uri,
            aws_iam_arn=aws_iam_arn,
            description="Test endpoint",
            summary="Test endpoint",
            tags=["test"],
        )(endpoint)

        # Generate OpenAPI schema
        openapi_schema = app.openapi()

        # Access the operation for the given path and method
        operation = openapi_schema["paths"][path][method.lower()]

        # Check if 'x-amazon-apigateway-integration' exists in the operation
        self.assertIn(
            "x-amazon-apigateway-integration",
            operation,
            "AWS integration not found in OpenAPI operation",
        )

        integration = operation["x-amazon-apigateway-integration"]

        # Assert the integration details
        self.assertEqual(integration["uri"], aws_lambda_uri)
        self.assertEqual(integration["httpMethod"], "POST")
        self.assertEqual(integration["type"], "aws")
        self.assertEqual(integration["credentials"], aws_iam_arn)
        self.assertIn("requestTemplates", integration)
        self.assertIn("responses", integration)

        # Check the request template
        request_template = json.loads(
            integration["requestTemplates"]["application/json"]
        )
        self.maxDiff = None
        self.assertEqual(
            request_template,
            expected_request_template,
            "Request template does not match expected value",
        )

    def test_aws_api_route_methods(self):
        methods = ["get", "post", "put", "delete"]
        for method in methods:
            with self.subTest(method=method):
                path = f"/test-{method}"
                aws_lambda_uri = "${test_function_arn}"
                aws_iam_arn = "${test_function_invoke_role_arn}"
                expected_request_template = {
                    "body": "$input.json('$')",
                    "httpMethod": "$context.httpMethod",
                    "resource": "$context.resourcePath",
                    "path": "$context.path",
                }
                self.check_aws_api_route_with_lambda_uri(
                    method, path, aws_lambda_uri, aws_iam_arn, expected_request_template
                )

    @unittest.skip("pathParameters expected output unknown")
    def test_aws_api_route_with_path_parameters(self):
        method = "get"
        path = "/user/{user_id}"
        aws_lambda_uri = "${user_function_arn}"
        aws_iam_arn = "${user_function_invoke_role_arn}"
        expected_request_template = {
            "body": "$input.json('$')",
            "httpMethod": "$context.httpMethod",
            "resource": "$context.resourcePath",
            "path": "$context.path",
#            "pathParameters": {
#                "user_id": "$input.params('user_id')",
#            },
        }
        self.check_aws_api_route_with_lambda_uri(
            method, path, aws_lambda_uri, aws_iam_arn, expected_request_template
        )

    def test_aws_api_route_basic(self):
        app = FastAPI()
        router = AWSAPIRouter()
        app.router = router

        @router.get(
            "/user",
            aws_lambda_uri="${user_function_arn}",
            aws_iam_arn="${user_function_invoke_role_arn}",
            description="Retrieve account information for the API key of the request",
            summary="Get account info",
            tags=["account"],
        )
        async def list_user_details():
            return {"status": "not implemented"}

        # Generate OpenAPI schema
        openapi_schema = app.openapi()

        # Access the operation for the '/user' path and 'get' method
        operation = openapi_schema["paths"]["/user"]["get"]

        # Check if 'x-amazon-apigateway-integration' exists in the operation
        self.assertIn(
            "x-amazon-apigateway-integration",
            operation,
            "AWS integration not found in OpenAPI operation",
        )

        integration = operation["x-amazon-apigateway-integration"]

        # Assert the integration details
        self.assertEqual(integration["uri"], "${user_function_arn}")
        self.assertEqual(integration["httpMethod"], "POST")
        self.assertEqual(integration["type"], "aws")
        self.assertEqual(integration["credentials"], "${user_function_invoke_role_arn}")
        self.assertIn("requestTemplates", integration)
        self.assertIn("responses", integration)

        # Check the request template
        request_template = json.loads(
            integration["requestTemplates"]["application/json"]
        )
        expected_request_template = {
            "body": "$input.json('$')",
            "httpMethod": "$context.httpMethod",
            "resource": "$context.resourcePath",
            "path": "$context.path",
        }
        self.assertEqual(
            request_template,
            expected_request_template,
            "Request template does not match expected value",
        )


if __name__ == "__main__":
    unittest.main()
