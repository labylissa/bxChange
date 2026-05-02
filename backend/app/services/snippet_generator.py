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
    connector_operation: str | None = None,
) -> str:
    """Generate a code snippet for executing a connector.

    connector_operation: the default SOAP operation stored on the connector.
    When absent, the snippet includes "operation" in the example params so the
    caller knows they must supply it at runtime.
    """
    if lang not in SUPPORTED_LANGS:
        raise ValueError(f"Unsupported language: {lang!r}. Supported: {sorted(SUPPORTED_LANGS)}")

    key = api_key_hint if api_key_hint else "YOUR_API_KEY"
    url = _BASE_URL.format(connector_id=connector_id)
    snake = _to_snake(connector_name)
    camel = _to_camel(connector_name)
    pascal = _to_pascal(connector_name)
    show_operation = not (connector_operation and connector_operation.strip())

    if lang == "curl":
        return _curl(url, key, show_operation)
    if lang == "python":
        return _python(url, key, snake, show_operation)
    if lang == "javascript":
        return _javascript(url, key, camel, show_operation)
    if lang == "php":
        return _php(url, key, snake, show_operation)
    return _java(url, key, pascal, show_operation)


def _curl(url: str, key: str, show_operation: bool) -> str:
    body_lines = []
    if show_operation:
        body_lines.append('    "operation": "NomOperation",')
    body_lines.append('    "param1": "value1"')
    lines = [
        f"curl -X POST {url} \\",
        f'  -H "X-API-Key: {key}" \\',
        '  -H "Content-Type: application/json" \\',
        "  -d '{",
        *body_lines,
        "  }'",
    ]
    return "\n".join(lines) + "\n"


def _python(url: str, key: str, snake: str, show_operation: bool) -> str:
    example_lines = []
    if show_operation:
        example_lines.append('    "operation": "NomOperation",')
    example_lines.append('    "param1": "value1",')
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
        *example_lines,
        "}))",
        "print(result)",
    ]
    return "\n".join(lines) + "\n"


def _javascript(url: str, key: str, camel: str, show_operation: bool) -> str:
    fn_name = (camel[0].upper() + camel[1:]) if camel else "Connector"
    if show_operation:
        call_args = "{ operation: 'NomOperation', param1: 'value1' }"
    else:
        call_args = "{ param1: 'value1' }"
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
        f"call{fn_name}({call_args})",
        "  .then(result => console.log(result))",
        "  .catch(console.error);",
    ]
    return "\n".join(lines) + "\n"


def _php(url: str, key: str, snake: str, show_operation: bool) -> str:
    if show_operation:
        call_args = "['operation' => 'NomOperation', 'param1' => 'value1']"
    else:
        call_args = "['param1' => 'value1']"
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
        f"$result = call_{snake}({call_args});",
        "print_r($result);",
    ]
    return "\n".join(lines) + "\n"


def _java(url: str, key: str, pascal: str, show_operation: bool) -> str:
    if show_operation:
        example_comment = (
            '    // Exemple : Map.of("operation", "NomOperation", "param1", "value1")'
        )
    else:
        example_comment = (
            '    // Exemple : Map.of("param1", "value1")'
        )
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
        "",
        example_comment,
        "}",
    ]
    return "\n".join(lines) + "\n"
