import unittest
from fastapi_aws.authorizers import AWSAuthorizer


class TestAWSAuthorizer(unittest.TestCase):
    def test_aws_authorizer_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            auth = AWSAuthorizer(
                authorizer_name="TestAuthorizer", authorizer_type="token"
            )
            # Attempt to access the model to trigger the NotImplementedError
            _ = auth.model


if __name__ == "__main__":
    unittest.main()
