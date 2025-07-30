import os
from typing import Dict
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
import requests
import sys
import traceback

# Set up exception handling to catch and log errors
def handle_exception(exc_type, exc_value, exc_traceback):
    print("Uncaught exception:", file=sys.stderr)
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    return sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = handle_exception

# Load environment variables
load_dotenv()

# Get gNucleus API from environment variables
GNUCLEUS_HOST = os.getenv("GNUCLEUS_HOST")
GNUCLEUS_API_KEY = os.getenv("GNUCLEUS_API_KEY")
# optional, only need for enterprise user
GNUCLEUS_ORG_ID = os.getenv("GNUCLEUS_ORG_ID") 

# Set up the MCP server
mcp = FastMCP("gNucleus MCP Server", request_timeout=300)

# Helper function for gNucleus REST API requests
def gnucleus_api_request(endpoint: str, payload: Dict = None) -> Dict | None:
    """Make a request to the gNucleus REST API"""
    if payload is None:
        payload = {}
        
    if not all([GNUCLEUS_HOST, GNUCLEUS_API_KEY]):
        print(f"Missing required GNUCLEUS_HOST and GNUCLEUS_API_KEY in .env file", file=sys.stderr)
        return {"message": "Configuration error: Missing API credentials"}

    url = f"https://{GNUCLEUS_HOST}:5000/api/{endpoint}"

    headers = {
        "Authorization": f"Bearer {GNUCLEUS_API_KEY}",
        "Content-Type": "application/json"
    }
    
    if GNUCLEUS_ORG_ID:
        payload["org_id"] = GNUCLEUS_ORG_ID
        
    try:
        print(f"Making API request to {url}", file=sys.stderr)
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API request error: {e}", file=sys.stderr)
        return {"message": f"API request failed: {str(e)}"}
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return {"message": "An unexpected error occurred"}


@mcp.tool()
def text_to_cad(input: str) -> str:
    """Transform a text prompt into a CAD Part or CAD Assembly and
    return a markdown summary plus a viewer URL."""
    print(f"text_to_cad called with input: {input}", file=sys.stderr)

    # ----- call gNucleus API -----
    response = gnucleus_api_request("text_to_cad", {"input": input})
    if not response:
        return f"gNucleus failed to generate CAD for '{input}' and no response from server, check your GNUCLEUS_HOST and GNUCLEUS_API_KEY"

    # ----- validate/normalize ID -----
    gnucleus_id = str(response.get("id", ""))
    if not gnucleus_id or not gnucleus_id.startswith("gnucleus-"):
        return f"gNucleus failed to generate CAD for '{input}' and the reponse is {response} "    

    # ----- build markdown -----
    result_lines: list[str] = []
    result_lines.append(f"### gNucleus\n\n{response.get('message', '')}\n")

    design_spec = response.get("design_spec", {}) or {}
    key_params = design_spec.get("key_parameters")
    conditions  = design_spec.get("conditions")
    description = design_spec.get("description")

    shared_result_url = f"https://gnucleus.ai/app/viewer/{gnucleus_id}"
    if response.get("is_assembly", False):
        asm_info  = response.get("assemblies_info", {}) or {}
        root_asm  = asm_info.get("root_assembly", None)
        if root_asm:
            result_lines.append(f"**Assembly:** `{root_asm}`\n")
            shared_result_url = f"https://gnucleus.ai/app/viewer/{gnucleus_id}/{root_asm}"
            result_lines.append(f"\n⚙️⚙️⚙️ **View the generated Root Assembly in this viewer URL:** {shared_result_url}\n")
        else:
            result_lines.append(f"\n⚙️⚙️⚙️ **Unable to generated Root Assembly**. Please check your input and try again.\n")

        if key_params:
            result_lines.append("**Key Parameters (assembly)**\n\n")
            result_lines.append(key_params.strip() if isinstance(key_params, str) else str(key_params))
        if conditions:
            result_lines.append(f"**Conditions:** {conditions}\n")
        if description:
            result_lines.append(f"**Description:** {description}\n")

        # list parts
        parts = asm_info.get("parts", [])
        if parts:
            result_lines.append("\n**Parts**\n")
            for p in parts:
                pname   = p.get("part_name", "(unnamed part)")
                pparams = p.get("key_parameters", "")
                result_lines.append(f"* **{pname}**\n")
                if pparams:
                    result_lines.append(pparams.strip() if isinstance(pparams, str) else str(pparams))
    else:  # single part
        if key_params:
            result_lines.append("**Key Parameters**\n")
            result_lines.append(key_params.strip() if isinstance(key_params, str) else str(key_params))
        if conditions:
            result_lines.append(f"**Conditions:** {conditions}\n")
        if description:
            result_lines.append(f"**Description:** {description}\n")
        result_lines.append(f"\n⚙️⚙️⚙️ **View the generated CAD in this viewer URL:** {shared_result_url}\n")

    print("Generating response successfully", file=sys.stderr)
    return "\n".join(result_lines)


if __name__ == "__main__":
    # Print a startup message
    print("Starting gNucleus MCP Server...", file=sys.stderr)
    print(f"GNUCLEUS_HOST is {GNUCLEUS_HOST}", file=sys.stderr)
    if GNUCLEUS_ORG_ID:
        print(f"GNUCLEUS_ORG_ID is {GNUCLEUS_ORG_ID}", file=sys.stderr)
    
    # Initialize and run the server
    try:
        mcp.run(transport='stdio')
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)