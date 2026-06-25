"""Zhipu AI (智谱) API client — BigModel / GLM.

Uses OpenAI-compatible chat completions format.
"""
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

ZHIPU_TIMEOUT = 60  # seconds


def call_zhipu(system_prompt: str, user_prompt: str) -> str:
    """Call Zhipu AI API and return the assistant's response text.

    Returns empty string on any error (no API key, timeout, HTTP error, etc.).
    """
    api_key = settings.ZHIPU_API_KEY
    if not api_key:
        logger.warning('ZHIPU_API_KEY is not configured, skipping AI summary')
        return ''

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }

    payload = {
        'model': settings.ZHIPU_MODEL,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'temperature': 0.7,
        'max_tokens': 800,
    }

    try:
        resp = requests.post(
            settings.ZHIPU_API_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=ZHIPU_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data['choices'][0]['message']['content'].strip()
    except requests.exceptions.Timeout:
        logger.warning('Zhipu API timeout after %ds', ZHIPU_TIMEOUT)
    except requests.exceptions.RequestException as e:
        logger.warning('Zhipu API request failed: %s', e)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.warning('Zhipu API unexpected response format: %s', e)

    return ''
