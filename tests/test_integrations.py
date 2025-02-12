import unittest
import json
from fastapi_aws.integrations import (
    lambda_integration,
    s3_integration,
    step_function_sync_integration,
    step_function_integration,
)


class TestAWSIntegrations(unittest.TestCase):
    def test_lambda_integration(self):
        uri = "${lambda_function_arn}"
        iam = "${my_role_arn}"
        expected_output = {
            "uri": uri,
            "integration_type": "aws",
            "credentials": iam,
            "request_template": {
                "body": "$input.json('$')",
                "httpMethod": "$context.httpMethod",
                "resource": "$context.resourcePath",
                "path": "$context.path",
            },
            "response_template": {"default": {"statusCode": "200"}},
        }

        result = lambda_integration(uri, iam)

        self.maxDiff = None
        self.assertEqual(result, expected_output)

    def test_lambda_integration_with_path_params(self):
        uri = "${lambda_function_arn}"
        iam = "${my_role_arn}"
        path_params = ["user_id"]

        expected_output = {
            "uri": uri,
            "integration_type": "aws",
            "credentials": iam,
            "request_template": {
                "body": "$input.json('$')",
                "httpMethod": "$context.httpMethod",
                "resource": "$context.resourcePath",
                "path": "$context.path",
                "pathParameters": {
                    "user_id": "$input.params('user_id')"
                },
            },
            "response_template": {"default": {"statusCode": "200"}},
        }

        result = lambda_integration(uri, iam, path_parameters=path_params)

        self.maxDiff = None
        self.assertEqual(result, expected_output)

    def test_s3_integration_with_no_key_or_path(self):
        bucket_name = "test-bucket"
        iam = "${my_role_arn}"
        expected_output = {
            "uri": f"arn:aws:apigateway:${{region}}:s3:path/{bucket_name}",
            "credentials": iam,
            "http_method": "GET",
            "integration_type": "aws",
            "request_template": {
                "integration.request.path.bucket": "method.request.path.bucket",
                "integration.request.path.key": "method.request.path.key",
            },
            "response_template": {"default": {"statusCode": "200"}},
        }

        with self.assertRaises(ValueError):
            result = s3_integration(bucket_name, iam)


    def test_s3_integration_with_object_key(self):
        bucket_name = "test-bucket"
        iam = "${my_role_arn}"
        object_key = "${my_object_key}"
        expected_output = {
            "uri": f"arn:aws:apigateway:${{region}}:s3:path/{bucket_name}/${{my_object_key}}",
            "credentials": iam,
            "http_method": "GET",
            "integration_type": "aws",
            "request_template": {
                "integration.request.path.bucket": "method.request.path.bucket",
                "integration.request.path.key": "method.request.path.key",
            },
            "response_template": {"default": {"statusCode": "200"}},
        }

        result = s3_integration(bucket_name, iam, object_key=object_key)
        self.maxDiff = None
        self.assertEqual(result, expected_output)


    def test_s3_integration_with_path_parameters(self):
        bucket_name = "test-bucket"
        iam = "${my_role_arn}"
        path_parameters = ["user_id", "24"]
        expected_output = {
            "uri": f"arn:aws:apigateway:${{region}}:s3:path/{bucket_name}/user_id/24",
            "credentials": iam,
            "http_method": "GET",
            "integration_type": "aws",
            "request_template": {
                "integration.request.path.bucket": "method.request.path.bucket",
                "integration.request.path.key": "method.request.path.key",
            },
            "response_template": {"default": {"statusCode": "200"}},
        }

        result = s3_integration(bucket_name, iam, path_parameters=path_parameters)
        self.maxDiff = None
        self.assertEqual(result, expected_output)

    def test_step_function_integration(self):
        """Test Step Function integration"""
        sfn_arn = "${step_function_arn}"
        iam = "${my_role_arn}"
        expected_output = {
            "uri": "arn:aws:apigateway:${region}:states:action/StartExecution",
            "credentials": iam,
            "integration_type": "aws",
            "request_template": {
                "input": "$input.json('$')",
                "stateMachineArn": sfn_arn,
                "region": "${region}",
            },
            "response_template": {
                "default": {
                    "statusCode": "200",
                    "responseTemplates": {
                        "application/json": "#set($output = $util.parseJson($input.path('$.output')))\n$output.body"
                    },
                }
            },
        }

        result = step_function_integration(sfn_arn, iam)
        self.maxDiff = None
        self.assertEqual(result, expected_output)

    def test_step_function_sync_integration(self):
        """Test Step Function Sync integration"""
        sfn_arn = "${step_function_arn}"
        iam = "${my_role_arn}"
        expected_output = {
            "uri": "arn:aws:apigateway:${region}:states:action/StartSyncExecution",
            "credentials": iam,
            "integration_type": "aws",
            "request_template": {
                "input": "$input.json('$')",
                "stateMachineArn": sfn_arn,
                "region": "${region}",
            },
            "response_template": {
                "default": {
                    "statusCode": "200",
                    "responseTemplates": {
                        "application/json": "#set($output = $util.parseJson($input.path('$.output')))\n$output.body"
                    },
                }
            },
        }

        result = step_function_sync_integration(sfn_arn, iam)
        self.maxDiff = None
        self.assertEqual(result, expected_output)


if __name__ == "__main__":
    unittest.main()
