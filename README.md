# Life Lab AI

English | [日本語](README.ja.md)

A 20×20 implementation of Conway's Game of Life built with Python and Flask.
Control the board in a browser, through natural-language instructions, or with an MCP client using stdio or Streamable HTTP.
This is a local learning and experimentation project. The interface, operation messages, and validation errors are in English. The local parser accepts English and Japanese instructions.

![Game of Life interface](docs/screenshot.jpg)

## Features

- Click to edit cells; start, stop, step, randomize, and clear the board
- Place gliders, blinkers, and blocks
- Parse common English and Japanese instructions locally, with optional OpenAI interpretation for other expressions
- Read and modify the board through MCP, with changes reflected in the browser
- Share one board across browsers and MCP clients, using revisions to detect conflicting edits

Cells outside the board are dead; edges do not wrap.
The board lives in the Flask process's memory. Reloading the page preserves it; restarting Flask resets it.

## Getting started

Requires Python 3.10 or later. Run these commands in the downloaded or cloned project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

On Windows, activate the environment with `.venv\Scripts\activate`.
Open <http://127.0.0.1:5000> in your browser. Press Ctrl+C in the terminal to stop the server.

## Natural-language commands

Enter an instruction and click **Execute**. These examples work without an API key:

| Instruction | Operation |
| --- | --- |
| `place a glider in the center` | Add a centered glider, preserving existing cells |
| `place a blinker at the top left` | Place a blinker at the top left |
| `place a block at the bottom right` | Place a block at the bottom right |
| `set row 3 column 5 alive` | Set one cell; use `dead` to clear it |
| `advance 10 generations` | Advance 10 generations; accepts 1–100 |
| `start` / `stop` | Start / stop automatic playback |
| `randomize` / `clear` | Replace the board and reset the generation counter |

Pattern placement, cell edits, and manual stepping stop playback.
Rows and columns use coordinates from 1 to 20. Invalid coordinates and unsupported instructions produce an error.
Japanese instructions remain supported; see [the Japanese README](README.ja.md) for examples.

### Optional OpenAI interpretation

Set `OPENAI_API_KEY` as an environment variable in the terminal used to start Flask.
Keep your key out of source files, documentation, MCP configuration examples, and the browser.
In Bash on macOS or Linux, you can enter it without placing the key in shell history:

```bash
read -r -s -p 'OpenAI API key: ' OPENAI_API_KEY
printf '\n'
export OPENAI_API_KEY
export OPENAI_MODEL='gpt-4o-mini'  # Optional; this is also the default
python app.py
```

Only instructions that the local parser cannot interpret are sent to the OpenAI Responses API.
For example, `盤面を空にしてから真ん中にグライダーを配置して` means “clear the board, then place a glider in the center.”
Only the instruction text is sent, not the board. API usage may incur charges.
The application does not automatically load `.env` files.

AI output is validated against an allowlist of operations. Up to 10 operations are applied only if all are valid.
The application does not execute generated code, inspect the board with AI, or generate unsupported patterns.
Verify live API connectivity and model access in your own environment.

## MCP connection

Start Flask before connecting an MCP client.
MCP operations do not require an OpenAI API key.

### stdio

`mcp-config.example.json` provides an example for clients using the `mcpServers` configuration format.
Replace `/absolute/path/to/life-lab-ai` with your local absolute path.
Configuration formats vary by client.

```json
{
  "mcpServers": {
    "life-lab": {
      "command": "/absolute/path/to/life-lab-ai/.venv/bin/python",
      "args": ["/absolute/path/to/life-lab-ai/mcp_server.py"],
      "env": { "LIFE_APP_URL": "http://127.0.0.1:5000" }
    }
  }
}
```

On Windows, use `.venv/Scripts/python.exe` as the Python executable.
The MCP client starts the server process. stdio does not have a connection URL.

### Streamable HTTP

In a separate terminal, activate the virtual environment and start the MCP server:

```bash
python mcp_server.py --transport streamable-http --port 8000
```

Set the MCP client's transport to **Streamable HTTP** and its URL to **http://127.0.0.1:8000/mcp**.
This is a protocol endpoint, not a regular web page.
If you change Flask's port, update the `LIFE_APP_URL` environment variable.
Press Ctrl+C to stop the MCP server. Omitting the startup options selects stdio.

### Tools

| Tool | Operation |
| --- | --- |
| `get_board` | Read the grid, generation, live-cell count, playback state, and revision |
| `set_cell` | Change one cell using `row`, `col`, and `alive` |
| `place_pattern` | Add `glider`, `blinker`, or `block`; `row` and `col` specify its top-left corner, defaulting to 9,9 |
| `step_generation` | Advance `steps` generations; defaults to 1, maximum 100 |
| `clear_board` | Clear all cells, reset the generation counter, and stop playback |
| `randomize_board` | Make about 30% of cells alive, reset the generation counter, and stop playback |
| `start_game` | Start automatic playback at four generations per second |
| `stop_game` | Stop automatic playback |

Pass the `revision` obtained from a read to editing tools to reject changes if another operation has already updated the board.
Automatic generations are calculated from elapsed server time when the board is read or modified.
Browsers poll every 250 ms; opening additional browsers does not increase the simulation speed.

## Security and limitations

- Flask and HTTP MCP listen on 127.0.0.1. This is an unauthenticated local experiment; other processes on the same computer can access it.
- Publishing the source does not deploy the application. Internet hosting and authentication for multiple users are not supported.
- The MCP bridge accepts Flask URLs only on localhost or 127.0.0.1. HTTP MCP uses the SDK's Host/Origin validation.
- AI operations are checked for allowed types, coordinates, and generation counts. Generated code is never executed.
- Do not include secrets in instructions. When OpenAI interpretation is enabled, instructions not recognized locally are sent to an external API.
- `.gitignore` excludes `.env` files, key files, local configuration, virtual environments, and caches. Inspect the files being committed before publishing.
- The board belongs to a single Flask process. Database persistence and multiple workers are not supported.

## Tests

With the virtual environment activated:

```bash
python -m unittest discover -s tests -v
```

Tests cover Life rules, instruction parsing, mocked AI responses, operation validation, revision conflicts, and real stdio/HTTP MCP connections.
MCP tests use an isolated board, temporary localhost ports, and subprocesses that are stopped during cleanup.
They do not verify live OpenAI requests or compatibility with every operating system.

## Project layout

```text
app.py                    Flask application and board APIs
commands.py               Instruction parsing, validation, and execution
shared_board.py           Shared board and revision management
mcp_server.py             MCP tools and transports
mcp-config.example.json   Example stdio configuration
locales/                  Japanese command compatibility data
static/                   JavaScript and CSS
templates/                HTML
tests/                    Automated tests
docs/screenshot.jpg       Example interface
```

The compatibility endpoints `/api/step` and `/api/command` perform independent calculations.
Use `/api/board`, `/api/board/actions`, and `/api/board/command` to interact with the shared board.

## License

[MIT License](LICENSE)
