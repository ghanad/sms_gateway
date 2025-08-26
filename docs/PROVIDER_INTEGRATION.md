# How to Add a New SMS Provider

This document explains how to add a new SMS provider to the SMS gateway.

## Introduction

The SMS gateway uses a provider adapter layer to handle different SMS provider APIs. This makes it easy to add new providers without modifying the core application logic.

Each provider is represented by an adapter class that knows how to communicate with that provider's API. These adapters are located in `server-b/providers/adapters.py`.

## Steps to Add a New Provider

To add a new provider, you need to follow these steps:

### 1. Update `ProviderType`

First, you need to add the new provider type to the `ProviderType` enum in `server-b/providers/models.py`.

For example, if you are adding a new provider called "AcmeSms", you would add the following to the `ProviderType` enum:

```python
class ProviderType(models.TextChoices):
    MAGFA = "magfa", _("Magfa")
    ACMESMS = "acmesms", _("AcmeSms")
```

### 2. Create a New Adapter Class

Next, you need to create a new adapter class for the provider in `server-b/providers/adapters.py`. The class should inherit from `BaseSmsProvider` and implement the `send_sms` method.

The `send_sms` method should take a recipient and a message as input, and it should return a dictionary containing the response from the provider's API.

Here's an example of an adapter class for the fictional "AcmeSms" provider:

```python
class AcmeSmsProvider(BaseSmsProvider):
    def send_sms(self, recipient: str, message: str) -> dict:
        headers = {
            'Content-Type': 'application/json',
            'X-Api-Key': self.provider.auth_config.get('api_key'),
        }

        payload = {
            'to': recipient,
            'body': message,
        }

        try:
            response = requests.post(self.provider.send_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
```

### 3. Update the Factory Function

Finally, you need to add the new provider type to the `get_provider_adapter()` factory function in `server-b/providers/adapters.py`.

This function is responsible for returning the correct provider adapter based on the provider's type.

Here's an example of how to update the factory function for the "AcmeSms" provider:

```python
def get_provider_adapter(provider: SmsProvider) -> BaseSmsProvider:
    if provider.provider_type == ProviderType.MAGFA:
        return MagfaSmsProvider(provider)
    elif provider.provider_type == ProviderType.ACMESMS:
        return AcmeSmsProvider(provider)
    else:
        raise NotImplementedError(f"Provider type {provider.provider_type} is not supported.")
```

## Conclusion

Once you have completed these steps, the new provider will be integrated into the SMS gateway. You will be able to add a new provider of this type in the admin dashboard and send test SMS messages using the new provider.
