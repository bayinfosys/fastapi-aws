import unittest
from fastapi import FastAPI, Security
from fastapi.openapi.utils import get_openapi
from fastapi_aws import APIKeyAuthorizer


class TestAPIKeyAuthorizer(unittest.TestCase):
    def test_apikey_authorizer_openapi_spec(self):
        app = FastAPI()

        # Instantiate APIKeyAuthorizer
        authorizer_name = "MyAPIKeyAuthorizer"
        header_name = "X-API-Key"

        with self.assertRaises(NotImplementedError):
            api_key_auth = APIKeyAuthorizer(
                authorizer_name=authorizer_name, header_names=[header_name]
            )
