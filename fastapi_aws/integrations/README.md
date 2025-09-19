# AWS Integrations

This directory contains AWS service integrations for API Gateway. Each integration generates the appropriate `x-amazon-apigateway-integration` blocks for OpenAPI specifications.

## Available Integrations

### Lambda Functions (`lambda_fn.py`)
- `aws_lambda_arn` - Lambda function invocation (proxy mode)
- `aws_lambda_direct_uri` - Lambda function invocation (direct mode)

**Usage:**
```python
@router.post(
    "/process",
    aws_lambda_arn="${function_arn}",
    aws_iam_arn="${lambda_invoke_role_arn}"
)
```

### DynamoDB (`dynamodb.py`)
- `aws_dynamodb_table_name` - DynamoDB PutItem/Query operations with VTL templates

**Parameters:**
- `aws_dynamodb_pk_pattern` - Primary key VTL expression
- `aws_dynamodb_sk_pattern` - Sort key VTL expression
- `aws_dynamodb_field_patterns` - Item fields VTL expression
- `aws_dynamodb_query_expr` - Query expression for GET operations

**Usage:**
```python
@router.post(
    "/events",
    aws_dynamodb_table_name="events",
    aws_iam_arn="${dynamodb_role_arn}",
    aws_dynamodb_pk_pattern="USER#$input.params('user_id')",
    aws_dynamodb_sk_pattern="EVENT#$context.requestTimeEpoch"
)
```

### S3 Storage (`s3.py`)
- `aws_s3_bucket` - S3 object access (GET/PUT/DELETE)

**Parameters:**
- `aws_s3_object_key` - Fixed object key
- Path parameters used as object key if `aws_s3_object_key` not provided

**Usage:**
```python
@router.get(
    "/files/{filename}",
    aws_s3_bucket="my-bucket",
    aws_iam_arn="${s3_access_role_arn}",
    aws_s3_object_key="uploads/{filename}"
)
```

### Step Functions (`step_function.py`)
- `aws_sfn_arn` - Async step function execution
- `aws_sfn_sync_arn` - Synchronous step function execution

**Usage:**
```python
@router.post(
    "/workflow",
    aws_sfn_sync_arn="${workflow_arn}",
    aws_iam_arn="${stepfunction_role_arn}",
    aws_vtl_mapping_template={"input": "$input.json('$')"}
)
```

### SNS Notifications (`sns.py`)
- `aws_sns_topic_arn` - SNS message publishing

**Parameters:**
- `aws_sns_subject_template` - Message subject VTL expression
- `aws_sns_message_template` - Message body VTL expression (defaults to `$input.body`)

**Usage:**
```python
@router.post(
    "/notify",
    aws_sns_topic_arn="${alert_topic_arn}",
    aws_iam_arn="${sns_publish_role_arn}",
    aws_sns_subject_template="Alert from $context.identity.sourceIp"
)
```

### Mock Responses (`mock.py`)
- `mock` - Fixed mock responses for testing

## Common Parameters

All integrations support:
- `aws_iam_arn` - IAM role ARN for service access (required)
- `aws_vtl_request_template` - Custom VTL request template
- `aws_vtl_response_template` - Custom VTL response template
- `aws_request_parameters` - Additional request parameter mappings

## VTL Context Variables

Common VTL expressions available in templates:
- `$input.body` - Request body
- `$input.params('param_name')` - Query/header parameters
- `$context.requestTimeEpoch` - Request timestamp
- `$context.identity.sourceIp` - Client IP address
- `$context.authorizer.claims[...]` - Authorizer claims (Cognito)

## Adding New Integrations

1. Create new Python file in this directory
2. Use `@register_integration("service_name")` decorator
3. Function should accept `service_value`, `iam_arn`, and relevant parameters
4. Return dict with `uri`, `integration_type`, `credentials`, `responses`
5. Add to `__init__.py` exports
