# Plugin SDK

## Overview

DASH provides a plugin system that allows developers to extend functionality with sandboxed, permission-controlled plugins.

## Architecture

```
Plugin Package (directory with manifest.json)
  │
  ├── manifest.json  — Plugin metadata & permissions
  ├── main.py        — Plugin entry point
  └── ...            — Plugin resources

PluginLoader
  │
  ├── discover()     — Find plugin directories
  ├── load()         — Load plugin module
  └── unload()       — Remove plugin

PluginSandbox
  │
  ├── exec()         — Run code in sandbox
  └── restrict()     — Apply filesystem/permission restrictions

PluginPermissions
  │
  ├── check()        — Verify permission grant
  └── request()      — Request user consent
```

## Plugin Manifest

```json
{
  "name": "hello-world",
  "version": "1.0.0",
  "description": "Example plugin",
  "author": "",
  "entry": "main.py",
  "permissions": [
    "memory:read",
    "memory:write",
    "tools:read"
  ],
  "min_sdk_version": "0.1.0"
}
```

## Plugin API

Plugins receive a `PluginAPI` instance providing:

- `memory.read()` — Read from user's memory
- `memory.write()` — Write to user's memory
- `tools.execute()` — Execute a tool
- `logger` — Structured logging
- `permissions` — Permission checking

## Sandbox

- Restricted filesystem access (plugin workspace directory)
- Dangerous shell commands blocked
- Permission enforcement on all operations
- Path traversal prevention

## Example Plugin

```python
from dash_backend.plugins.api import PluginAPI

api = PluginAPI()

def main():
    api.logger.info("Hello World plugin loaded")
    memories = api.memory.read("user preferences")
    api.logger.info(f"Found {len(memories)} memories")
