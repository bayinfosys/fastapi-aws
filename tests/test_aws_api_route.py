import unittest
from fastapi import FastAPI
from fastapi_aws import AWSAPIRoute, AWSAPIRouter


class TestAWSAPIRoute(unittest.TestCase):
    def test_aws_api_route_with_lambda(self):
        """End-to-end test for AWSAPIRoute with Lambda integration"""
        app = FastAPI(default_route_class=AWSAPIRoute)
        router = AWSAPIRouter()
        app.router = router

        @router.get(
            "/lambda-test",
            aws_lambda_arn="${lambda_function_arn}",
            aws_iam_arn="${lambda_role_arn}",
            description="Test Lambda",
            summary="Lambda Test",
            tags=["test"],
        )
        def lambda_endpoint():
            return {"status": "ok"}

        openapi_schema = app.openapi()
        operation = openapi_schema["paths"]["/lambda-test"]["get"]

        self.assertIn("x-amazon-apigateway-integration", operation)
        self.assertEqual(operation["x-amazon-apigateway-integration"]["uri"], "${lambda_function_arn}")


if __name__ == "__main__":
    unittest.main()
