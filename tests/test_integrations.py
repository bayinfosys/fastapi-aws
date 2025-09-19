import unittest
import json
from fastapi_aws.integrations import (
    lambda_integration,
    s3_integration,
    step_function_sync_integration,
    step_function_integration,
    sns_integration,
)


class TestAWSIntegrations(unittest.TestCase):
    def test_lambda_integration(self):
        uri = "${lambda_function_arn}"
        iam = "${my_role_arn}"
        integration_type = "aws_proxy"
        vtl_request_template = {
            "body": "$input.json('$')",
            "httpMethod": "$context.httpMethod",
            "resource": "$context.resourcePath",
            "path": "$context.path",
        }

        expected_output = {
            "uri": uri,
            "http_method": "POST",
            "integration_type": integration_type,
            "credentials": iam,
            "request_parameters": None,
            "vtl_request_template": {"application/json": vtl_request_template},
            "responses": {"default": {"statusCode": "200"}},
        }

        result = lambda_integration(
            uri,
            iam,
            integration_type=integration_type,
            vtl_request_template=vtl_request_template,
        )

        self.maxDiff = None
        self.assertEqual(result, expected_output)

    def test_lambda_integration_with_path_params(self):
        uri = "${lambda_function_arn}"
        iam = "${my_role_arn}"
        path_params = ["user_id"]
        integration_type = "aws"
        vtl_request_template = {
            "body": "$input.json('$')",
            "httpMethod": "$context.httpMethod",
            "resource": "$context.resourcePath",
            "path": "$context.path",
        }

        expected_output = {
            "uri": uri,
            "http_method": "POST",
            "integration_type": "aws",
            "credentials": iam,
            "request_parameters": {
                "integration.request.path.user_id": "method.request.path.user_id"
            },
            "vtl_request_template": {
                "application/json": {
                    "body": "$input.json('$')",
                    "httpMethod": "$context.httpMethod",
                    "resource": "$context.resourcePath",
                    "path": "$context.path",
                }
            },
            "responses": {"default": {"statusCode": "200"}},
        }

        result = lambda_integration(
            uri,
            iam,
            path_parameters=path_params,
            integration_type=integration_type,
            vtl_request_template=vtl_request_template,
        )

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
            "vtl_request_template": {
                "application/json": {
                    "integration.request.path.bucket": "method.request.path.bucket",
                    "integration.request.path.key": "method.request.path.key",
                }
            },
            "response_template": {"default": {"statusCode": "200"}},
        }

        with self.assertRaises(ValueError):
            result = s3_integration(bucket_name, iam)

    def test_s3_integration_with_object_key(self):
        bucket_name = "test-bucket"
        iam = "${my_role_arn}"
        s3_object_key = "${my_object_key}"
        expected_output = {
            "uri": f"arn:aws:apigateway:${{region}}:s3:path/{bucket_name}/${{my_object_key}}",
            "credentials": iam,
            "http_method": "GET",
            "integration_type": "aws",
            "responses": {
                "403": {"statusCode": "404"},
                "404": {"statusCode": "404"},
                "4xx": {"statusCode": "404"},
                "default": {"statusCode": "200"},
            },
        }

        result = s3_integration(bucket_name, iam, s3_object_key=s3_object_key)
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
            "responses": {
                "403": {"statusCode": "404"},
                "404": {"statusCode": "404"},
                "4xx": {"statusCode": "404"},
                "default": {"statusCode": "200"},
            },
        }

        result = s3_integration(bucket_name, iam, path_parameters=path_parameters)
        self.maxDiff = None
        self.assertEqual(result, expected_output)

    def test_step_function_integration(self):
        """Test Step Function integration"""
        sfn_arn = "${step_function_arn}"
        iam = "${my_role_arn}"
        vtl_request_template = {
            "application/json": json.dumps(
                {
                    "input": "$input.json('$')",
                    "stateMachineArn": sfn_arn,
                    "region": "${region}",
                }
            )
        }

        expected_output = {
            "uri": "arn:aws:apigateway:${region}:states:action/StartExecution",
            "http_method": "POST",
            "credentials": iam,
            "integration_type": "aws",
            "vtl_request_template": vtl_request_template,
            "responses": {
                "default": {
                    "statusCode": "200",
                    "responseTemplates": {
                        "application/json": "#set($output = $util.parseJson($input.path('$.output')))\n$output.body"
                    },
                }
            },
        }

        result = step_function_integration(
            sfn_arn, iam, vtl_request_template=vtl_request_template
        )
        self.maxDiff = None
        self.assertEqual(result, expected_output)

    def test_step_function_sync_integration(self):
        """Test Step Function Sync integration"""
        sfn_arn = "${step_function_arn}"
        iam = "${my_role_arn}"
        expected_output = {
            "uri": "arn:aws:apigateway:${region}:states:action/StartSyncExecution",
            "http_method": "POST",
            "credentials": iam,
            "integration_type": "aws",
            "vtl_request_template": {
                "application/json": json.dumps(
                    {
                        "input": "$input.json('$')",
                        "stateMachineArn": sfn_arn,
                        "region": "${region}",
                    }
                )
            },
            "responses": {
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

    def test_sns_integration(self):
        """Test SNS integration"""
        topic_arn = "${sns_topic_arn}"
        iam = "${my_role_arn}"
        sns_message_template = '{"account":"$body.account","project":"$body.project"}'

        expected_output = {
            "uri": "arn:aws:apigateway:${region}:sns:action/Publish",
            "http_method": "POST",
            "integration_type": "aws",
            "credentials": iam,
            "vtl_request_template": {
                "application/json": f"Action=Publish&TopicArn=$util.urlEncode(\"{topic_arn}\")&Message=$util.urlEncode(\"$input.body\")"
            },
            "request_parameters": {
                "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
            },
            "responses": {
                "default": {"statusCode": "200"},
                "4xx": {"statusCode": "400"},
                "5xx": {"statusCode": "500"},
            },
        }

        result = sns_integration(
            topic_arn,
            iam,
            sns_message_template=sns_message_template,
        )

        self.maxDiff = None
        self.assertEqual(result, expected_output)
