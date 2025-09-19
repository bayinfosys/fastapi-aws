"""
Golden master test to capture complete OpenAPI output for validation
"""

import unittest
from fastapi import FastAPI
from fastapi_aws import AWSAPIRouter


class TestGoldenMaster(unittest.TestCase):
    """Capture complete OpenAPI schemas to detect regressions"""

    def test_lambda_integration_full_pipeline(self):
        """Test complete route -> integration -> OpenAPI pipeline for Lambda"""
        app = FastAPI()
        router = AWSAPIRouter()
        app.router = router

        @router.get(
            "/lambda-test",
            aws_lambda_arn="${lambda_function_arn}",
            aws_iam_arn="${lambda_role_arn}",
            description="Test Lambda Integration",
        )
        def lambda_endpoint():
            return {"status": "ok"}

        # Capture full OpenAPI schema
        openapi_schema = app.openapi()
        integration = openapi_schema["paths"]["/lambda-test"]["get"][
            "x-amazon-apigateway-integration"
        ]

        # Assertions for critical fields
        self.assertEqual(integration["uri"], "${lambda_function_arn}")
        self.assertEqual(integration["type"], "aws_proxy")
        self.assertEqual(integration["credentials"], "${lambda_role_arn}")
        self.assertIn("responses", integration)

        # Check if requestTemplates are present (they should be for Lambda proxy)
        # This will reveal if we're missing default template generation
        self.assertIn("requestTemplates", integration)

    def test_dynamodb_integration_full_pipeline(self):
        """Test complete pipeline for DynamoDB with VTL templates"""
        app = FastAPI()
        router = AWSAPIRouter()
        app.router = router

        @router.post(
            "/events",
            aws_dynamodb_table_name="events-table",
            aws_iam_arn="${dynamodb_role_arn}",
            aws_dynamodb_pk_pattern="USER#$input.params('origin')",
            aws_dynamodb_sk_pattern="EVENT#$context.requestTimeEpoch",
        )
        def create_event():
            return {"status": "created"}

        openapi_schema = app.openapi()
        integration = openapi_schema["paths"]["/events"]["post"][
            "x-amazon-apigateway-integration"
        ]

        # Check VTL template generation
        self.assertIn("requestTemplates", integration)
        self.assertIn("application/json", integration["requestTemplates"])

        # Check origin parameter detection
        if "requestParameters" in integration:
            self.assertIn(
                "integration.request.header.origin", integration["requestParameters"]
            )

    def test_s3_integration_full_pipeline(self):
        """Test S3 integration with object key"""
        app = FastAPI()
        router = AWSAPIRouter()
        app.router = router

        @router.get(
            "/files/{filename}",
            aws_s3_bucket="my-bucket",
            aws_iam_arn="${s3_role_arn}",
            aws_s3_object_key="uploads/{filename}",
        )
        def get_file(filename: str):
            return {"file": filename}

        openapi_schema = app.openapi()
        integration = openapi_schema["paths"]["/files/{filename}"]["get"][
            "x-amazon-apigateway-integration"
        ]

        expected_uri = (
            "arn:aws:apigateway:${region}:s3:path/my-bucket/uploads/{filename}"
        )
        self.assertEqual(integration["uri"], expected_uri)
