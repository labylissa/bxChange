"""Generate ready-to-use code snippets for bxChange connector execution."""
import re

SUPPORTED_LANGS = frozenset({"curl", "python", "javascript", "php", "java"})
_BASE_URL = "https://app.bxchange.io/api/v1/connectors/{connector_id}/execute"


def _to_snake(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]+', '_', name).strip('_').lower() or "connector"


def _to_camel(name: str) -> str:
    words = [w for w in re.split(r'[^a-zA-Z0-9]+', name) if w]
    if not words:
        return "connector"
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


def _to_pascal(name: str) -> str:
    words = [w for w in re.split(r'[^a-zA-Z0-9]+', name) if w]
    return "".join(w.capitalize() for w in words) or "Connector"


def generate_snippet(
    connector_id: str,
    connector_name: str,
    lang: str,
    api_key_hint: str | None,
) -> str:
    if lang not in SUPPORTED_LANGS:
        raise ValueError(f"Unsupported language: {lang!r}. Supported: {sorted(SUPPORTED_LANGS)}")

    key = api_key_hint if api_key_hint else "YOUR_API_KEY"
    url = _BASE_URL.format(connector_id=connector_id)
    snake = _to_snake(connector_name)
    camel = _to_camel(connector_name)
    pascal = _to_pascal(connector_name)

    if lang == "curl":
        return _curl(url, key)
    if lang == "python":
        return _python(url, key, snake)
    if lang == "javascript":
        return _javascript(url, key, camel)
    if lang == "php":
        return _php(url, key, snake)
    return _java(url, key, pascal)


def _curl(url: str, key: str) -> str:
    lines = [
        f"curl -X POST {url} \\",
        f'  -H "X-API-Key: {key}" \\',
        '  -H "Content-Type: application/json" \\',
        "  -d '{",
        '    "param1": "value1"',
        "  }'",
    ]
    return "\n".join(lines) + "\n"


def _python(url: str, key: str, snake: str) -> str:
    lines = [
        "import httpx",
        "import asyncio",
        "",
        "",
        f"async def call_{snake}(params: dict) -> dict:",
        "    async with httpx.AsyncClient() as client:",
        "        response = await client.post(",
        f'            "{url}",',
        f'            headers={{"X-API-Key": "{key}"}},',
        "            json=params,",
        "            timeout=30.0,",
        "        )",
        "        response.raise_for_status()",
        "        return response.json()",
        "",
        "",
        f"result = asyncio.run(call_{snake}({{",
        '    "param1": "value1",',
        "}))",
        "print(result)",
    ]
    return "\n".join(lines) + "\n"


def _javascript(url: str, key: str, camel: str) -> str:
    fn_name = (camel[0].upper() + camel[1:]) if camel else "Connector"
    lines = [
        f"async function call{fn_name}(params) {{",
        "  const response = await fetch(",
        f"    '{url}',",
        "    {",
        "      method: 'POST',",
        "      headers: {",
        f"        'X-API-Key': '{key}',",
        "        'Content-Type': 'application/json',",
        "      },",
        "      body: JSON.stringify(params),",
        "    }",
        "  );",
        f"  if (!response.ok) throw new Error(`bxChange error: ${{response.status}}`);",
        "  return response.json();",
        "}",
        "",
        "// Exemple d'appel",
        f"call{fn_name}({{ param1: 'value1' }})",
        "  .then(result => console.log(result))",
        "  .catch(console.error);",
    ]
    return "\n".join(lines) + "\n"


def _php(url: str, key: str, snake: str) -> str:
    lines = [
        "<?php",
        f"function call_{snake}(array $params): array {{",
        f"    $ch = curl_init('{url}');",
        "    curl_setopt_array($ch, [",
        "        CURLOPT_POST => true,",
        "        CURLOPT_RETURNTRANSFER => true,",
        "        CURLOPT_HTTPHEADER => [",
        f"            'X-API-Key: {key}',",
        "            'Content-Type: application/json',",
        "        ],",
        "        CURLOPT_POSTFIELDS => json_encode($params),",
        "        CURLOPT_TIMEOUT => 30,",
        "    ]);",
        "    $response = curl_exec($ch);",
        "    curl_close($ch);",
        "    return json_decode($response, true);",
        "}",
        "",
        "// Exemple d'appel",
        f"$result = call_{snake}(['param1' => 'value1']);",
        "print_r($result);",
    ]
    return "\n".join(lines) + "\n"


def _java(url: str, key: str, pascal: str) -> str:
    lines = [
        "import java.net.http.*;",
        "import java.net.URI;",
        "import com.fasterxml.jackson.databind.ObjectMapper;",
        "",
        f"public class {pascal}Client {{",
        f'    private static final String API_KEY = "{key}";',
        f'    private static final String URL = "{url}";',
        "",
        "    public static String execute(Object params) throws Exception {",
        "        var mapper = new ObjectMapper();",
        "        var body = mapper.writeValueAsString(params);",
        "",
        "        var request = HttpRequest.newBuilder()",
        "            .uri(URI.create(URL))",
        '            .header("X-API-Key", API_KEY)',
        '            .header("Content-Type", "application/json")',
        "            .POST(HttpRequest.BodyPublishers.ofString(body))",
        "            .build();",
        "",
        "        var client = HttpClient.newHttpClient();",
        "        var response = client.send(request, HttpResponse.BodyHandlers.ofString());",
        "        return response.body();",
        "    }",
        "}",
    ]
    return "\n".join(lines) + "\n"
