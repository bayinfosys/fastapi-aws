import unittest
import json
from fastapi_aws.route import AWSAPIRoute


class TestCreateIntegration(unittest.TestCase):
    def test_create_integration_lambda(self):
        params = {
            "aws_lambda_uri": "${my_function_uri}",
            "aws_iam_arn": "${iam_role_arn}",
            "request_template": {
                "body": "$input.json('$')",
                "httpMethod": "$context.httpMethod",
                "resource": "$context.resourcePath",
                "path": "$context.path",
            },
            "response_template": {"default": {"statusCode": "200"}},
        }

        expected_output = {
            "x-amazon-apigateway-integration": {
                "uri": params["aws_lambda_uri"],
                "httpMethod": "POST",
                "type": "aws",
                "credentials": params["aws_iam_arn"],
                "requestTemplates": {
                    "application/json": json.dumps(params["request_template"])
                },
                "responses": params["response_template"],
            }
        }

        aws_route = AWSAPIRoute("/", lambda: None, **params)
        result = aws_route.openapi_extra

        self.maxDiff = None
        self.assertEqual(result, expected_output)

    def test_create_integration_s3(self):
        params = {
            "aws_s3_bucket": "my-test-bucket",
            "aws_iam_arn": "${my_role_arn}",
            #            "response_template": {
            #                "method.response.header.Content-Length": "integration.response.header.Content-Length",
            #                "method.response.header.Content-Type": "integration.response.header.Content-Type",
            #                "method.response.header.Timestamp": "integration.response.header.Date",
            #            },
            "aws_object_key": "${my_object_key}"
        }

        expected_output = {
            "x-amazon-apigateway-integration": {
                "uri": "arn:aws:apigateway:${region}:s3:path/%s/%s" % (params["aws_s3_bucket"], params["aws_object_key"]),
                "httpMethod": "GET",
                "type": "aws",
                "credentials": "${my_role_arn}",
                "requestTemplates": {
                    "application/json": json.dumps(
                        {
                            "integration.request.path.bucket": "method.request.path.bucket",
                            "integration.request.path.key": "method.request.path.key",
                        }
                    )
                },
                "responses": {
                    "default": {"statusCode": "200"},
                    #                    "responseParameters": params["response_template"],
                },
            }
        }

        aws_route = AWSAPIRoute("/", lambda: None, **params)
        result = aws_route.openapi_extra

        self.maxDiff = None
        self.assertEqual(result, expected_output)


if __name__ == "__main__":
    unittest.main()
